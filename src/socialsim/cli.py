"""CLI entrypoint. Stage 1 only exposes `init`; the full command set arrives in stage 2."""
from __future__ import annotations

import argparse
import json
import sys

from socialsim.db import init_schema, make_engine, resolve_db_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="socialsim")
    parser.add_argument("--db", help="Path to the SQLite file (default: $SOCIALSIM_DB or data/socialsim.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create the database and tables (safe to run repeatedly)")
    args = parser.parse_args(argv)

    path = resolve_db_path(args.db)
    engine = make_engine(path)
    init_schema(engine)
    print(json.dumps({"ok": True, "data": {"db": str(path)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
