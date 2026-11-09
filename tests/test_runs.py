import pytest


def react(cli, run_id, persona_id, action="like", sentiment="positive", intent=5, **extra):
    return cli("reaction", "save", run_id=run_id, persona_id=persona_id, action=action,
               sentiment=sentiment, purchase_intent=intent, **extra)


def test_run_start_creates_pending_reactions(seeded):
    r = seeded("run", "start", idea_id=1, persona_ids=[1, 2, 2, 3], notes="first")
    assert r.data == {"run_id": 1, "idea": "Diet app", "pending": 3, "already_reacted_to_this_idea": []}
    st = seeded("run", "status", "1").data
    assert st["counts"] == {"planned": 3, "ok": 0, "failed": 0, "pending": 3}
    assert st["pending_persona_ids"] == [1, 2, 3]


def test_run_start_errors(seeded):
    assert "idea 9 not found" in seeded("run", "start", idea_id=9, persona_ids=[1]).error
    r = seeded("run", "start", idea_id=1, persona_ids=[1, 77, 88])
    assert not r.ok and "[77, 88]" in r.error
    assert seeded("run", "list").data == []  # nothing half-created
    assert not seeded("run", "start", idea_id=1, persona_ids=[]).ok


def test_full_lifecycle_with_partial_failure_and_resume(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2, 3])
    assert react(seeded, 1, 1, "convert", "positive", 9).ok
    assert seeded("reaction", "save", run_id=1, persona_id=2, status="failed", error="bad json").ok
    # persona 3 is never simulated -> stays pending
    fin = seeded("run", "finish", "1").data
    assert fin["status"] == "partial" and fin["counts"] == {"planned": 3, "ok": 1, "failed": 1, "pending": 1}

    todo = seeded("run", "resume", "1").data["todo"]
    assert [t["persona_id"] for t in todo] == [2, 3]  # failed became pending again
    assert seeded("run", "status", "1").data["run"]["status"] == "running"

    react(seeded, 1, 2, "reject", "negative", 1)
    react(seeded, 1, 3, "ignore", "neutral", 2)
    fin = seeded("run", "finish", "1").data
    assert fin["status"] == "completed" and fin["counts"]["ok"] == 3


def test_reaction_save_is_idempotent(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1])
    react(seeded, 1, 1, "like", "positive", 5, comment="first")
    react(seeded, 1, 1, "reject", "negative", 1, comment="changed my mind")
    rows = seeded("reaction", "list", run_id=1).data
    assert rows["total"] == 1 and rows["reactions"][0]["action"] == "reject"
    assert seeded("persona", "get", "1").data["state"]["memory"].__len__() == 1  # memory replaced, not duplicated


def test_failed_then_ok_clears_error(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1])
    seeded("reaction", "save", run_id=1, persona_id=1, status="failed", error="boom")
    react(seeded, 1, 1)
    r = seeded("reaction", "get", "1").data
    assert r["status"] == "ok" and r["error"] is None


def test_reaction_validation(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1])
    assert "requires" in seeded("reaction", "save", run_id=1, persona_id=1, action="like").error
    assert "requires 'error'" in seeded("reaction", "save", run_id=1, persona_id=1, status="failed").error
    assert not react(seeded, 1, 1, intent=11).ok
    assert not react(seeded, 1, 1, intent=-1).ok
    assert "one of" in react(seeded, 1, 1, action="buy").error
    assert not react(seeded, 99, 1).ok and not react(seeded, 1, 99).ok


def test_reaction_batch_is_atomic(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2])
    good = dict(run_id=1, persona_id=1, action="like", sentiment="positive", purchase_intent=5)
    bad = dict(run_id=1, persona_id=2, action="like", sentiment="positive", purchase_intent=99)
    assert not seeded("reaction", "save", reactions=[good, bad]).ok
    assert seeded("run", "status", "1").data["counts"]["ok"] == 0
    assert len(seeded("reaction", "save", reactions=[good, {**bad, "purchase_intent": 3}]).data["saved"]) == 2


