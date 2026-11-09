"""persona.* and state.* commands."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from socialsim.core import Ctx, get_or_404, need_confirm, need_id, paginate, to_dict
from socialsim.models import Idea, Persona, PersonaState, Reaction, utcnow
from socialsim.registry import command
from socialsim.validation import CliError, Field, as_list, validate

PERSONA_SPEC = {
    "name": Field("str", required=True),
    "age": Field("int", required=True, min=13, max=100),
    "gender": Field("str"),
    "occupation": Field("str"),
    "income_level": Field("str"),
    "location": Field("str"),
    "segment": Field("str"),
    "bio": Field("str"),
    "personality": Field("dict"),
    "interests": Field("list_str"),
    "platforms": Field("list_str"),
    "tags": Field("list_str"),
    "origin": Field("str"),
}
COMPACT = ("id", "name", "age", "gender", "occupation", "segment", "tags", "platforms", "origin")

LIST_SPEC = {
    "min_age": Field("int"), "max_age": Field("int"), "gender": Field("str"), "segment": Field("str"),
    "tag": Field("str"), "origin": Field("str"), "q": Field("str"), "ids": Field("list_int"),
    "reacted_idea_id": Field("int", min=1), "not_reacted_idea_id": Field("int", min=1),
}
SEARCH_SPEC = {
    "age": Field("int"), "gender": Field("str"), "occupation": Field("str"), "segment": Field("str"),
    "location": Field("str"), "interests": Field("list_str"), "min_score": Field("int", min=1),
}
STATE_SPEC = {
    "mood": Field("str"),
    "interest_level": Field("int", min=0, max=10),
    "notes": Field("str"),
    "memory_append": Field("dict"),
}
DUPLICATE_SCORE = 7


def _eq(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()


def persona_view(p: Persona, full: bool) -> dict[str, Any]:
    return to_dict(p) if full else to_dict(p, COMPACT)


def get_state(session, persona: Persona) -> PersonaState:
    if persona.state is None:
        persona.state = PersonaState(persona_id=persona.id, memory=[])
        session.flush()
    return persona.state


@command("persona", "create", help="Create persona(s) (object, list, or {\"personas\": [...]}). All-or-nothing.",
         payload="required", spec=PERSONA_SPEC,
         example="""persona create --json '{"name": "Marina Souza", "age": 32, "gender": "female", "occupation": "graphic designer", "income_level": "middle", "location": "Sao Paulo, BR", "segment": "busy professional", "bio": "Freelancer, skips meals when deadlines hit.", "personality": {"openness": "high", "skepticism": "medium"}, "interests": ["design", "yoga"], "platforms": ["instagram", "pinterest"], "tags": ["lote-1"], "origin": "sim:diet-app"}'""")
def persona_create(ctx: Ctx) -> Any:
    items = [validate(i, PERSONA_SPEC) for i in as_list(ctx.payload, "personas")]
    rows = [Persona(**i) for i in items]
    ctx.session.add_all(rows)
    ctx.session.flush()
    for r in rows:
        r.state = PersonaState(persona_id=r.id, memory=[])
    ctx.session.flush()
    return {"created": [{"id": r.id, "name": r.name} for r in rows]}


@command("persona", "get", help="Show a persona with state and reaction history", id_arg="PERSONA_ID",
         example="persona get 5")
def persona_get(ctx: Ctx) -> Any:
    p = get_or_404(ctx.session, Persona, need_id(ctx, "persona"), "persona", "persona list")
    out = to_dict(p)
    st = get_state(ctx.session, p)
    out["state"] = to_dict(st)
    ideas = {i.id: i.name for i in ctx.session.scalars(select(Idea))}
    out["history"] = [
        {"run_id": r.run_id, "idea_id": r.run.idea_id, "idea": ideas.get(r.run.idea_id), "status": r.status,
         "action": r.action, "sentiment": r.sentiment, "purchase_intent": r.purchase_intent}
        for r in sorted(p.reactions, key=lambda r: r.run_id)
    ]
    return out


@command("persona", "list", help="List personas with filters", payload="optional", flags=("limit", "full"),
         spec=LIST_SPEC,
         example="""persona list --json '{"min_age": 30, "max_age": 45, "tag": "lote-1", "not_reacted_idea_id": 2}'""")
def persona_list(ctx: Ctx) -> Any:
    f = validate(ctx.payload or {}, LIST_SPEC, partial=True)
    reacted: set[int] | None = None
    not_reacted: set[int] = set()
    if "reacted_idea_id" in f or "not_reacted_idea_id" in f:
        from socialsim.models import Run

        def ids_for(idea_id: int) -> set[int]:
            stmt = select(Reaction.persona_id).join(Run).where(Run.idea_id == idea_id, Reaction.status == "ok")
            return set(ctx.session.scalars(stmt))

        if "reacted_idea_id" in f:
            reacted = ids_for(f["reacted_idea_id"])
        if "not_reacted_idea_id" in f:
            not_reacted = ids_for(f["not_reacted_idea_id"])
    q = f.get("q", "").lower()
    rows = []
    for p in ctx.session.scalars(select(Persona).order_by(Persona.id)):
        if "ids" in f and p.id not in f["ids"]:
            continue
        if "min_age" in f and p.age < f["min_age"]:
            continue
        if "max_age" in f and p.age > f["max_age"]:
            continue
        if "gender" in f and not _eq(p.gender, f["gender"]):
            continue
        if "segment" in f and not _eq(p.segment, f["segment"]):
            continue
        if "origin" in f and not _eq(p.origin, f["origin"]):
            continue
        if "tag" in f and f["tag"].lower() not in [t.lower() for t in (p.tags or [])]:
            continue
        if reacted is not None and p.id not in reacted:
            continue
        if p.id in not_reacted:
            continue
        if q and q not in " ".join(str(x) for x in (p.name, p.occupation, p.bio, p.segment, p.location) if x).lower():
            continue
        rows.append(persona_view(p, bool(ctx.opts.get("full"))))
    return {"total": len(rows), "personas": paginate(rows, ctx.opts, 200)}


@command("persona", "search", help="Find similar existing personas (duplicate check before creating)",
         payload="required", spec=SEARCH_SPEC,
         example="""persona search --json '{"age": 32, "gender": "female", "occupation": "graphic designer", "segment": "busy professional"}'""")
def persona_search(ctx: Ctx) -> Any:
    f = validate(ctx.payload, SEARCH_SPEC)
    if not f or set(f) == {"min_score"}:
        raise CliError("provide at least one profile field to compare", "e.g. {\"age\": 32, \"segment\": \"...\"}")
    min_score = f.get("min_score", 3)
    wanted = {i.lower() for i in f.get("interests", [])}
    scored = []
    for p in ctx.session.scalars(select(Persona)):
        score = 0
        if _eq(p.segment, f.get("segment")):
            score += 3
        if _eq(p.gender, f.get("gender")):
            score += 1
        if "age" in f:
            diff = abs(p.age - f["age"])
            score += 2 if diff <= 3 else 1 if diff <= 6 else 0
        if _eq(p.occupation, f.get("occupation")):
            score += 2
        if _eq(p.location, f.get("location")):
            score += 1
        score += min(3, len(wanted & {i.lower() for i in (p.interests or [])}))
        if score >= min_score:
            scored.append({"score": score, "likely_duplicate": score >= DUPLICATE_SCORE, "persona": to_dict(p, COMPACT)})
    scored.sort(key=lambda r: -r["score"])
    return {"matches": scored[:10], "duplicate_threshold": DUPLICATE_SCORE}


@command("persona", "update", help="Update persona fields", id_arg="PERSONA_ID", payload="required",
         spec=PERSONA_SPEC, example="""persona update 5 --json '{"tags": ["lote-1", "fitness"]}'""")
def persona_update(ctx: Ctx) -> Any:
    p = get_or_404(ctx.session, Persona, need_id(ctx, "persona"), "persona", "persona list")
    for k, v in validate(ctx.payload, PERSONA_SPEC, partial=True).items():
        setattr(p, k, v)
    p.updated_at = utcnow()
    return to_dict(p)


@command("persona", "delete", help="Delete a persona (and its state/reactions)", id_arg="PERSONA_ID",
         flags=("confirm",), example="persona delete 5 --confirm")
def persona_delete(ctx: Ctx) -> Any:
    p = get_or_404(ctx.session, Persona, need_id(ctx, "persona"), "persona", "persona list")
    need_confirm(ctx, f"persona {p.id} ({p.name})")
    ctx.session.delete(p)
    return {"deleted": p.id}


@command("state", "get", help="Show a persona's mutable state and memory", id_arg="PERSONA_ID",
         example="state get 5")
def state_get(ctx: Ctx) -> Any:
    p = get_or_404(ctx.session, Persona, need_id(ctx, "persona"), "persona", "persona list")
    return to_dict(get_state(ctx.session, p))


@command("state", "update", help="Update persona state (mood, interest_level 0-10, notes, memory_append)",
         id_arg="PERSONA_ID", payload="required", spec=STATE_SPEC,
         example="""state update 5 --json '{"mood": "tired", "interest_level": 4, "memory_append": {"note": "saw a similar app last week"}}'""")
def state_update(ctx: Ctx) -> Any:
    p = get_or_404(ctx.session, Persona, need_id(ctx, "persona"), "persona", "persona list")
    data = validate(ctx.payload, STATE_SPEC, partial=True)
    st = get_state(ctx.session, p)
    append = data.pop("memory_append", None)
    for k, v in data.items():
        setattr(st, k, v)
    if append is not None:
        st.memory = [*(st.memory or []), append]
    st.updated_at = utcnow()
    return to_dict(st)
