from import_character_lore import chapter_for, make_cards


def test_future_story_and_uncertainty_survive_import(tmp_path):
    source = tmp_path / "history.txt"
    source.write_text("[1부 최종편]\n- 프라나에 관한 해석은 위키의 추정이며 확정된 사실과 구별해야 합니다.\n", encoding="utf-8")
    card = make_cards("arona", source, True)[0]
    assert card["story_chapter"] == 4
    assert "uncertain" in card["tags"]
    assert "추정" in card["text"]
    assert card["training_eligible"] is False


def test_ner_past_and_later_season_are_separate():
    assert chapter_for("ner", "현재", "목수를 꿈꾸던 과거 이야기") == 1
    assert chapter_for("ner", "현재", "시즌 3 이후 선배 사제 복귀") == 2


def test_letter_summary_keeps_affection_unlock(tmp_path):
    source = tmp_path / 'settings.txt'
    source.write_text('- 친밀 30 편지에는 교주에게 전하는 감사와 앞으로의 기대가 담겨 있습니다.\n', encoding='utf-8')
    assert make_cards('ner', source)[0]['min_affection'] == 100
