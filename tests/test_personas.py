from conftest import persona_payload


def ids(r):
    return [p["id"] for p in r.data["personas"]]


def test_create_single_list_and_wrapped(cli):
    assert cli("persona", "create", **persona_payload()).data["created"][0]["id"] == 1
    assert len(cli("persona", "create", personas=[persona_payload(name="B"), persona_payload(name="C")]).data["created"]) == 2
    assert cli("persona", "list").data["total"] == 3


def test_create_is_all_or_nothing(cli):
    r = cli("persona", "create", personas=[persona_payload(), persona_payload(name="Bad", age=5)])
    assert not r.ok and "age" in r.error
    assert cli("persona", "list").data["total"] == 0


def test_validation_errors(cli):
    assert "unknown field" in cli("persona", "create", **persona_payload(nickname="x")).error
    assert "missing required field 'name'" in cli("persona", "create", age=30).error
    assert "list of strings" in cli("persona", "create", **persona_payload(tags="lote-1")).error
    assert not cli("persona", "create", **persona_payload(age=True)).ok  # bool is not an int


def test_list_filters(seeded):
    assert ids(seeded("persona", "list", min_age=30)) == [1, 2]
    assert ids(seeded("persona", "list", max_age=30)) == [3]
    assert ids(seeded("persona", "list", gender="MALE")) == [2]
    assert ids(seeded("persona", "list", tag="lote-1")) == [1, 3]
    assert ids(seeded("persona", "list", segment="health scare")) == [2]
    assert ids(seeded("persona", "list", q="student")) == [3]
    assert ids(seeded("persona", "list", ids=[2, 3])) == [2, 3]
    assert ids(seeded("persona", "list", min_age=30, tag="lote-1")) == [1]
    assert seeded("persona", "list", "--limit", "1").data["personas"][0]["id"] == 1


def test_list_compact_vs_full(seeded):
    assert "bio" not in seeded("persona", "list").data["personas"][0]
    assert "bio" in seeded("persona", "list", "--full").data["personas"][0]


def test_list_by_reaction_history(seeded):
    seeded("run", "start", idea_id=1, persona_ids=[1, 2])
    seeded("reaction", "save", run_id=1, persona_id=1, action="like", sentiment="positive", purchase_intent=6)
    # persona 2 is still pending, so it has NOT reacted yet
    assert ids(seeded("persona", "list", reacted_idea_id=1)) == [1]
    assert ids(seeded("persona", "list", not_reacted_idea_id=1)) == [2, 3]


def test_search_flags_duplicates(seeded):
    dup = seeded("persona", "search", age=33, gender="female", occupation="Designer", segment="busy professional")
    top = dup.data["matches"][0]
    assert top["persona"]["id"] == 1 and top["likely_duplicate"]
    far = seeded("persona", "search", age=70, segment="retired hiker")
    assert far.data["matches"] == []
    assert not seeded("persona", "search", min_score=3).ok  # needs at least one profile field


def test_update_and_delete(seeded):
    assert seeded("persona", "update", "1", tags=["x"]).data["tags"] == ["x"]
    assert not seeded("persona", "update", "1", age=1).ok
    assert not seeded("persona", "delete", "1").ok
    assert seeded("persona", "delete", "1", "--confirm").ok
    assert not seeded("persona", "get", "1").ok


def test_state_update_and_memory_append(seeded):
    assert seeded("state", "get", "1").data["memory"] == []
    st = seeded("state", "update", "1", mood="tired", interest_level=4, memory_append={"note": "a"}).data
    assert st["mood"] == "tired" and st["memory"] == [{"note": "a"}]
    st = seeded("state", "update", "1", memory_append={"note": "b"}).data
    assert [m["note"] for m in st["memory"]] == ["a", "b"]
    assert not seeded("state", "update", "1", interest_level=11).ok


def test_age_filters_are_inclusive(seeded):
    # ages are 32 (Marina), 51 (Carlos), 22 (Ana)
    assert ids(seeded("persona", "list", min_age=32)) == [1, 2]
    assert ids(seeded("persona", "list", max_age=32)) == [1, 3]
    assert ids(seeded("persona", "list", min_age=32, max_age=32)) == [1]
