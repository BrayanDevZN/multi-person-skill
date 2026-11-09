"""socialsim CLI. Every command prints one JSON object: {"ok": true, "data": ...} or {"ok": false, "error", "hint"}."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, NoReturn

import socialsim.commands  # noqa: F401  (registers all commands)
from socialsim.core import Ctx
from socialsim.db import init_schema, make_engine, resolve_db_path, session_scope
from socialsim.registry import REGISTRY, Cmd
from socialsim.validation import CliError

GROUP_HELP = {
    "idea": "Ideas under test", "research": "Market research linked to ideas", "persona": "Reusable personas",
    "state": "Mutable persona state and memory", "run": "Simulation rounds", "reaction": "Persona reactions",
    "report": "Aggregated analysis",
}


def emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, default=str))


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        emit({"ok": False, "error": f"invalid usage: {message}", "hint": f"Run `{self.prog} --help` for usage"})
        sys.exit(2)


def read_payload(args: argparse.Namespace, cmd: Cmd) -> Any:
    if args.json is not None and args.file is not None:
        raise CliError("use either --json or --file, not both")
    raw: str | None = args.json
    if args.file is not None:
        try:
            raw = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        except OSError as e:
            raise CliError(f"cannot read --file: {e}") from e
    if raw is None:
        if cmd.payload == "required":
            raise CliError("this command needs a JSON payload", f"Example: socialsim {cmd.example}")
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise CliError(f"invalid JSON payload: {e}", "Check quotes/escaping; for long text use --file payload.json") from e


def add_leaf(sub: Any, cmd: Cmd) -> None:
    p = sub.add_parser(cmd.name, help=cmd.help, description=cmd.help, epilog=f"example:\n  socialsim {cmd.example}",
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    p.set_defaults(cmd=cmd)
    if cmd.id_arg:
        p.add_argument("id", type=int, metavar=cmd.id_arg)
    if cmd.payload:
        p.add_argument("--json", help="JSON payload")
        p.add_argument("--file", help="Path to a JSON file ('-' reads stdin)")
    flag_defs = {
        "confirm": dict(action="store_true", help="Confirm a destructive operation"),
        "full": dict(action="store_true", help="Include all fields (e.g. ReAct traces)"),
        "sql": dict(help="Read-only SELECT statement"),
        "limit": dict(type=int, help="Maximum rows to return"),
        "table": dict(help="Table name"),
        "format": dict(choices=["json", "csv"], help="Output format"),
        "out": dict(help="Write result to this file"),
    }
    for f in cmd.flags:
        p.add_argument(f"--{f}", **flag_defs[f])


def build_parser() -> argparse.ArgumentParser:
    parser = JsonParser(prog="socialsim", description="Persona simulation database CLI (JSON in, JSON out).")
    parser.add_argument("--db", help="SQLite file (default: $SOCIALSIM_DB or data/socialsim.db)")
    sub = parser.add_subparsers(dest="group_or_cmd", required=True, parser_class=JsonParser)
    groups: dict[str, Any] = {}
    for cmd in REGISTRY:
        if cmd.group is None:
            add_leaf(sub, cmd)
            continue
        if cmd.group not in groups:
            gp = sub.add_parser(cmd.group, help=GROUP_HELP.get(cmd.group, cmd.group))
            groups[cmd.group] = gp.add_subparsers(dest="sub", required=True, parser_class=JsonParser)
        add_leaf(groups[cmd.group], cmd)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd: Cmd = args.cmd
    try:
        payload = read_payload(args, cmd) if cmd.payload else None
        path = resolve_db_path(args.db)
        engine = make_engine(path)
        init_schema(engine)
        opts = {k: getattr(args, k, None) for k in cmd.flags}
        with session_scope(engine) as session:
            ctx = Ctx(session=session, engine=engine, db_path=str(path), id=getattr(args, "id", None),
                      payload=payload, opts=opts)
            data = cmd.fn(ctx)
        emit({"ok": True, "data": data})
        return 0
    except CliError as e:
        err: dict[str, Any] = {"ok": False, "error": e.message}
        if e.hint:
            err["hint"] = e.hint
        emit(err)
        return 1
    except Exception as e:  # noqa: BLE001
        emit({"ok": False, "error": f"{e.__class__.__name__}: {e}", "hint": "Unexpected error; check the payload and try again"})
        return 2


if __name__ == "__main__":
    sys.exit(main())
