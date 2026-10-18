import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataset_splits import allocate, check_leakage
from import_character_dialogue import parse_dialogue


def row(line):
    return {"messages": [{}, {}, {"content": json.dumps({"line": line})}], "meta": {}}


def test_group_allocation_is_stable_and_has_three_partitions():
    assert allocate(list(range(30))) == allocate(list(reversed(range(30))))
    assert set(allocate(list(range(30))).values()) == {"train", "val", "test"}


def test_answer_leakage_is_rejected_but_empty_silence_is_shared():
    with pytest.raises(ValueError, match="Split leakage"):
        check_leakage({"train": [row("same")], "test": [row("same")]})
    check_leakage({"train": [row("")], "test": [row("")]})


def test_ner_filters_costumes_japanese_and_other_speakers(tmp_path):
    path = tmp_path / "dialogue.txt"
    path.write_text("[상호작용]\n- 상황: 기본 사복/韓\n네르: 「감사합니다.」\n- 상황: 한 때 한가닥\n네르: 「안녕하세요.」\n- 상황: 기본 사복/日\n네르: 「고마워요.」\n- 상황: 기본 사복\n에르핀: 「기다려요.」", encoding="utf-8")
    assert [r["line"] for r in parse_dialogue("ner", path)] == ["감사합니다."]


def test_arona_excludes_prana_and_deduplicates_groups(tmp_path):
    path = tmp_path / "dialogue.txt"
    path.write_text("## 책상\n상황: 입장 1\n아로나: (자기 이름), 안녕하세요.\n프라나: 아니에요.\n상황: 입장 2\n아로나: 반가워요.\n아로나: 반가워요.", encoding="utf-8")
    rows = parse_dialogue("arona", path)
    assert len(rows) == 2
    assert rows[0]["line"] == "선생님, 안녕하세요."
    assert rows[0]["official_group"] == rows[1]["official_group"]