def test_memory_feeds_later_runs(seeded):
    seeded("idea", "create", name="Gym app")
    seeded("run", "start", idea_id=1, persona_ids=[1])
    react(seeded, 1, 1, "convert", "positive", 8)
    r2 = seeded("run", "start", idea_id=2, persona_ids=[1])
    react(seeded, r2.data["run_id"], 1, "ignore", "neutral", 2)
    mem = seeded("state", "get", "1").data["memory"]
    assert [m["idea"] for m in mem] == ["Diet app", "Gym app"]
    hist = seeded("persona", "get", "1").data["history"]
    assert [h["action"] for h in hist] == ["convert", "ignore"]


def test_run_start_reports_prior_reactions_to_same_idea(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2])
    react(seeded, 1, 1)
    again = seeded("run", "start", idea_id=1, persona_ids=[1, 2, 3])
    assert again.data["already_reacted_to_this_idea"] == [1]


def test_reaction_list_filters_and_trace_visibility(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2, 3])
    react(seeded, 1, 1, "convert", "positive", 9, react_trace="Thought: yes")
    react(seeded, 1, 2, "reject", "negative", 1, react_trace="Thought: no")
    react(seeded, 1, 3, "ignore", "neutral", 3)
    names = lambda r: [x["persona_name"] for x in r.data["reactions"]]  # noqa: E731
    assert names(seeded("reaction", "list", sentiment="negative")) == ["Carlos"]
    assert names(seeded("reaction", "list", min_intent=3)) == ["Marina", "Ana"]
    assert names(seeded("reaction", "list", action="convert", idea_id=1)) == ["Marina"]
    assert "react_trace" not in seeded("reaction", "list").data["reactions"][0]
    assert seeded("reaction", "list", "--full").data["reactions"][0]["react_trace"] == "Thought: yes"
    assert seeded("reaction", "get", "2").data["react_trace"] == "Thought: no"


def test_report_aggregates(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2, 3])
    react(seeded, 1, 1, "convert", "positive", 9, objections=["Price"])
    react(seeded, 1, 2, "reject", "negative", 1, objections=["price ", "no trust"])
    seeded("reaction", "save", run_id=1, persona_id=3, status="failed", error="x")
    rep = seeded("report", "run", "1").data
    assert rep["counts"] == {"planned": 3, "ok": 2, "failed": 1, "pending": 0}
    assert rep["conversion_rate"] == 0.5 and rep["engagement_rate"] == 1.0
    assert rep["avg_purchase_intent"] == 5.0
    assert rep["top_objections"][0] == {"objection": "price", "count": 2}  # normalised
    assert rep["by_segment"]["busy professional"]["conversions"] == 1
    assert set(rep["by_age_group"]) == {"25-34", "45-54"}
    assert rep["highlights"]["most_interested"][0]["name"] == "Marina"
    assert rep["failed"] == [{"persona_id": 3, "error": "x"}]


def test_report_on_run_without_results_does_not_crash(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1])
    rep = seeded("report", "run", "1").data
    assert rep["conversion_rate"] is None and rep["avg_purchase_intent"] is None
    assert rep["pending_persona_ids"] == [1]


@pytest.mark.parametrize("age,group", [(17 + 0, "<18"), (24, "18-24"), (34, "25-34"), (44, "35-44"), (54, "45-54"), (80, "55+")])
def test_age_groups(age, group):
    from socialsim.commands.runs import _age_group
    if age >= 13:  # personas must be 13+, but the bucket function covers all ages
        assert _age_group(age) == group


def test_deleting_persona_or_run_cascades(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2])
    react(seeded, 1, 1)
    react(seeded, 1, 2)
    seeded("persona", "delete", "1", "--confirm")
    assert [r["persona_id"] for r in seeded("reaction", "list").data["reactions"]] == [2]
    seeded("run", "delete", "1", "--confirm")
    assert seeded("reaction", "list").data["total"] == 0


def test_memory_is_capped(seeded):
    from socialsim.commands.runs import MEMORY_CAP
    for i in range(MEMORY_CAP + 5):
        seeded("run", "start", idea_id=1, persona_ids=[1])
        react(seeded, i + 1, 1)
    assert len(seeded("state", "get", "1").data["memory"]) == MEMORY_CAP
