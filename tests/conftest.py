"""Test helpers: run the real CLI in-process against a throwaway SQLite file."""
from __future__ import annotations

import json
from typing import Any, Callable

import pytest

from socialsim.cli import main


class Result:
    def __init__(self, body: dict[str, Any], code: int):
        self.body, self.code = body, code
        self.ok: bool = body.get("ok", False)
        self.data = body.get("data")
        self.error: str = body.get("error", "")
        self.hint: str | None = body.get("hint")


@pytest.fixture
def cli(tmp_path, capsys) -> Callable[..., Result]:
    db = str(tmp_path / "test.db")

    def run(*args: str, **json_payload: Any) -> Result:
        argv = ["--db", db, *args]
        if json_payload:
            argv += ["--json", json.dumps(json_payload)]
        try:
            code = main(argv)
        except SystemExit as e:  # argparse usage errors
            code = int(e.code or 0)
        out = capsys.readouterr().out.strip().splitlines()
        return Result(json.loads(out[-1]), code)

    run.db = db  # type: ignore[attr-defined]
    return run


def persona_payload(**over: Any) -> dict[str, Any]:
    base = {"name": "Marina", "age": 32, "gender": "female", "occupation": "designer",
            "segment": "busy professional", "tags": ["lote-1"], "interests": ["yoga"]}
    return {**base, **over}


@pytest.fixture
def seeded(cli):
    """An idea (id 1) and three personas (ids 1-3)."""
    assert cli("idea", "create", name="Diet app", description="AI meal planner").ok
    assert cli("persona", "create", personas=[
        persona_payload(),
        persona_payload(name="Carlos", age=51, gender="male", occupation="driver", segment="health scare", tags=["lote-2"]),
        persona_payload(name="Ana", age=22, occupation="student", segment="budget student", tags=["lote-1"]),
    ]).ok
    return cli
