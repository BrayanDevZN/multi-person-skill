"""Top-level commands: init, schema, stats, query, export, commands."""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select, text

from socialsim import models
from socialsim.core import Ctx, to_dict
from socialsim.registry import REGISTRY, command
from socialsim.validation import CliError

TABLES = {m.__tablename__: m for m in (models.Idea, models.Research, models.Persona, models.PersonaState,
                                       models.Run, models.Reaction)}
FORBIDDEN_SQL = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum)\b", re.I)


@command(None, "init", help="Create the database and tables (idempotent)", example="init")
def init(ctx: Ctx) -> Any:
    return {"db": ctx.db_path, "tables": sorted(TABLES)}


@command(None, "schema", help="Show tables, columns and allowed enum values", example="schema")
def schema(ctx: Ctx) -> Any:
    insp = inspect(ctx.engine)
    tables = {
        t: [{"name": c["name"], "type": str(c["type"]), "nullable": c["nullable"]} for c in insp.get_columns(t)]
        for t in sorted(insp.get_table_names())
    }
    return {"tables": tables, "enums": {"action": models.ACTIONS, "sentiment": models.SENTIMENTS,
                                        "reaction_status": models.REACTION_STATUSES, "run_status": models.RUN_STATUSES}}


@command(None, "stats", help="Row counts and run overview", example="stats")
def stats(ctx: Ctx) -> Any:
    counts = {name: ctx.session.scalar(select(func.count()).select_from(m)) for name, m in TABLES.items()}
    runs = dict(ctx.session.execute(select(models.Run.status, func.count()).group_by(models.Run.status)).all())
    path = Path(ctx.db_path)
    return {"db": ctx.db_path, "size_bytes": path.stat().st_size if path.exists() else 0, "rows": counts, "runs_by_status": runs}


@command(None, "query", help="Read-only SQL (SELECT/WITH only) for ad-hoc analysis", flags=("sql", "limit"),
         example="""query --sql "SELECT segment, COUNT(*) n FROM personas GROUP BY segment" """)
def query(ctx: Ctx) -> Any:
    sql = (ctx.opts.get("sql") or "").strip().rstrip(";")
    if not sql:
        raise CliError("--sql is required", 'e.g. query --sql "SELECT * FROM personas LIMIT 5"')
    if not re.match(r"^(select|with)\b", sql, re.I) or ";" in sql or FORBIDDEN_SQL.search(sql):
        raise CliError("only a single read-only SELECT/WITH statement is allowed",
                       "Use the dedicated commands (persona create, reaction save...) for writes")
    limit = ctx.opts.get("limit") or 200
    with ctx.engine.connect() as conn:
        conn.execute(text("PRAGMA query_only=ON"))
        try:
            result = conn.execute(text(sql))
            rows = [dict(r._mapping) for r in result.fetchmany(limit + 1)]
        except Exception as e:  # noqa: BLE001
            raise CliError(f"SQL error: {e.__class__.__name__}: {getattr(e, 'orig', e)}",
                           "Run `schema` to see table and column names") from e
        finally:
            conn.execute(text("PRAGMA query_only=OFF"))
    return {"rows": rows[:limit], "truncated": len(rows) > limit}


@command(None, "export", help="Export a table as json or csv (to stdout payload or a file with --out)",
         flags=("table", "format", "out"), example="export --table personas --format csv --out /tmp/personas.csv")
def export(ctx: Ctx) -> Any:
    table = ctx.opts.get("table")
    if table not in TABLES:
        raise CliError(f"--table must be one of {sorted(TABLES)}")
    fmt = ctx.opts.get("format") or "json"
    cols = [c.name for c in TABLES[table].__table__.columns]
    rows = [to_dict(o) for o in ctx.session.scalars(select(TABLES[table]))]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()})
        content: Any = buf.getvalue()
    else:
        content = rows
    out = ctx.opts.get("out")
    if out:
        p = Path(out).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if fmt == "csv" else json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"table": table, "rows": len(rows), "file": str(p.resolve())}
    return {"table": table, "rows": len(rows), "csv" if fmt == "csv" else "data": content}


@command(None, "commands", help="Machine-readable catalog of every command with payload fields and examples",
         example="commands")
def commands(ctx: Ctx) -> Any:
    out = []
    for c in REGISTRY:
        out.append({
            "command": f"{c.group} {c.name}" if c.group else c.name,
            "help": c.help,
            "positional_id": c.id_arg,
            "payload": c.payload,
            "payload_fields": {k: f.describe() for k, f in (c.spec or {}).items()} or None,
            "flags": list(c.flags),
            "example": f"socialsim {c.example}",
        })
    return out
