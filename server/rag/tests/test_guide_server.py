import sys
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import guide_server as guide
from guide_common import canonical_state


def test_explicit_empty_visible_targets_stays_empty():
    state = canonical_state(guide.PACK, {"screen": "lobby", "unlocked_systems": [s["id"] for s in guide.PACK["systems"]], "visible_targets": []})
    assert state["visible_targets"] == []


def test_adapter_lookup_retries_after_failure(monkeypatch):
    monkeypatch.setattr(guide, "_loaded_ids", None)
    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(guide.requests, "get", fail)
    assert guide.loaded_adapter_ids() == []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return [{"id": 0}]
    monkeypatch.setattr(guide.requests, "get", lambda *a, **kw: Response())
    assert guide.loaded_adapter_ids() == [0]


@pytest.mark.parametrize("failure", [requests.ConnectionError("offline"), KeyError("missing model"), RuntimeError("missing adapter")])
def test_backend_failure_returns_replaced_200(monkeypatch, tmp_path, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(guide, "call_llm", fail)
    monkeypatch.setattr(guide, "LOG", tmp_path / "turns.jsonl")
    response = TestClient(guide.app).post("/guide/generate", json={"trigger": "player_utterance", "state": {}})
    assert response.status_code == 200
    assert response.json()["risk"] == "replaced"
    assert response.json()["debug"]["issues"]


def test_missing_character_returns_replaced(monkeypatch, tmp_path):
    monkeypatch.setattr(guide, "LOG", tmp_path / "turns.jsonl")
    response = TestClient(guide.app).post("/guide/generate", json={"trigger": "player_utterance", "state": {}, "character_id": "does_not_exist"})
    assert response.status_code == 200
    assert response.json()["risk"] == "replaced"


def test_parse_failure_is_replaced(monkeypatch):
    monkeypatch.setattr(guide, "call_llm", lambda *a, **kw: ("not json", 0, {}))
    response, _, _ = guide.run_turn("player_utterance", "hello", {})
    assert response["risk"] == "replaced"
    assert "parse_fail" in response["debug"]["issues"]


def test_invalid_target_is_removed():
    _, prof = guide.profile("rapi")
    response, issues = guide.validate({**guide.SILENT, "speak": True, "line": "확인합니다.", "ui_target": "bad", "action": "highlight"}, {"visible_targets": [], "unlocked_systems": []}, prof)
    assert response["ui_target"] is None
    assert response["action"] == "none"
    assert response["risk"] == "replaced"
    assert issues
