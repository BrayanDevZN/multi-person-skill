from conftest import persona_payload  # noqa: F401


def test_idea_crud_and_unique_name(cli):
    r = cli("idea", "create", name="Diet app", ad_copy="Lose weight")
    assert r.ok and r.data["id"] == 1
    dup = cli("idea", "create", name="diet APP")  # case-insensitive duplicate
    assert not dup.ok and "already exists" in dup.error and dup.hint
    assert cli("idea", "update", "1", description="x").data["description"] == "x"
    assert [i["name"] for i in cli("idea", "list", q="diet").data] == ["Diet app"]
    assert cli("idea", "list", q="zzz").data == []


def test_idea_update_rejects_name_collision(cli):
    cli("idea", "create", name="A")
    cli("idea", "create", name="B")
    assert not cli("idea", "update", "2", name="A").ok
    assert cli("idea", "update", "2", name="B").ok  # same name on itself is fine


def test_idea_delete_requires_confirm_and_cascades(seeded):
    seeded("research", "add", idea_id=1, topic="t", finding="f")
    seeded("run", "start", idea_id=1, persona_ids=[1])
    blocked = seeded("idea", "delete", "1")
    assert not blocked.ok and "--confirm" in blocked.hint
    assert seeded("idea", "delete", "1", "--confirm").ok
    assert seeded("research", "list").data == []
    assert seeded("run", "list").data == []
    assert seeded("persona", "list").data["total"] == 3  # personas survive


def test_research_batch_all_or_nothing(seeded):
    bad = seeded("research", "add", research=[
        {"idea_id": 1, "topic": "a", "finding": "ok"},
        {"idea_id": 99, "topic": "b", "finding": "orphan"},
    ])
    assert not bad.ok and "idea 99 not found" in bad.error
    assert seeded("research", "list").data == []
    good = seeded("research", "add", research=[{"idea_id": 1, "topic": "a", "finding": "x"},
                                               {"idea_id": 1, "topic": "b", "finding": "y"}])
    assert len(good.data["created"]) == 2
    assert len(seeded("research", "list", idea_id=1).data) == 2
