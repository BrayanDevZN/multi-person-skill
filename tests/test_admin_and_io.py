import json
import sqlite3
import sys

from conftest import persona_payload


def test_init_is_idempotent_and_creates_tables(cli):
    assert cli("init").ok and cli("init").ok
    assert set(cli("schema").data["tables"]) == {"ideas", "research", "personas", "persona_state", "runs", "reactions"}
    assert "convert" in cli("schema").data["enums"]["action"]


def test_stats(seeded):
    s = seeded("stats").data
    assert s["rows"]["personas"] == 3 and s["rows"]["ideas"] == 1 and s["size_bytes"] > 0


def test_query_read_only(seeded):
    ok = seeded("query", "--sql", "SELECT segment, COUNT(*) AS n FROM personas GROUP BY segment ORDER BY segment")
    assert ok.ok and len(ok.data["rows"]) == 3
    assert seeded("query", "--sql", "WITH x AS (SELECT 1 AS a) SELECT * FROM x").ok
    assert seeded("query", "--sql", "SELECT * FROM personas;").ok  # trailing semicolon tolerated
    for bad in ("DELETE FROM personas", "UPDATE personas SET age=1", "DROP TABLE personas",
                "SELECT 1; DELETE FROM personas", "PRAGMA table_info(personas)", "insert into ideas(name) values('x')"):
        r = seeded("query", "--sql", bad)
        assert not r.ok, bad
    assert seeded("persona", "list").data["total"] == 3  # nothing was modified
    assert not seeded("query").ok  # --sql missing
    assert "SQL error" in seeded("query", "--sql", "SELECT * FROM nope").error


def test_query_limit_truncates(seeded):
    r = seeded("query", "--sql", "SELECT * FROM personas", "--limit", "2")
    assert len(r.data["rows"]) == 2 and r.data["truncated"] is True


def test_export_json_csv_and_file(seeded, tmp_path):
    assert len(seeded("export", "--table", "personas").data["data"]) == 3
    csv_text = seeded("export", "--table", "personas", "--format", "csv").data["csv"]
    assert csv_text.splitlines()[0].startswith("id,name,age")
    out = tmp_path / "sub" / "p.json"
    r = seeded("export", "--table", "personas", "--out", str(out))
    assert r.data["rows"] == 3 and len(json.loads(out.read_text())) == 3
    assert not seeded("export", "--table", "nope").ok
    assert not seeded("export").ok


def test_commands_catalog_is_complete(cli):
    cat = cli("commands").data
    names = {c["command"] for c in cat}
    assert {"persona create", "reaction save", "run start", "report run", "query", "init"} <= names
    assert all(c["example"].startswith("socialsim ") for c in cat)
    create = next(c for c in cat if c["command"] == "persona create")
    assert create["payload_fields"]["age"] == {"type": "int", "required": True, "min": 13, "max": 100}


def test_payload_from_file_and_stdin(cli, tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(persona_payload(bio="long text, with \"quotes\" and ünïcode")), encoding="utf-8")
    assert cli("persona", "create", "--file", str(f)).ok
    assert "ünïcode" in cli("persona", "get", "1").data["bio"]
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(persona_payload(name="Stdin"))))
    assert cli("persona", "create", "--file", "-").ok
    assert not cli("persona", "create", "--file", str(tmp_path / "missing.json")).ok


def test_io_errors_are_json_with_hints(cli):
    bad = cli("persona", "create", "--json", "{oops")
    assert not bad.ok and bad.code == 1 and "invalid JSON" in bad.error and bad.hint
    both = cli("persona", "create", "--json", "{}", "--file", "x")
    assert "either --json or --file" in both.error
    missing = cli("persona", "create")
    assert "needs a JSON payload" in missing.error and "Example" in missing.hint
    assert not cli("persona", "create", "--json", "[1]").ok  # list of non-objects
    assert not cli("persona", "create", "--json", '"str"').ok


def test_usage_errors_are_json(cli):
    for argv in (["persona", "get", "abc"], ["persona", "bogus"], ["nonexistent"], ["persona", "get"]):
        r = cli(*argv)
        assert not r.ok and r.code == 2 and "invalid usage" in r.error, argv


def test_unicode_roundtrip(cli):
    cli("persona", "create", **persona_payload(name="José Ñandú 日本"))
    assert cli("persona", "get", "1").data["name"] == "José Ñandú 日本"


def test_foreign_keys_enforced(cli):
    cli("init")
    con = sqlite3.connect(cli.db)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        try:
            con.execute("INSERT INTO runs (idea_id, status) VALUES (999, 'running')")
            raised = False
        except sqlite3.IntegrityError:
            raised = True
    finally:
        con.close()
    assert raised


def test_query_rejects_multiple_statements(seeded):
    r = seeded("query", "--sql", "SELECT 1; SELECT 2")
    assert not r.ok and "single read-only" in r.error
