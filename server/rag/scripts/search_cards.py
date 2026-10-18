from __future__ import annotations

import argparse
import json
import math
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "rag" / "data" / "rapi_dialogue.sqlite"
DEFAULT_MODEL = "qwen3-embedding:0.6b"
DEFAULT_HOST = "http://127.0.0.1:11434"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search embedded RAG cards with metadata gates.")
    parser.add_argument("query", help="Korean semantic query.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama embedding model name.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Ollama host URL.")
    parser.add_argument("--character-id", default="rapi", help="Character id filter.")
    parser.add_argument("--scene", help="Scene id filter.")
    parser.add_argument("--affection-band", help="Affection band id filter.")
    parser.add_argument("--affection", type=int, help="Numeric affection filter.")
    parser.add_argument("--flags", default="", help="Pipe-separated story flags, e.g. chapter_04_cleared|first_advise_seen")
    parser.add_argument("--max-spoiler", type=int, default=0, help="Maximum allowed spoiler level.")
    parser.add_argument("--limit", type=int, default=5, help="Number of results to print.")
    parser.add_argument("--query-prefix", default="", help="Optional prefix added before the query.")
    return parser.parse_args()


def embed_text(host: str, model: str, text: str) -> list[float]:
    payload = json.dumps({"model": model, "input": text}).encode("utf-8")
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama embed request failed: {exc}") from exc

    embeddings = body.get("embeddings")
    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
        return embeddings[0]
    raise RuntimeError(f"Unexpected Ollama response: {body}")


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def parse_flags(raw: str) -> set[str]:
    return {item.strip() for item in raw.split("|") if item.strip()}


def gates_allow(conn: sqlite3.Connection, card_id: str, flags: set[str]) -> bool:
    rows = conn.execute(
        "SELECT flag_id, gate_type FROM rag_card_story_gates WHERE card_id = ?",
        (card_id,),
    ).fetchall()
    required = {row["flag_id"] for row in rows if row["gate_type"] == "required"}
    forbidden = {row["flag_id"] for row in rows if row["gate_type"] == "forbidden"}
    return required.issubset(flags) and not forbidden.intersection(flags)


def metadata_allow(row: sqlite3.Row, args: argparse.Namespace, flags: set[str]) -> bool:
    if row["spoiler_level"] is not None and row["spoiler_level"] > args.max_spoiler:
        return False
    if args.scene and row["scene_id"] and row["scene_id"] != args.scene:
        return False
    if args.affection_band and row["affection_band_id"] and row["affection_band_id"] != args.affection_band:
        return False
    if args.affection is not None:
        if row["min_affection"] is not None and args.affection < row["min_affection"]:
            return False
        if row["max_affection"] is not None and args.affection > row["max_affection"]:
            return False
    return True


def main() -> None:
    args = parse_args()
    flags = parse_flags(args.flags)
    query_vector = embed_text(args.host, args.model, f"{args.query_prefix}{args.query}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT card_id, retrieval_text, scene_id, affection_band_id, min_affection,
                   max_affection, spoiler_level, emotion_tag, voice_tag, motion_tag,
                   dialogue_function, source_weight, embedding_json
            FROM rag_cards
            WHERE character_id = ?
              AND is_active = 1
              AND embedding_model = ?
              AND embedding_json IS NOT NULL
            """,
            (args.character_id, args.model),
        ).fetchall()

        scored = []
        for row in rows:
            if not metadata_allow(row, args, flags):
                continue
            if not gates_allow(conn, row["card_id"], flags):
                continue
            card_vector = json.loads(row["embedding_json"])
            score = cosine(query_vector, card_vector) * float(row["source_weight"] or 1.0)
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        for rank, (score, row) in enumerate(scored[: args.limit], start=1):
            preview = row["retrieval_text"].replace("\n", " ")[:180]
            print(
                json.dumps(
                    {
                        "rank": rank,
                        "score": round(score, 6),
                        "card_id": row["card_id"],
                        "scene_id": row["scene_id"],
                        "affection_band_id": row["affection_band_id"],
                        "spoiler_level": row["spoiler_level"],
                        "emotion_tag": row["emotion_tag"],
                        "voice_tag": row["voice_tag"],
                        "motion_tag": row["motion_tag"],
                        "dialogue_function": row["dialogue_function"],
                        "preview": preview,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
