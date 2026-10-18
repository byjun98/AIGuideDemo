from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from rag.scripts.generate_dialogue import (
    DEFAULT_AUTO_ACCEPT_MIN_NOVELTY,
    DEFAULT_AUTO_ACCEPT_MIN_SPOILER,
    DEFAULT_AUTO_ACCEPT_MIN_STYLE,
    DEFAULT_BEST_OF,
    DEFAULT_CHAT_MODEL,
    DEFAULT_DB,
    DEFAULT_EMBED_MODEL,
    DEFAULT_HOST,
    DEFAULT_TEMPERATURE_STEP,
    best_of_n_generate,
    cache_generation,
    embed_text,
    insert_qa_checks,
    log_retrieval,
    make_query,
    retrieve_cards,
    should_auto_accept,
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


SERVER_AUTO_ACCEPT_DEFAULT = _env_flag("RAPI_API_AUTO_ACCEPT")
SERVER_AUTO_ACCEPT_MIN_STYLE = _env_float("RAPI_API_AUTO_ACCEPT_MIN_STYLE", DEFAULT_AUTO_ACCEPT_MIN_STYLE)
SERVER_AUTO_ACCEPT_MIN_NOVELTY = _env_float("RAPI_API_AUTO_ACCEPT_MIN_NOVELTY", DEFAULT_AUTO_ACCEPT_MIN_NOVELTY)
SERVER_AUTO_ACCEPT_MIN_SPOILER = _env_float("RAPI_API_AUTO_ACCEPT_MIN_SPOILER", DEFAULT_AUTO_ACCEPT_MIN_SPOILER)


class RuntimeState(BaseModel):
    model_config = ConfigDict(extra="allow")

    character_id: str = "rapi"
    affection: int = Field(ge=0, le=100)
    affection_band: str
    story_flags: list[str] = Field(default_factory=list)
    scene: str
    player_recent_action: str | None = None
    time_of_day: str | None = None
    place: str | None = None
    recent_lines: list[str] = Field(default_factory=list)
    recent_card_ids: list[str] = Field(
        default_factory=list,
        description="Card IDs returned in the last ~10 turns. Used by retrieval to penalise repeated cards and reduce monotony.",
    )
    tone: str = "subculture_romantic_but_wholesome"
    max_spoiler_level: int = Field(default=0, ge=0, le=5)
    output_language: str = "ko"


class DialogueGenerateRequest(BaseModel):
    state: RuntimeState
    query: str | None = None
    limit: int = Field(default=5, ge=1, le=12)
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.5,
        description="Base temperature; with best_of > 1 each attempt uses base + idx * temperature_step.",
    )
    best_of: int = Field(
        default=DEFAULT_BEST_OF,
        ge=1,
        le=8,
        description="Number of temperature-jittered candidates to generate per request. Best by novelty * style * spoiler wins. 1 disables best-of-N.",
    )
    temperature_step: float = Field(
        default=DEFAULT_TEMPERATURE_STEP,
        ge=0.0,
        le=0.5,
        description="Per-attempt temperature increment for best-of-N jitter.",
    )
    accept_cache: bool = False
    auto_accept_on_safe: bool | None = Field(
        default=None,
        description="If True (or env RAPI_API_AUTO_ACCEPT=1), set accepted=1 when risk=safe and scores clear thresholds. None falls back to env default.",
    )
    include_cards: bool = True
    embed_model: str = DEFAULT_EMBED_MODEL
    chat_model: str = DEFAULT_CHAT_MODEL


class RagSearchRequest(BaseModel):
    state: RuntimeState
    query: str | None = None
    limit: int = Field(default=5, ge=1, le=20)
    embed_model: str = DEFAULT_EMBED_MODEL


class DialogueOutput(BaseModel):
    line: str
    emotion: str
    voice_tag: str
    motion: str
    memory_update: Any = None
    risk: str


class DialogueGenerateResponse(BaseModel):
    generated_id: str
    retrieved_card_ids: list[str]
    output: DialogueOutput
    cards: list[dict[str, Any]] | None = None
    accepted: bool = False
    auto_accepted: bool = False
    style_score: float | None = None
    novelty_score: float | None = None
    spoiler_score: float | None = None


class RagSearchResponse(BaseModel):
    query: str
    retrieved_card_ids: list[str]
    cards: list[dict[str, Any]]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rapi Dialogue RAG API",
        version="0.1.0",
        description="Local Unity-facing dialogue API backed by SQLite RAG, Ollama embeddings, and gemma4:e4b.",
    )
    return app


app = create_app()


def connect_db() -> sqlite3.Connection:
    if not DEFAULT_DB.exists():
        raise HTTPException(status_code=500, detail=f"Database not found: {DEFAULT_DB}")
    conn = sqlite3.connect(DEFAULT_DB)
    conn.row_factory = sqlite3.Row
    return conn


def state_to_dict(state: RuntimeState) -> dict[str, Any]:
    return state.model_dump(mode="json")


def get_ollama_tags() -> dict[str, Any]:
    request = urllib.request.Request(f"{DEFAULT_HOST.rstrip('/')}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama is not reachable: {exc}") from exc


