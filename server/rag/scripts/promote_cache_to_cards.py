from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "rag" / "data" / "rapi_dialogue.sqlite"
DEFAULT_SOURCE_ID = "synthetic_promoted_cache"
DEFAULT_SOURCE_WEIGHT = 0.6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--character-id", default="rapi")
    parser.add_argument("--limit", type=int, default=10, help="Max number of cache rows to promote.")
    parser.add_argument(
        "--require-accepted",
        action="store_true",
        help="Only promote rows with accepted=1. Off by default since the current generator does not auto-set this flag.",
    )
    parser.add_argument(
        "--allowed-risk",
        default="safe",
        help="Comma list of risk values to accept (e.g. 'safe' or 'safe,needs_review').",
    )
    parser.add_argument("--min-style-score", type=float, default=None)
    parser.add_argument("--min-novelty-score", type=float, default=None)
    parser.add_argument("--max-spoiler-score", type=float, default=None)
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--source-weight", type=float, default=DEFAULT_SOURCE_WEIGHT)
    parser.add_argument(
        "--inherit-gates",
        action="store_true",
        help="Copy state_json.story_flags into rag_card_story_gates as required gates.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print candidates without writing.")
    parser.add_argument(
        "--vectorize",
        action="store_true",
        help="After promoting, invoke scripts/vectorize_cards.py to fill embeddings.",
    )
    parser.add_argument(
        "--auto-mark-accepted",
        action="store_true",
        help="Before selecting candidates, set accepted=1 on cache rows that satisfy the same risk/score filters. Useful for batch curation when --require-accepted is also set.",
    )
    return parser.parse_args()


def ensure_source_document(conn: sqlite3.Connection, source_id: str) -> None:
    conn.execute(
        """
        INSERT INTO source_documents (
          source_id, title, source_type, url, language,
          rights_scope, reliability_tier, notes
        ) VALUES (?, ?, 'manual_note', NULL, 'ko', 'private_reference', 'C', ?)
        ON CONFLICT(source_id) DO NOTHING
        """,
        (
            source_id,
            "캐시 승격 합성 대사",
            "generated_dialogue_cache 에서 품질 기준을 통과한 합성 대사를 RAG 카드로 승격할 때 부여하는 출처. canon_tier=synthetic.",
        ),
    )


def build_filter_clauses(args: argparse.Namespace, *, require_accepted: bool) -> tuple[list[str], list[Any]]:
    risks = [item.strip() for item in args.allowed_risk.split(",") if item.strip()]
    placeholders = ",".join("?" for _ in risks)
    where = [
        f"c.risk IN ({placeholders})",
        "c.character_id = ?",
        "TRIM(c.line) <> ''",
    ]
    params: list[Any] = [*risks, args.character_id]
    if require_accepted:
        where.append("c.accepted = 1")
    if args.min_style_score is not None:
        where.append("c.style_score IS NOT NULL AND c.style_score >= ?")
        params.append(args.min_style_score)
    if args.min_novelty_score is not None:
        where.append("c.novelty_score IS NOT NULL AND c.novelty_score >= ?")
        params.append(args.min_novelty_score)
    if args.max_spoiler_score is not None:
        where.append("(c.spoiler_score IS NULL OR c.spoiler_score <= ?)")
        params.append(args.max_spoiler_score)
    return where, params


