"""idea.* and research.* commands."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from socialsim.core import Ctx, get_or_404, need_confirm, need_id, paginate, to_dict
from socialsim.models import Idea, Research, Run
from socialsim.registry import command
from socialsim.validation import CliError, Field, as_list, validate

IDEA_SPEC = {
    "name": Field("str", required=True),
    "description": Field("str"),
    "ad_copy": Field("str"),
}
RESEARCH_SPEC = {
    "idea_id": Field("int", required=True, min=1),
    "topic": Field("str", required=True),
    "finding": Field("str", required=True),
    "source_url": Field("str"),
}


def _name_taken(ctx: Ctx, name: str, exclude: int | None = None) -> bool:
    row = ctx.session.scalar(select(Idea).where(func.lower(Idea.name) == name.lower()))
    return row is not None and row.id != exclude


@command("idea", "create", help="Create an idea to be tested", payload="required", spec=IDEA_SPEC,
         example="""idea create --json '{"name": "Diet app", "description": "AI meal planner", "ad_copy": "Lose weight without counting calories"}'""")
def idea_create(ctx: Ctx) -> Any:
    data = validate(ctx.payload, IDEA_SPEC)
    if _name_taken(ctx, data["name"]):
        raise CliError(f"an idea named {data['name']!r} already exists", "Use `idea list --json '{\"q\": \"...\"}'` to find it and reuse its id")
    idea = Idea(**data)
    ctx.session.add(idea)
    ctx.session.flush()
    return to_dict(idea)


@command("idea", "get", help="Show an idea with its research and runs", id_arg="IDEA_ID",
         example="idea get 1")
def idea_get(ctx: Ctx) -> Any:
    idea = get_or_404(ctx.session, Idea, need_id(ctx, "idea"), "idea", "idea list")
    out = to_dict(idea)
    out["research"] = [to_dict(r) for r in idea.research]
    out["runs"] = [to_dict(r, ("id", "status", "started_at", "finished_at")) for r in idea.runs]
    return out


@command("idea", "list", help="List ideas (optional filter: q)", payload="optional", flags=("limit",),
         spec={"q": Field("str")}, example="""idea list --json '{"q": "diet"}'""")
def idea_list(ctx: Ctx) -> Any:
    q = (ctx.payload or {}).get("q", "").lower() if isinstance(ctx.payload, dict) else ""
    rows = []
    for idea in ctx.session.scalars(select(Idea).order_by(Idea.id)):
        if q and q not in f"{idea.name} {idea.description or ''}".lower():
            continue
        d = to_dict(idea, ("id", "name", "description", "created_at"))
        d["runs"] = len(idea.runs)
        d["research"] = len(idea.research)
        rows.append(d)
    return paginate(rows, ctx.opts)


@command("idea", "update", help="Update fields of an idea", id_arg="IDEA_ID", payload="required",
         spec=IDEA_SPEC, example="""idea update 1 --json '{"ad_copy": "New ad text"}'""")
def idea_update(ctx: Ctx) -> Any:
    idea = get_or_404(ctx.session, Idea, need_id(ctx, "idea"), "idea", "idea list")
    data = validate(ctx.payload, IDEA_SPEC, partial=True)
    if "name" in data and _name_taken(ctx, data["name"], exclude=idea.id):
        raise CliError(f"an idea named {data['name']!r} already exists")
    for k, v in data.items():
        setattr(idea, k, v)
    return to_dict(idea)


@command("idea", "delete", help="Delete an idea and its research/runs/reactions", id_arg="IDEA_ID",
         flags=("confirm",), example="idea delete 1 --confirm")
def idea_delete(ctx: Ctx) -> Any:
    idea = get_or_404(ctx.session, Idea, need_id(ctx, "idea"), "idea", "idea list")
    need_confirm(ctx, f"idea {idea.id} and all its runs")
    ctx.session.delete(idea)
    return {"deleted": idea.id}


@command("research", "add", help="Add research finding(s) to an idea (object, list, or {\"research\": [...]})",
         payload="required", spec=RESEARCH_SPEC,
         example="""research add --json '{"idea_id": 1, "topic": "competitors", "finding": "MyFitnessPal dominates calorie tracking", "source_url": "https://..."}'""")
def research_add(ctx: Ctx) -> Any:
    items = [validate(i, RESEARCH_SPEC) for i in as_list(ctx.payload, "research")]
    for i in items:
        get_or_404(ctx.session, Idea, i["idea_id"], "idea", "idea list")
    rows = [Research(**i) for i in items]
    ctx.session.add_all(rows)
    ctx.session.flush()
    return {"created": [r.id for r in rows]}


@command("research", "list", help="List research (optional filter: idea_id)", payload="optional",
         flags=("limit",), spec={"idea_id": Field("int", min=1)},
         example="""research list --json '{"idea_id": 1}'""")
def research_list(ctx: Ctx) -> Any:
    stmt = select(Research).order_by(Research.id)
    idea_id = (ctx.payload or {}).get("idea_id") if isinstance(ctx.payload, dict) else None
    if idea_id is not None:
        stmt = stmt.where(Research.idea_id == idea_id)
    return paginate([to_dict(r) for r in ctx.session.scalars(stmt)], ctx.opts, 200)


@command("research", "delete", help="Delete a research entry", id_arg="RESEARCH_ID", flags=("confirm",),
         example="research delete 3 --confirm")
def research_delete(ctx: Ctx) -> Any:
    row = get_or_404(ctx.session, Research, need_id(ctx, "research"), "research", "research list")
    need_confirm(ctx, f"research {row.id}")
    ctx.session.delete(row)
    return {"deleted": row.id}
