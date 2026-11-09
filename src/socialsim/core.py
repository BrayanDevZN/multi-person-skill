"""Shared helpers: context, serialization, lookups."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from socialsim.validation import CliError


@dataclass
class Ctx:
    session: Session
    engine: Engine
    db_path: str
    id: int | None = None
    payload: Any = None
    opts: dict[str, Any] = field(default_factory=dict)


def to_dict(obj: Any, only: tuple[str, ...] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        if only is not None and col.name not in only:
            continue
        v = getattr(obj, col.name)
        out[col.name] = v.isoformat(timespec="seconds") if isinstance(v, datetime) else v
    return out


def get_or_404(session: Session, model: type, pk: int, label: str, list_cmd: str) -> Any:
    obj = session.get(model, pk)
    if obj is None:
        raise CliError(f"{label} {pk} not found", f"Run `{list_cmd}` to see valid ids")
    return obj


def need_id(ctx: Ctx, label: str) -> int:
    if ctx.id is None:
        raise CliError(f"{label} id is required")
    return ctx.id


def need_confirm(ctx: Ctx, what: str) -> None:
    if not ctx.opts.get("confirm"):
        raise CliError(f"refusing to delete {what} without --confirm", "Re-run the same command adding --confirm")


def paginate(rows: list[Any], opts: dict[str, Any], default_limit: int = 100) -> list[Any]:
    limit = opts.get("limit") or default_limit
    return rows[:limit]
