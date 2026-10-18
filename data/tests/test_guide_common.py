import random

from guide_common import canonical_state, load_pack, load_profile, query_terms, retrieve, unknown_ui_mentions
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]


def _setup(character, pack_name, chapter):
    pack = load_pack(DATA / pack_name)
    _, prof = load_profile(DATA / f"character_{character}.json")
    pack = {**pack, "cards": pack["cards"] + prof["story_cards"]}
    raw = {"tutorial_step": pack["tutorial_steps"][0]["id"], "unlocked_systems": [s["id"] for s in pack["systems"][:2]],
           "screen": "lobby", "story_chapter": chapter, "affection": 50}
    return pack, prof, canonical_state(pack, raw, prof["story"])


def test_query_terms_strip_korean_particles():
    stems = {w: st for w, st in query_terms("프라나에 관한 이야기를 레드 후드를 계승한다는 건")}
    assert "프라나" in stems["프라나에"]
    assert "후드" in stems["후드를"]
    assert "계승" in stems["계승한다는"]


def test_story_card_is_retrieved_from_particle_question():
    cases = [("arona", "pack_bluearchive.json", "프라나에 관한 이야기를 지금 들을 수 있을까?", 4, "arona_story_prana"),
             ("rapi", "pack_nikke.json", "레드 후드를 계승한다는 건 무슨 뜻이야?", 34, "rapi_story_inheritance")]
    for character, pack_name, question, chapter, expected in cases:
        pack, prof, state = _setup(character, pack_name, chapter)
        for seed in range(5):
            cards = retrieve(pack, state, question, rng=random.Random(seed), story=prof["story"])
            assert expected in [c["id"] for c in cards], (character, seed, cards)
            assert all(set(c) == {"id", "text", "chapter"} for c in cards)


def test_story_gate_still_hides_future_cards():
    pack, prof, state = _setup("arona", "pack_bluearchive.json", 3)
    cards = retrieve(pack, state, "프라나에 관한 이야기를 지금 들을 수 있을까?", story=prof["story"])
    assert all(c["chapter"] <= 3 for c in cards)
    assert "arona_story_prana" not in [c["id"] for c in cards]


def test_generic_nouns_are_not_menu_names():
    pack = load_pack(DATA / "pack_nikke.json")
    assert unknown_ui_mentions(pack, "지휘관, 방주 이용은 로비에서 시작합니다.") == []
    assert unknown_ui_mentions(pack, "전초기지 사용은 로비에서 가능합니다. 시작 버튼을 누르십시오.") == []
    assert unknown_ui_mentions(pack, "세금 버튼을 누르십시오.") == ["세금 버튼"]