def auto_mark_accepted(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    where, params = build_filter_clauses(args, require_accepted=False)
    where.append("c.accepted = 0")
    sql = f"""
      UPDATE generated_dialogue_cache
         SET accepted = 1
       WHERE generated_id IN (
         SELECT c.generated_id FROM generated_dialogue_cache c
         WHERE {' AND '.join(where)}
       )
    """
    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor.rowcount or 0


def select_candidates(conn: sqlite3.Connection, args: argparse.Namespace) -> list[sqlite3.Row]:
    where, params = build_filter_clauses(args, require_accepted=args.require_accepted)
    where.append("NOT EXISTS (SELECT 1 FROM rag_cards rc WHERE rc.card_id = 'synth_' || c.generated_id)")

    sql = f"""
      SELECT c.generated_id, c.character_id, c.state_json, c.retrieved_card_ids_json,
             c.line, c.emotion_tag, c.voice_tag, c.motion_tag, c.risk,
             c.style_score, c.novelty_score, c.spoiler_score, c.accepted,
             c.model_name, c.created_at
      FROM generated_dialogue_cache c
      WHERE {' AND '.join(where)}
      ORDER BY
        c.accepted DESC,
        COALESCE(c.style_score, 0) DESC,
        c.created_at DESC
      LIMIT ?
    """
    params.append(args.limit)
    return list(conn.execute(sql, params))


def load_state(state_json: str) -> dict:
    try:
        data = json.loads(state_json) if state_json else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def affection_band_for(conn: sqlite3.Connection, affection: int | None) -> str | None:
    if affection is None:
        return None
    row = conn.execute(
        "SELECT band_id FROM affection_bands WHERE ? BETWEEN min_affection AND max_affection ORDER BY min_affection LIMIT 1",
        (affection,),
    ).fetchone()
    return row[0] if row else None


def existing_line_id_by_hash(conn: sqlite3.Connection, sha: str) -> str | None:
    row = conn.execute(
        "SELECT line_id FROM raw_dialogue_lines WHERE raw_text_sha256 = ? LIMIT 1",
        (sha,),
    ).fetchone()
    return row[0] if row else None


def get_dialogue_function_for_scene(scene_id: str | None) -> str | None:
    mapping = {
        "gift_received": "gift_response",
        "advise_session": "advise_answer",
        "after_battle_win": "battle_result",
        "after_battle_hard": "battle_result",
        "lobby_morning": "greeting",
        "lobby_evening": "greeting",
        "late_night": "greeting",
        "event_idle": "idle",
    }
    return mapping.get(scene_id) if scene_id else None


def build_retrieval_text(line: str, state: dict, scene_id: str | None, affection_band: str | None) -> str:
    parts = ["[합성 캐시 카드]"]
    if scene_id:
        parts.append(f"scene={scene_id}")
    if affection_band:
        parts.append(f"band={affection_band}")
    action = state.get("player_recent_action")
    if action:
        parts.append(f"action={action}")
    header = " ".join(parts)
    return f"{header}\n{line.strip()}"


def known_flag_ids(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT flag_id FROM story_flags")}


def promote_one(
    conn: sqlite3.Connection,
    cache_row: sqlite3.Row,
    args: argparse.Namespace,
    flag_whitelist: set[str],
) -> dict:
    state = load_state(cache_row["state_json"])
    scene_id = state.get("scene")
    affection = state.get("affection") if isinstance(state.get("affection"), int) else None
    affection_band = state.get("affection_band") or affection_band_for(conn, affection)

    line = cache_row["line"].strip()
    sha = hashlib.sha256(line.encode("utf-8")).hexdigest()

    line_id = existing_line_id_by_hash(conn, sha)
    if not line_id:
        line_id = f"synth_line_{uuid.uuid4().hex[:12]}"
        short_excerpt = line[:60]
        conn.execute(
            """
            INSERT INTO raw_dialogue_lines (
              line_id, character_id, speaker, raw_text, raw_text_sha256, short_excerpt,
              language, source_id, source_location, scene_id, affection_band_id,
              min_affection, max_affection, spoiler_level, canon_tier,
              emotion_tag, voice_tag, motion_tag, dialogue_function,
              summary_kr, voice_features_kr, forbidden_notes,
              is_verbatim_allowed, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 'ko', ?, ?, ?, ?, ?, ?, 0, 'synthetic', ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                line_id,
                cache_row["character_id"],
                state.get("character_id", cache_row["character_id"]),
                line,
                sha,
                short_excerpt,
                args.source_id,
                f"generated_dialogue_cache/{cache_row['generated_id']}",
                scene_id,
                affection_band,
                affection,
                affection,
                cache_row["emotion_tag"],
                cache_row["voice_tag"],
                cache_row["motion_tag"],
                get_dialogue_function_for_scene(scene_id),
                f"승격된 합성 대사. risk={cache_row['risk']}, accepted={cache_row['accepted']}.",
                "",
                "원문 그대로 노출 금지. 검색 컨텍스트에서만 사용.",
                f"promoted from {cache_row['generated_id']}",
            ),
        )

    card_id = f"synth_{cache_row['generated_id']}"
    facts = {
        "source": "generated_dialogue_cache",
        "generated_id": cache_row["generated_id"],
        "model": cache_row["model_name"],
        "scene": scene_id,
        "affection": affection,
        "affection_band": affection_band,
        "player_recent_action": state.get("player_recent_action"),
        "promoted_at": "now",
    }
    voice_rules = {
        "origin": "synthetic_promoted",
        "note": "캐시에서 승격된 카드. 원문이 아니라 모델 생성 결과이므로 가중치를 낮춰 사용한다.",
    }
    forbidden = {
        "notes": "이 카드 자체를 다시 합성에 그대로 복제하지 않는다. 변주만 허용.",
    }

    conn.execute(
        """
        INSERT INTO rag_cards (
          card_id, line_id, character_id, retrieval_text, facts_json, voice_rules_json,
          forbidden_json, scene_id, affection_band_id, min_affection, max_affection,
          spoiler_level, emotion_tag, voice_tag, motion_tag, dialogue_function,
          embedding_model, embedding_dimension, embedding_json,
          source_weight, is_active, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, NULL, NULL, NULL, ?, 1, datetime('now'))
        """,
        (
            card_id,
            line_id,
            cache_row["character_id"],
            build_retrieval_text(line, state, scene_id, affection_band),
            json.dumps(facts, ensure_ascii=False),
            json.dumps(voice_rules, ensure_ascii=False),
            json.dumps(forbidden, ensure_ascii=False),
            scene_id,
            affection_band,
            affection,
            affection,
            cache_row["emotion_tag"],
            cache_row["voice_tag"],
            cache_row["motion_tag"],
            get_dialogue_function_for_scene(scene_id),
            args.source_weight,
        ),
    )

    if args.inherit_gates:
        flags = state.get("story_flags") or []
        if isinstance(flags, list):
            for flag_id in flags:
                if isinstance(flag_id, str) and flag_id in flag_whitelist:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO rag_card_story_gates (card_id, flag_id, gate_type)
                        VALUES (?, ?, 'required')
                        """,
                        (card_id, flag_id),
                    )

    return {
        "generated_id": cache_row["generated_id"],
        "card_id": card_id,
        "line_id": line_id,
        "scene_id": scene_id,
        "affection_band_id": affection_band,
        "line_preview": line[:80],
    }


def main() -> int:
    args = parse_args()
    if not args.db.exists():
        print(f"db not found: {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        if args.auto_mark_accepted and not args.dry_run:
            marked = auto_mark_accepted(conn, args)
            print(f"auto_marked_accepted_rows: {marked}")
        elif args.auto_mark_accepted and args.dry_run:
            where, params = build_filter_clauses(args, require_accepted=False)
            where.append("c.accepted = 0")
            sql = f"SELECT COUNT(*) FROM generated_dialogue_cache c WHERE {' AND '.join(where)}"
            count = conn.execute(sql, params).fetchone()[0]
            print(f"would_auto_mark_accepted_rows: {count}")

        candidates = select_candidates(conn, args)
        print(f"candidates_found: {len(candidates)}")

        if args.dry_run or not candidates:
            for row in candidates:
                state = load_state(row["state_json"])
                print(
                    json.dumps(
                        {
                            "generated_id": row["generated_id"],
                            "risk": row["risk"],
                            "accepted": row["accepted"],
                            "scene": state.get("scene"),
                            "affection": state.get("affection"),
                            "line_preview": row["line"].strip()[:80],
                        },
                        ensure_ascii=False,
                    )
                )
            return 0

        ensure_source_document(conn, args.source_id)
        flag_whitelist = known_flag_ids(conn)

        promoted: list[dict] = []
        for row in candidates:
            try:
                result = promote_one(conn, row, args, flag_whitelist)
                promoted.append(result)
            except sqlite3.IntegrityError as exc:
                print(f"skip {row['generated_id']}: {exc}", file=sys.stderr)
        conn.commit()

        for entry in promoted:
            print(json.dumps(entry, ensure_ascii=False))
        print(f"promoted_count: {len(promoted)}")

    finally:
        conn.close()

    if args.vectorize and not args.dry_run:
        cmd = [
            sys.executable,
            str(ROOT / "rag" / "scripts" / "vectorize_cards.py"),
            "--db",
            str(args.db),
        ]
        print(f"running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False)
        return result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
