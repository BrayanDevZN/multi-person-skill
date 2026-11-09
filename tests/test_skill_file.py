import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "social-sim"
TEXT = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


def frontmatter() -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", TEXT, re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    return dict(line.split(": ", 1) for line in m.group(1).splitlines())


def test_frontmatter_is_valid():
    fm = frontmatter()
    assert fm["name"] == SKILL_DIR.name == "social-sim"
    assert 50 < len(fm["description"]) <= 1024
    assert set(fm) == {"name", "description"}


def test_description_triggers_in_both_languages():
    d = frontmatter()["description"].lower()
    assert "simulate" in d and "persona" in d
    assert "anúncio" in d or "redes sociais" in d


def test_every_prompt_file_is_referenced_and_exists():
    for name in ("orchestrator.md", "cli_reference.md", "persona_generator.md", "persona_agent.md"):
        assert f"prompts/{name}" in TEXT or name in TEXT
        assert (SKILL_DIR / "prompts" / name).exists()
    listed = set(re.findall(r"^\s{2}(\w+\.md)\s", TEXT, re.M))
    assert listed == {p.name for p in (SKILL_DIR / "prompts").glob("*.md")}


def test_wrapper_referenced_by_skill_exists_and_is_executable():
    import os
    wrapper = SKILL_DIR.parents[2] / "bin" / "socialsim"
    assert "bin/socialsim" in TEXT and os.access(wrapper, os.X_OK)


def test_skill_states_the_hard_rules():
    for phrase in ("run start", "parallel", "every persona agent", "report run", "not market validation"):
        assert phrase in TEXT, phrase
