from fastapi.testclient import TestClient
import pytest

from rag.api import main as api


STATE = {"affection": 50, "affection_band": "trust", "scene": "gift_received"}


def test_search_returns_cards(monkeypatch):
    monkeypatch.setattr(api, "run_retrieval", lambda *a: ("query", [{"card_id": "one"}]))
    response = TestClient(api.app).post("/rag/search", json={"state": STATE})
    assert response.status_code == 200
    assert response.json()["retrieved_card_ids"] == ["one"]


@pytest.mark.parametrize("path", ["/rag/search", "/dialogue/generate"])
def test_invalid_state_is_422(path):
    assert TestClient(api.app).post(path, json={"state": {}}).status_code == 422


def test_cors_is_not_granted_to_foreign_origin(monkeypatch):
    monkeypatch.setattr(api, "run_retrieval", lambda *a: ("query", []))
    client = TestClient(api.app)
    headers = {"Origin": "https://untrusted.example"}
    response = client.post("/rag/search", json={"state": STATE}, headers=headers)
    assert "access-control-allow-origin" not in response.headers
    response = client.options("/dialogue/generate", headers={**headers, "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in response.headers


def test_model_failure_is_502(monkeypatch):
    monkeypatch.setattr(api, "run_retrieval", lambda *a: ("query", [{"card_id": "one"}]))
    def fail(*a, **kw):
        raise RuntimeError("Ollama offline")
    monkeypatch.setattr(api, "best_of_n_generate", fail)
    response = TestClient(api.app).post("/dialogue/generate", json={"state": STATE})
    assert response.status_code == 502
    assert "offline" in response.json()["detail"]


def test_embedding_failure_is_502(monkeypatch):
    def fail(*a, **kw):
        raise RuntimeError("Ollama offline")
    monkeypatch.setattr(api, "embed_text", fail)
    response = TestClient(api.app).post("/rag/search", json={"state": STATE})
    assert response.status_code == 502


def test_generate_persists_valid_output(monkeypatch, tmp_path):
    import sqlite3
    schema = api.__file__
    from pathlib import Path
    db = tmp_path / "api.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript((Path(schema).resolve().parents[1] / "schema/dialogue_schema.sql").read_text(encoding="utf-8"))
    monkeypatch.setattr(api, "DEFAULT_DB", db)
    monkeypatch.setattr(api, "run_retrieval", lambda *a: ("query", [{"card_id": "one"}]))
    output = {"line": "지휘관, 감사합니다.", "emotion": "neutral", "voice_tag": "calm_brief", "motion": "idle", "risk": "safe"}
    monkeypatch.setattr(api, "best_of_n_generate", lambda *a, **kw: {"output": output, "style_score": 1, "novelty_score": 1, "spoiler_score": 1, "checks": []})
    response = TestClient(api.app).post("/dialogue/generate", json={"state": STATE})
    assert response.status_code == 200
    assert response.json()["output"]["line"] == output["line"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM generated_dialogue_cache").fetchone()[0] == 1