def run_retrieval(state: dict[str, Any], query: str | None, embed_model: str, limit: int) -> tuple[str, list[dict[str, Any]]]:
    retrieval_query = make_query(state, query)
    try:
        query_vector = embed_text(DEFAULT_HOST, embed_model, retrieval_query)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    candidate_card_ids: list[str] = []
    conn = connect_db()
    try:
        cards = retrieve_cards(conn, state, query_vector, embed_model, limit, candidate_card_ids)
        if cards:
            log_retrieval(conn, state, retrieval_query, candidate_card_ids, cards, embed_model)
    finally:
        conn.close()

    if not cards:
        raise HTTPException(
            status_code=404,
            detail="No RAG cards passed metadata/story gates. Check scene, affection band, story flags, or max_spoiler_level.",
        )
    return retrieval_query, cards


@app.get("/health")
def health() -> dict[str, Any]:
    tags = get_ollama_tags()
    conn = connect_db()
    try:
        rag_cards = conn.execute("SELECT COUNT(*) FROM rag_cards").fetchone()[0]
        embedded_cards = conn.execute("SELECT COUNT(*) FROM rag_cards WHERE embedding_json IS NOT NULL").fetchone()[0]
        generated = conn.execute("SELECT COUNT(*) FROM generated_dialogue_cache").fetchone()[0]
    finally:
        conn.close()

    return {
        "status": "ok",
        "db": str(DEFAULT_DB),
        "ollama_host": DEFAULT_HOST,
        "models": [model.get("name") for model in tags.get("models", [])],
        "rag_cards": rag_cards,
        "embedded_cards": embedded_cards,
        "generated_cache": generated,
    }


@app.get("/schema/tags")
def schema_tags() -> dict[str, Any]:
    conn = connect_db()
    try:
        tables = {
            "affection_bands": "SELECT * FROM affection_bands ORDER BY min_affection",
            "story_flags": "SELECT * FROM story_flags ORDER BY spoiler_level, flag_id",
            "scenes": "SELECT * FROM scenes ORDER BY scene_id",
            "emotion_tags": "SELECT * FROM emotion_tags ORDER BY emotion_tag",
            "voice_tags": "SELECT * FROM voice_tags ORDER BY voice_tag",
            "motion_tags": "SELECT * FROM motion_tags ORDER BY motion_tag",
            "dialogue_functions": "SELECT * FROM dialogue_functions ORDER BY function_id",
        }
        return {
            name: [dict(row) for row in conn.execute(sql).fetchall()]
            for name, sql in tables.items()
        }
    finally:
        conn.close()


@app.post("/rag/search", response_model=RagSearchResponse)
def rag_search(request: RagSearchRequest) -> RagSearchResponse:
    state = state_to_dict(request.state)
    query, cards = run_retrieval(state, request.query, request.embed_model, request.limit)
    return RagSearchResponse(
        query=query,
        retrieved_card_ids=[card["card_id"] for card in cards],
        cards=cards,
    )


@app.post("/dialogue/generate", response_model=DialogueGenerateResponse)
def generate_dialogue(request: DialogueGenerateRequest) -> DialogueGenerateResponse:
    state = state_to_dict(request.state)
    query, cards = run_retrieval(state, request.query, request.embed_model, request.limit)

    try:
        evaluation = best_of_n_generate(
            DEFAULT_HOST,
            request.chat_model,
            state,
            cards,
            query_text=query,
            n=request.best_of,
            base_temperature=request.temperature,
            temperature_step=request.temperature_step,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    conn = connect_db()
    try:
        output = evaluation["output"]
        auto_accept_enabled = (
            request.auto_accept_on_safe
            if request.auto_accept_on_safe is not None
            else SERVER_AUTO_ACCEPT_DEFAULT
        )
        auto_accepted = bool(
            auto_accept_enabled
            and should_auto_accept(
                evaluation,
                min_style=SERVER_AUTO_ACCEPT_MIN_STYLE,
                min_novelty=SERVER_AUTO_ACCEPT_MIN_NOVELTY,
                min_spoiler=SERVER_AUTO_ACCEPT_MIN_SPOILER,
            )
        )
        accepted = bool(request.accept_cache or auto_accepted)
        generated_id = cache_generation(
            conn,
            state,
            cards,
            output,
            request.chat_model,
            accepted,
            evaluation,
        )
        insert_qa_checks(conn, generated_id, evaluation["checks"])
    finally:
        conn.close()

    return DialogueGenerateResponse(
        generated_id=generated_id,
        retrieved_card_ids=[card["card_id"] for card in cards],
        output=DialogueOutput(
            line=str(output.get("line", "")),
            emotion=str(output.get("emotion", "neutral")),
            voice_tag=str(output.get("voice_tag", "calm_brief")),
            motion=str(output.get("motion", "idle")),
            memory_update=output.get("memory_update"),
            risk=str(output.get("risk", "needs_review")),
        ),
        cards=cards if request.include_cards else None,
        accepted=accepted,
        auto_accepted=auto_accepted,
        style_score=evaluation.get("style_score"),
        novelty_score=evaluation.get("novelty_score"),
        spoiler_score=evaluation.get("spoiler_score"),
    )
