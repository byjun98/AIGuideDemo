from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "rag" / "data" / "rapi_dialogue.sqlite"
DEFAULT_MODEL = "qwen3-embedding:0.6b"
DEFAULT_HOST = "http://127.0.0.1:11434"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vectorize active RAG cards through Ollama /api/embed.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama embedding model name.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Ollama host URL.")
    parser.add_argument("--batch-size", type=int, default=8, help="Embedding batch size.")
    parser.add_argument("--limit", type=int, help="Maximum number of cards to vectorize.")
    parser.add_argument("--force", action="store_true", help="Recompute embeddings even when present.")
    parser.add_argument("--document-prefix", default="", help="Optional prefix added before each card text.")
    return parser.parse_args()


def embed_texts(host: str, model: str, texts: list[str]) -> list[list[float]]:
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
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
    if not isinstance(embeddings, list):
        raise RuntimeError(f"Unexpected Ollama response: {body}")
    return embeddings


def select_cards(conn: sqlite3.Connection, model: str, force: bool, limit: int | None) -> list[sqlite3.Row]:
    where = ["is_active = 1"]
    params: list[Any] = []
    if not force:
        where.append("(embedding_json IS NULL OR embedding_model IS NULL OR embedding_model != ?)")
        params.append(model)
    sql = f"""
      SELECT card_id, retrieval_text
      FROM rag_cards
      WHERE {' AND '.join(where)}
      ORDER BY updated_at ASC, card_id ASC
    """
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(sql, params))


def chunks(items: list[sqlite3.Row], batch_size: int) -> list[list[sqlite3.Row]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def main() -> None:
    args = parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        cards = select_cards(conn, args.model, args.force, args.limit)
        if not cards:
            print("vectorized_cards: 0")
            print("message: no active cards need embeddings")
            return

        total = 0
        for batch in chunks(cards, max(1, args.batch_size)):
            texts = [f"{args.document_prefix}{row['retrieval_text']}" for row in batch]
            embeddings = embed_texts(args.host, args.model, texts)
            if len(embeddings) != len(batch):
                raise RuntimeError(f"Embedding count mismatch: expected {len(batch)}, got {len(embeddings)}")

            for row, embedding in zip(batch, embeddings):
                dimension = len(embedding)
                conn.execute(
                    """
                    UPDATE rag_cards
                    SET embedding_model = ?,
                        embedding_dimension = ?,
                        embedding_json = ?,
                        updated_at = datetime('now')
                    WHERE card_id = ?
                    """,
                    (
                        args.model,
                        dimension,
                        json.dumps(embedding, separators=(",", ":")),
                        row["card_id"],
                    ),
                )
                total += 1
            conn.commit()
            print(f"vectorized_batch: {total}/{len(cards)}")

        print(f"vectorized_cards: {total}")
        print(f"embedding_model: {args.model}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
