from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from rag.scripts.generate_dialogue import evaluate_output

DEFAULT_DB = ROOT / "rag" / "data" / "rapi_dialogue.sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--character-id", default=None, help="Optional character filter.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--only-null",
        action="store_true",
        help="Only update rows where any score column is NULL. Default: update all rows.",
    )
    parser.add_argument(
        "--update-risk",
        action="store_true",
        help="Overwrite the stored risk with the freshly evaluated risk. Default: leave risk untouched.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def select_rows(conn: sqlite3.Connection, args: argparse.Namespace) -> list[sqlite3.Row]:
    where: list[str] = []
    params: list[Any] = []
    if args.only_null:
        where.append("(style_score IS NULL OR novelty_score IS NULL OR spoiler_score IS NULL)")
    if args.character_id:
        where.append("character_id = ?")
        params.append(args.character_id)
    sql = """
      SELECT generated_id, character_id, state_json, line,
             emotion_tag, voice_tag, motion_tag, memory_update_json, risk,
             style_score, novelty_score, spoiler_score
      FROM generated_dialogue_cache
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at ASC"
    if args.limit:
        sql += " LIMIT ?"
        params.append(args.limit)
    return list(conn.execute(sql, params))


def reconstruct_state(state_json: str) -> dict:
    try:
        data = json.loads(state_json) if state_json else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def reconstruct_output(row: sqlite3.Row) -> dict:
    memory_update: Any = None
    if row["memory_update_json"]:
        try:
            memory_update = json.loads(row["memory_update_json"])
        except json.JSONDecodeError:
            memory_update = None
    return {
        "line": row["line"] or "",
        "emotion": row["emotion_tag"] or "neutral",
        "voice_tag": row["voice_tag"] or "calm_brief",
        "motion": row["motion_tag"] or "idle",
        "memory_update": memory_update,
        "risk": row["risk"] or "safe",
    }


def main() -> int:
    args = parse_args()
    if not args.db.exists():
        print(f"db not found: {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    try:
        rows = select_rows(conn, args)
        print(f"rows_to_process: {len(rows)}")
        if not rows:
            return 0

        updated = 0
        risk_changes = 0
        summary_buckets = {"safe": 0, "needs_review": 0, "blocked": 0}

        for row in rows:
            state = reconstruct_state(row["state_json"])
            output = reconstruct_output(row)
            evaluation = evaluate_output(state, [], output)

            new_style = evaluation["style_score"]
            new_novelty = evaluation["novelty_score"]
            new_spoiler = evaluation["spoiler_score"]
            new_risk = evaluation["output"]["risk"]
            summary_buckets[new_risk] = summary_buckets.get(new_risk, 0) + 1

            if new_risk != (row["risk"] or "safe"):
                risk_changes += 1

            if args.dry_run:
                continue

            if args.update_risk:
                conn.execute(
                    """
                    UPDATE generated_dialogue_cache
                       SET style_score = ?, novelty_score = ?, spoiler_score = ?, risk = ?
                     WHERE generated_id = ?
                    """,
                    (new_style, new_novelty, new_spoiler, new_risk, row["generated_id"]),
                )
            else:
                conn.execute(
                    """
                    UPDATE generated_dialogue_cache
                       SET style_score = ?, novelty_score = ?, spoiler_score = ?
                     WHERE generated_id = ?
                    """,
                    (new_style, new_novelty, new_spoiler, row["generated_id"]),
                )
            updated += 1

        if not args.dry_run:
            conn.commit()
            print(f"updated_rows: {updated}")
            if args.update_risk:
                print(f"risk_changed_rows: {risk_changes}")
        else:
            print(f"would_update_rows: {len(rows)}")
            print(f"would_change_risk_rows (if --update-risk): {risk_changes}")

        print(f"risk_distribution_after: {summary_buckets}")

    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
