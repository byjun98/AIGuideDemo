import json

import pytest

from suggestion_checks import check_suggestions, suggestion_questions


def test_suggestion_overlap_is_rejected_for_all_slots():
    bank = {'normal_questions': ['{system} 위치는?'], 'locked_question': '{system} 해금은?',
            'spoiler_question': '{marker} 이야기는?', 'oos_questions': ['세금은?'],
            'fallback_question': '자기소개는?', 'questions': [{'question': '쉬고 싶어?'}]}
    questions = suggestion_questions({'systems': [{'name': '메뉴'}]}, {'chapters': [{'spoiler_markers': ['비밀']}]}, bank)
    assert questions == {'메뉴 위치는?', '메뉴 해금은?', '비밀 이야기는?', '세금은?', '자기소개는?', '쉬고 싶어?'}
    for question in questions:
        row = {'messages': [{}, {'content': json.dumps({'player_input': question})}]}
        with pytest.raises(ValueError, match='suggestions overlap training'):
            check_suggestions([row], questions)
    check_suggestions([{'messages': [{}, {'content': '{"player_input":"다른 질문"}'}]}], questions)
