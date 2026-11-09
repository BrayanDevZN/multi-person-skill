"""Guard against drift between the prompts and the CLI they teach."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from socialsim.commands.personas import PERSONA_SPEC
from socialsim.commands.runs import REACTION_SPEC
from socialsim.registry import REGISTRY
from socialsim.validation import validate

PROMPTS = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "social-sim" / "prompts"
FILES = {n: (PROMPTS / n).read_text(encoding="utf-8") for n in
         ("cli_reference.md", "persona_agent.md", "persona_generator.md", "orchestrator.md")}
COMMANDS = {f"{c.group} {c.name}" if c.group else c.name for c in REGISTRY}


def example_outputs(text: str) -> list[str]:
    return re.findall(r"<example_output>\s*(.*?)\s*</example_output>", text, re.S)


def test_every_command_is_documented_in_the_reference():
    headings = set(re.findall(r"^### `([^`]+)`", FILES["cli_reference.md"], re.M))
    assert COMMANDS == headings, f"missing: {COMMANDS - headings}, stale: {headings - COMMANDS}"


def test_every_cli_invocation_in_prompts_uses_a_real_command():
    seen = 0
    for name, text in FILES.items():
        for line in text.splitlines():
            m = re.search(r"bin/socialsim\s+((?:--db\s+\S+\s+)?)([a-z]+)(?:\s+([a-z]+))?", line)
            if not m or line.strip().startswith("#"):
                continue
            first, second = m.group(2), m.group(3)
            ok = first in COMMANDS or (second and f"{first} {second}" in COMMANDS)
            assert ok, f"{name}: unknown command in line: {line.strip()}"
            seen += 1
    assert seen > 30


def test_json_payload_examples_in_prompts_parse_and_validate():
    """Every `--json '{...}'` example must be valid JSON whose fields exist in that command's spec."""
    by_name = {f"{c.group} {c.name}" if c.group else c.name: c for c in REGISTRY}
    checked = 0
    for name, text in FILES.items():
        for m in re.finditer(r"bin/socialsim\s+([a-z]+)\s+([a-z]+)[^\n]*?--json\s+'(\{.*?\})'", text, re.S):
            cmd = by_name.get(f"{m.group(1)} {m.group(2)}")
            if cmd is None or not cmd.spec:
                continue
            raw = m.group(3)
            if "..." in raw:
                continue  # abridged illustration
            payload = json.loads(raw)
            wrapper = next(iter(payload)) if len(payload) == 1 else None
            items = payload[wrapper] if wrapper in ("personas", "reactions", "research") else [payload]
            for item in items:
                validate(item, cmd.spec, partial=True)
            checked += 1
    assert checked >= 10


MARKER = re.compile(r"^=== PROMPT START ===$", re.M)


def split_prompt(text: str) -> tuple[str, str]:
    parts = MARKER.split(text)
    assert len(parts) == 2, "the marker line must appear exactly once"
    return parts[0], parts[1]


def test_persona_agent_placeholders_match_documentation():
    head, body = split_prompt(FILES["persona_agent.md"])
    used = set(re.findall(r"\{\{([A-Z_]+)\}\}", body))
    documented = set(re.findall(r"- `\{\{([A-Z_]+)\}\}`", head))
    assert used == documented == {"PERSONA_JSON", "PERSONA_MEMORY_JSON", "AD_JSON", "PLATFORM", "SESSION_CONTEXT", "MARKET_BRIEF", "RESEARCH_RULES"}
    for p in used:
        assert p in FILES["orchestrator.md"], f"orchestrator does not explain {p}"


def test_persona_generator_placeholders_match_documentation():
    head, body = split_prompt(FILES["persona_generator.md"])
    used = set(re.findall(r"\{\{([A-Z_]+)\}\}", body))
    documented = set(re.findall(r"- `\{\{([A-Z_]+)\}\}`", head))
    assert used == documented


@pytest.mark.parametrize("raw", example_outputs(FILES["persona_agent.md"]))
def test_persona_agent_examples_are_valid_reactions(raw):
    out = json.loads(raw)
    assert set(out) == {"action", "sentiment", "purchase_intent", "comment", "objections", "react_trace"}
    validate({"run_id": 1, "persona_id": 1, **out}, REACTION_SPEC)  # exactly what the orchestrator will save
    a, s, i = out["action"], out["sentiment"], out["purchase_intent"]
    if a == "convert":
        assert i >= 7 and s != "negative"
    if a == "reject":
        assert s == "negative" and i <= 3
    if a == "ignore":
        assert i <= 4 and out["comment"] is None
    if a == "comment":
        assert out["comment"]
    trace = out["react_trace"]
    assert trace.startswith("Thought:") and f"Action: decide[{a}]" in trace and trace.endswith("Observation: done")
    assert not re.search(r"\b(AI|simulation|persona|language model)\b", trace + (out["comment"] or ""), re.I)


def test_persona_agent_examples_are_contrasting():
    actions = {json.loads(r)["action"] for r in example_outputs(FILES["persona_agent.md"])}
    assert {"convert", "ignore", "reject"} <= actions


@pytest.mark.parametrize("raw", example_outputs(FILES["persona_generator.md"]))
def test_persona_generator_examples_are_valid_personas(raw):
    personas = json.loads(raw)
    assert len(personas) >= 2
    keys = {"openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism", "skepticism",
            "price_sensitivity", "impulsivity", "tech_savviness", "ad_attitude", "social_media_habits", "pain_points"}
    for p in personas:
        validate(p, PERSONA_SPEC)
        assert keys <= set(p["personality"])
        assert "ledger-2026-11" in p["tags"] and p["origin"].startswith("sim:")
    assert len({p["name"] for p in personas}) == len(personas)
    assert {p["personality"]["skepticism"] for p in personas} != {"low"}  # not all enthusiasts


def test_orchestrator_references_companion_files_that_exist():
    for f in ("cli_reference.md", "persona_generator.md", "persona_agent.md"):
        assert f in FILES["orchestrator.md"] and (PROMPTS / f).exists()


@pytest.mark.parametrize("name", ["persona_agent.md", "persona_generator.md", "orchestrator.md"])
def test_prompts_have_required_sections(name):
    text = FILES[name]
    for section in ("# ROLE", "# BEHAVIOR", "# CONSTRAINTS"):
        assert section in text, f"{name} lacks {section}"
    assert "EXAMPLE" in text


def test_orchestrator_asks_about_persona_research_and_html_report():
    orch = FILES["orchestrator.md"]
    assert "research_mode" in orch and "WebSearch" in orch
    assert "report html" in orch and "HTML REPORT" in orch
    assert "pesquisar na web" in orch  # the question asked to the user
