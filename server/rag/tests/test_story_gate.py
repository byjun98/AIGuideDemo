import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import guide_server as guide
from guide_common import canonical_state, retrieve


STORY = {"chapters": [{"index": 0, "name": "Start", "spoiler_markers": []}, {"index": 1, "name": "Secret", "spoiler_markers": ["Future secret"]}]}


def test_canonical_story_clamps_and_names_chapter():
    state = canonical_state(guide.PACK, {"story_chapter": 50, "story_name": "forged"}, STORY)
    assert state["story_chapter"] == 1
    assert state["story_name"] == "Secret"


def test_future_cards_and_affection_locked_cards_are_not_retrieved():
    pack = {**guide.PACK, "cards": [
        {"id": "future", "system": None, "text": "Future secret", "story_chapter": 1},
        {"id": "letter", "system": None, "text": "Personal letter", "min_affection": 100},
        {"id": "profile", "system": None, "text": "Profile", "story_chapter": 0},
    ]}
    assert [c["id"] for c in retrieve(pack, {"story_chapter": 0, "affection": 50}, "")] == ["profile"]
    assert len(retrieve(pack, {"story_chapter": 1, "affection": 100}, "")) == 3


def test_game_query_prefers_relevant_game_card_over_unrelated_character_card():
    system = guide.PACK["systems"][0]
    pack = {**guide.PACK, "cards": [
        {"id": "character", "system": None, "text": "캐릭터의 기본 프로필"},
        {"id": "game", "system": system["id"], "text": "버튼을 눌러 시작합니다."},
    ]}
    state = {"unlocked_systems": [system["id"]], "story_chapter": 0, "affection": 50}
    assert retrieve(pack, state, system["name"], k=1)[0]["id"] == "game"


def test_story_spoiler_is_replaced_before_unlock():
    _, prof = guide.profile("arona")
    prof = {**prof, "story": STORY}
    output = {**guide.SILENT, "speak": True, "line": "Future secret"}
    response, issues = guide.validate(output, {"story_chapter": 0}, prof)
    assert response["refusal"] == "spoiler"
    assert response["risk"] == "replaced"
    assert "Future secret" not in response["line"]
    assert issues
    response, _ = guide.validate(output, {"story_chapter": 1}, prof)
    assert response["line"] == output["line"]
