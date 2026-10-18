import json

import guide_server as guide


def test_sampling_keeps_guidance_and_locked_questions_low():
    _, prof = guide.profile('arona')
    prof = {**prof, 'generation': {'diversity_enabled': True}}
    state = {'unlocked_systems': [], 'story_chapter': 0}
    assert guide.sampling_policy('mission_failed', '안녕', state, prof, guide.PACK) == (0.3, 1)
    assert guide.sampling_policy('player_utterance', '업무는 언제 열려?', state, prof, guide.PACK)[1] == 1
    assert guide.sampling_policy('player_utterance', '프라나 이야기', state, prof, guide.PACK) == (0.3, 1)
    assert guide.sampling_policy('player_utterance', '안녕', state, prof, guide.PACK) == (0.75, 2)


def test_runtime_chooses_valid_novel_candidate_without_changing_prompt(monkeypatch):
    _, prof = guide.profile('arona')
    monkeypatch.setattr(guide, 'profile', lambda _: ('unchanged system', {**prof, 'generation': {'diversity_enabled': True}}))
    monkeypatch.setattr(guide, '_recent_lines', {})
    old, new = '선생님, 오늘도 반가워요!', '선생님, 잠시 쉬면서 이야기해요.'
    guide.remember_line('arona', old)
    lines = iter([old, new])
    calls = []
    def fake(model, system, user, schema, temperature, seed, **kwargs):
        calls.append((system, user, temperature))
        return json.dumps({**guide.SILENT, 'speak': True, 'line': next(lines)}, ensure_ascii=False), .01, {}
    monkeypatch.setattr(guide, 'call_llm', fake)
    response, _, _ = guide.run_turn('player_utterance', '안녕', {}, character_id='arona', runtime_diversity=True)
    assert response['line'] == new
    assert response['risk'] == 'safe'
    assert len(calls) == 2 and calls[0] == calls[1]
    assert response['debug']['candidates'] == 2


def test_candidate_timeout_budget_and_history_bound(monkeypatch):
    monkeypatch.setattr(guide, '_recent_lines', {})
    for i in range(15):
        guide.remember_line('rapi', str(i))
    assert list(guide._recent_lines['rapi']) == [str(i) for i in range(5, 15)]
    assert not guide._recent_lines.get('arona')


def test_invalid_second_candidate_never_replaces_valid_first(monkeypatch):
    _, prof = guide.profile('arona')
    monkeypatch.setattr(guide, 'profile', lambda _: ('system', {**prof, 'generation': {'diversity_enabled': True}}))
    monkeypatch.setattr(guide, '_recent_lines', {})
    lines = iter(['선생님, 반가워요!', '프라나가 기다려요.'])
    def fake(*args, **kwargs):
        return json.dumps({**guide.SILENT, 'speak': True, 'line': next(lines)}, ensure_ascii=False), .01, {}
    monkeypatch.setattr(guide, 'call_llm', fake)
    response, _, _ = guide.run_turn('player_utterance', '안녕', {}, character_id='arona', runtime_diversity=True)
    assert response['line'] == '선생님, 반가워요!'
    assert response['risk'] == 'safe'


def test_second_request_failure_keeps_valid_first(monkeypatch):
    import requests
    _, prof = guide.profile('arona')
    monkeypatch.setattr(guide, 'profile', lambda _: ('system', {**prof, 'generation': {'diversity_enabled': True}}))
    def fake(*args, **kwargs):
        if 'timeout' in kwargs:
            assert 0 < kwargs['timeout'] <= 30
            raise requests.Timeout('second candidate exhausted budget')
        return json.dumps({**guide.SILENT, 'speak': True, 'line': '선생님, 반가워요!'}, ensure_ascii=False), .01, {}
    monkeypatch.setattr(guide, 'call_llm', fake)
    response, _, _ = guide.run_turn('player_utterance', '안녕', {}, character_id='arona', runtime_diversity=True)
    assert response['risk'] == 'safe'
