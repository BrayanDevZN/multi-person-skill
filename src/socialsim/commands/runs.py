"""run.*, reaction.* and report commands."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from socialsim.commands.personas import get_state
from socialsim.core import Ctx, get_or_404, need_confirm, need_id, paginate, to_dict
from socialsim.models import (ACTIONS, REACTION_STATUSES, RUN_STATUSES, SENTIMENTS, Idea, Persona,
                              Reaction, Run, utcnow)
from socialsim.registry import command
from socialsim.validation import CliError, Field, as_list, validate

RUN_START_SPEC = {
    "idea_id": Field("int", required=True, min=1),
    "persona_ids": Field("list_int", required=True),
    "notes": Field("str"),
}
RUN_LIST_SPEC = {"idea_id": Field("int", min=1), "status": Field("enum", choices=RUN_STATUSES)}
RUN_FINISH_SPEC = {"notes": Field("str")}
REACTION_SPEC = {
    "run_id": Field("int", required=True, min=1),
    "persona_id": Field("int", required=True, min=1),
    "status": Field("enum", choices=("ok", "failed")),
    "action": Field("enum", choices=ACTIONS),
    "sentiment": Field("enum", choices=SENTIMENTS),
    "purchase_intent": Field("int", min=0, max=10),
    "comment": Field("str"),
    "objections": Field("list_str"),
    "react_trace": Field("str"),
    "error": Field("str"),
}
REACTION_LIST_SPEC = {
    "run_id": Field("int", min=1), "persona_id": Field("int", min=1), "idea_id": Field("int", min=1),
    "action": Field("enum", choices=ACTIONS), "sentiment": Field("enum", choices=SENTIMENTS),
    "status": Field("enum", choices=REACTION_STATUSES),
    "min_intent": Field("int", min=0, max=10), "max_intent": Field("int", min=0, max=10),
}
MEMORY_CAP = 50


def _get_run(ctx: Ctx) -> Run:
    return get_or_404(ctx.session, Run, need_id(ctx, "run"), "run", "run list")


def _counts(run: Run) -> dict[str, int]:
    c = Counter(r.status for r in run.reactions)
    return {"planned": len(run.reactions), "ok": c["ok"], "failed": c["failed"], "pending": c["pending"]}


# ---------------------------------------------------------------- runs

@command("run", "start", help="Open a run: creates one pending reaction per persona", payload="required",
         spec=RUN_START_SPEC, example="""run start --json '{"idea_id": 1, "persona_ids": [1, 2, 3], "notes": "first pass"}'""")
def run_start(ctx: Ctx) -> Any:
    d = validate(ctx.payload, RUN_START_SPEC)
    idea = get_or_404(ctx.session, Idea, d["idea_id"], "idea", "idea list")
    ids = list(dict.fromkeys(d["persona_ids"]))
    found = {p.id: p for p in ctx.session.scalars(select(Persona).where(Persona.id.in_(ids)))}
    missing = [i for i in ids if i not in found]
    if missing:
        raise CliError(f"persona id(s) not found: {missing}", "Run `persona list` to see valid ids")
    prior = {
        r.persona_id
        for r in ctx.session.scalars(select(Reaction).join(Run).where(Run.idea_id == idea.id, Reaction.status == "ok"))
    }
    run = Run(idea_id=idea.id, notes=d.get("notes"), status="running")
    run.reactions = [Reaction(persona_id=i, status="pending") for i in ids]
    ctx.session.add(run)
    ctx.session.flush()
    return {"run_id": run.id, "idea": idea.name, "pending": len(ids),
            "already_reacted_to_this_idea": sorted(prior & set(ids))}


@command("run", "status", help="Progress of a run: counts and which personas are pending/failed", id_arg="RUN_ID",
         example="run status 1")
def run_status(ctx: Ctx) -> Any:
    run = _get_run(ctx)
    return {
        "run": to_dict(run), "counts": _counts(run),
        "pending_persona_ids": [r.persona_id for r in run.reactions if r.status == "pending"],
        "failed": [{"persona_id": r.persona_id, "error": r.error} for r in run.reactions if r.status == "failed"],
    }


@command("run", "finish", help="Close a run: 'completed' if all ok, else 'partial'", id_arg="RUN_ID",
         payload="optional", spec=RUN_FINISH_SPEC, example="run finish 1")
def run_finish(ctx: Ctx) -> Any:
    run = _get_run(ctx)
    d = validate(ctx.payload or {}, RUN_FINISH_SPEC, partial=True)
    counts = _counts(run)
    run.status = "completed" if counts["ok"] == counts["planned"] else "partial"
    run.finished_at = utcnow()
    if "notes" in d:
        run.notes = d["notes"]
    return {"run_id": run.id, "status": run.status, "counts": counts}


@command("run", "list", help="List runs (filters: idea_id, status)", payload="optional", flags=("limit",),
         spec=RUN_LIST_SPEC, example="""run list --json '{"idea_id": 1}'""")
def run_list(ctx: Ctx) -> Any:
    f = validate(ctx.payload or {}, RUN_LIST_SPEC, partial=True)
    stmt = select(Run).order_by(Run.id.desc())
    if "idea_id" in f:
        stmt = stmt.where(Run.idea_id == f["idea_id"])
    if "status" in f:
        stmt = stmt.where(Run.status == f["status"])
    rows = [{**to_dict(r, ("id", "idea_id", "status", "started_at", "finished_at")), "counts": _counts(r)}
            for r in ctx.session.scalars(stmt)]
    return paginate(rows, ctx.opts, 50)


@command("run", "resume", help="Reopen a run: failed reactions become pending; returns who still needs simulating",
         id_arg="RUN_ID", example="run resume 1")
def run_resume(ctx: Ctx) -> Any:
    run = _get_run(ctx)
    for r in run.reactions:
        if r.status == "failed":
            r.status, r.error = "pending", None
    run.status, run.finished_at = "running", None
    todo = [r for r in run.reactions if r.status == "pending"]
    return {"run_id": run.id, "idea_id": run.idea_id,
            "todo": [{"persona_id": r.persona_id, "name": r.persona.name} for r in todo]}


@command("run", "delete", help="Delete a run and its reactions", id_arg="RUN_ID", flags=("confirm",),
         example="run delete 1 --confirm")
def run_delete(ctx: Ctx) -> Any:
    run = _get_run(ctx)
    need_confirm(ctx, f"run {run.id}")
    ctx.session.delete(run)
    return {"deleted": run.id}


# ---------------------------------------------------------------- reactions

def _validate_reaction(item: Any) -> dict[str, Any]:
    d = validate(item, REACTION_SPEC)
    d.setdefault("status", "ok")
    if d["status"] == "ok":
        missing = [k for k in ("action", "sentiment", "purchase_intent") if d.get(k) is None]
        if missing:
            raise CliError(f"status 'ok' requires {missing}", "Use status 'failed' with an 'error' message if the simulation did not finish")
    elif not d.get("error"):
        raise CliError("status 'failed' requires 'error'")
    return d


def _remember(ctx: Ctx, run: Run, persona: Persona, d: dict[str, Any]) -> None:
    st = get_state(ctx.session, persona)
    idea = run.idea
    entry = {"run_id": run.id, "idea_id": idea.id, "idea": idea.name, "action": d["action"],
             "sentiment": d["sentiment"], "purchase_intent": d["purchase_intent"]}
    mem = [m for m in (st.memory or []) if m.get("run_id") != run.id]
    st.memory = [*mem, entry][-MEMORY_CAP:]
    st.updated_at = utcnow()


@command("reaction", "save",
         help="Save reaction(s) (object, list, or {\"reactions\": [...]}). Upserts per (run, persona); updates persona memory.",
         payload="required", spec=REACTION_SPEC,
         example="""reaction save --json '{"run_id": 1, "persona_id": 3, "action": "reject", "sentiment": "negative", "purchase_intent": 1, "comment": "Another diet app...", "objections": ["too expensive", "no trust"], "react_trace": "Thought: ... Action: ... Observation: ..."}'""")
def reaction_save(ctx: Ctx) -> Any:
    items = [_validate_reaction(i) for i in as_list(ctx.payload, "reactions")]
    saved = []
    for d in items:
        run = get_or_404(ctx.session, Run, d["run_id"], "run", "run list")
        persona = get_or_404(ctx.session, Persona, d["persona_id"], "persona", "persona list")
        row = ctx.session.scalar(select(Reaction).where(Reaction.run_id == run.id, Reaction.persona_id == persona.id))
        if row is None:
            row = Reaction(run_id=run.id, persona_id=persona.id)
            ctx.session.add(row)
        for k in ("status", "action", "sentiment", "purchase_intent", "comment", "objections", "react_trace", "error"):
            setattr(row, k, d.get(k))
        if d["status"] == "ok":
            row.error = None
            _remember(ctx, run, persona, d)
        row.updated_at = utcnow()
        ctx.session.flush()
        saved.append({"reaction_id": row.id, "run_id": run.id, "persona_id": persona.id, "status": row.status})
    return {"saved": saved}


def _reaction_view(r: Reaction, full: bool) -> dict[str, Any]:
    d = to_dict(r)
    if not full:
        d.pop("react_trace", None)
    d["persona_name"] = r.persona.name
    d["idea_id"] = r.run.idea_id
    return d


@command("reaction", "get", help="Show one reaction including its ReAct trace", id_arg="REACTION_ID",
         example="reaction get 7")
def reaction_get(ctx: Ctx) -> Any:
    r = get_or_404(ctx.session, Reaction, need_id(ctx, "reaction"), "reaction", "reaction list")
    return _reaction_view(r, True)


@command("reaction", "list", help="List reactions (filters; traces hidden unless --full)", payload="optional",
         flags=("limit", "full"), spec=REACTION_LIST_SPEC,
         example="""reaction list --json '{"run_id": 1, "sentiment": "negative"}'""")
def reaction_list(ctx: Ctx) -> Any:
    f = validate(ctx.payload or {}, REACTION_LIST_SPEC, partial=True)
    stmt = select(Reaction).join(Run).order_by(Reaction.id)
    for key, col in (("run_id", Reaction.run_id), ("persona_id", Reaction.persona_id), ("idea_id", Run.idea_id),
                     ("action", Reaction.action), ("sentiment", Reaction.sentiment), ("status", Reaction.status)):
        if key in f:
            stmt = stmt.where(col == f[key])
    if "min_intent" in f:
        stmt = stmt.where(Reaction.purchase_intent >= f["min_intent"])
    if "max_intent" in f:
        stmt = stmt.where(Reaction.purchase_intent <= f["max_intent"])
    rows = [_reaction_view(r, bool(ctx.opts.get("full"))) for r in ctx.session.scalars(stmt)]
    return {"total": len(rows), "reactions": paginate(rows, ctx.opts, 200)}


@command("reaction", "delete", help="Delete a reaction", id_arg="REACTION_ID", flags=("confirm",),
         example="reaction delete 7 --confirm")
def reaction_delete(ctx: Ctx) -> Any:
    r = get_or_404(ctx.session, Reaction, need_id(ctx, "reaction"), "reaction", "reaction list")
    need_confirm(ctx, f"reaction {r.id}")
    ctx.session.delete(r)
    return {"deleted": r.id}


# ---------------------------------------------------------------- report

def _age_group(age: int) -> str:
    for upper, label in ((17, "<18"), (24, "18-24"), (34, "25-34"), (44, "35-44"), (54, "45-54")):
        if age <= upper:
            return label
    return "55+"


def _avg(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _bucket(rs: list[Reaction]) -> dict[str, Any]:
    return {
        "n": len(rs),
        "avg_purchase_intent": _avg([r.purchase_intent for r in rs]),
        "conversions": sum(r.action == "convert" for r in rs),
        "positive": sum(r.sentiment == "positive" for r in rs),
        "negative": sum(r.sentiment == "negative" for r in rs),
    }


@command("report", "run", help="Aggregated analysis of a run (conversion, objections, segments, highlights)",
         id_arg="RUN_ID", example="report run 1")
def report_run(ctx: Ctx) -> Any:
    run = _get_run(ctx)
    ok = [r for r in run.reactions if r.status == "ok"]
    objections = Counter(o.strip().lower() for r in ok for o in (r.objections or []) if o.strip())
    by_segment: dict[str, list[Reaction]] = defaultdict(list)
    by_age: dict[str, list[Reaction]] = defaultdict(list)
    for r in ok:
        by_segment[r.persona.segment or "(none)"].append(r)
        by_age[_age_group(r.persona.age)].append(r)

    def card(r: Reaction) -> dict[str, Any]:
        return {"persona_id": r.persona_id, "name": r.persona.name, "age": r.persona.age,
                "segment": r.persona.segment, "action": r.action, "purchase_intent": r.purchase_intent,
                "comment": r.comment}

    ranked = sorted(ok, key=lambda r: (r.purchase_intent, r.id))
    n = len(ok)
    return {
        "run": to_dict(run, ("id", "idea_id", "status", "started_at", "finished_at")),
        "idea": run.idea.name,
        "counts": _counts(run),
        "actions": dict(Counter(r.action for r in ok)),
        "sentiment": dict(Counter(r.sentiment for r in ok)),
        "conversion_rate": round(sum(r.action == "convert" for r in ok) / n, 3) if n else None,
        "engagement_rate": round(sum(r.action != "ignore" for r in ok) / n, 3) if n else None,
        "avg_purchase_intent": _avg([r.purchase_intent for r in ok]),
        "top_objections": [{"objection": o, "count": c} for o, c in objections.most_common(10)],
        "by_segment": {k: _bucket(v) for k, v in sorted(by_segment.items())},
        "by_age_group": {k: _bucket(v) for k, v in sorted(by_age.items())},
        "highlights": {"most_interested": [card(r) for r in reversed(ranked[-3:])],
                       "least_interested": [card(r) for r in ranked[:3]]},
        "failed": [{"persona_id": r.persona_id, "error": r.error} for r in run.reactions if r.status == "failed"],
        "pending_persona_ids": [r.persona_id for r in run.reactions if r.status == "pending"],
    }
