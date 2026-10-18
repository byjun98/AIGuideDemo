from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "rag" / "data" / "rapi_dialogue.sqlite"
DEFAULT_SCHEMA = ROOT / "rag" / "schema" / "dialogue_schema.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the Rapi dialogue RAG SQLite database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="SQL schema path.")
    parser.add_argument("--import-csv", type=Path, help="Optional raw dialogue CSV to import.")
    return parser.parse_args()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean(value: str | None) -> str:
    return (value or "").strip()


def int_or_none(value: str | None) -> int | None:
    value = clean(value)
    return int(value) if value else None


def int_or_default(value: str | None, default: int) -> int:
    value = clean(value)
    return int(value) if value else default


def split_flags(value: str | None) -> list[str]:
    value = clean(value)
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def is_placeholder(raw_text: str) -> bool:
    stripped = raw_text.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def ensure_optional_dimension(conn: sqlite3.Connection, table: str, column: str, key_column: str, key: str, label: str) -> None:
    exists = conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (key,)).fetchone()
    if exists:
        return
    if table == "scenes":
        conn.execute("INSERT INTO scenes (scene_id, label_ko) VALUES (?, ?)", (key, label))
    elif table == "emotion_tags":
        conn.execute("INSERT INTO emotion_tags (emotion_tag, label_ko) VALUES (?, ?)", (key, label))
    elif table == "voice_tags":
        conn.execute("INSERT INTO voice_tags (voice_tag, label_ko, prompt_hint) VALUES (?, ?, ?)", (key, label, label))
    elif table == "motion_tags":
        conn.execute("INSERT INTO motion_tags (motion_tag, label_ko) VALUES (?, ?)", (key, label))
    elif table == "dialogue_functions":
        conn.execute("INSERT INTO dialogue_functions (function_id, label_ko) VALUES (?, ?)", (key, label))


def upsert_source(conn: sqlite3.Connection, row: dict[str, str]) -> str:
    source_id = clean(row.get("source_key")) or "manual_rapi_private"
    conn.execute(
        """
        INSERT INTO source_documents (
          source_id, title, source_type, url, language, rights_scope, reliability_tier, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
          title = excluded.title,
          source_type = excluded.source_type,
          url = excluded.url,
          language = excluded.language,
          rights_scope = excluded.rights_scope,
          reliability_tier = excluded.reliability_tier
        """,
        (
            source_id,
            clean(row.get("source_title")) or source_id,
            clean(row.get("source_type")) or "private_transcript",
            clean(row.get("source_url")) or None,
            clean(row.get("language")) or "ko",
            clean(row.get("rights_scope")) or "private_reference",
            clean(row.get("reliability_tier")) or "A",
            "Imported from CSV",
        ),
    )
    return source_id


def make_retrieval_text(row: dict[str, str]) -> str:
    parts = [
        "캐릭터: 라피",
        f"장면: {clean(row.get('scene_id'))}",
        f"호감도 단계: {clean(row.get('affection_band_id'))}",
        f"감정 태그: {clean(row.get('emotion_tag'))}",
        f"목소리 태그: {clean(row.get('voice_tag'))}",
        f"대사 기능: {clean(row.get('dialogue_function'))}",
        f"원문 일부: {clean(row.get('short_excerpt'))}",
        f"요약: {clean(row.get('summary_kr'))}",
        f"말투 특징: {clean(row.get('voice_features_kr'))}",
        f"금지/주의: {clean(row.get('forbidden_notes'))}",
    ]
    return "\n".join(part for part in parts if not part.endswith(": "))


def import_raw_dialogue_csv(conn: sqlite3.Connection, csv_path: Path) -> tuple[int, int]:
    imported = 0
    skipped = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            raw_text = clean(row.get("raw_text"))
            if not raw_text or is_placeholder(raw_text):
                skipped += 1
                continue

            source_id = upsert_source(conn, row)
            line_id = clean(row.get("line_id")) or f"rapi_{text_hash(raw_text)[:16]}"
            character_id = clean(row.get("character_id")) or "rapi"
            scene_id = clean(row.get("scene_id")) or None
            emotion_tag = clean(row.get("emotion_tag")) or None
            voice_tag = clean(row.get("voice_tag")) or None
            motion_tag = clean(row.get("motion_tag")) or None
            function_id = clean(row.get("dialogue_function")) or None

            if scene_id:
                ensure_optional_dimension(conn, "scenes", "scene_id", "scene_id", scene_id, scene_id)
            if emotion_tag:
                ensure_optional_dimension(conn, "emotion_tags", "emotion_tag", "emotion_tag", emotion_tag, emotion_tag)
            if voice_tag:
                ensure_optional_dimension(conn, "voice_tags", "voice_tag", "voice_tag", voice_tag, voice_tag)
            if motion_tag:
                ensure_optional_dimension(conn, "motion_tags", "motion_tag", "motion_tag", motion_tag, motion_tag)
            if function_id:
                ensure_optional_dimension(conn, "dialogue_functions", "function_id", "function_id", function_id, function_id)

            short_excerpt = clean(row.get("short_excerpt")) or raw_text[:64]
            conn.execute(
                """
                INSERT INTO raw_dialogue_lines (
                  line_id, character_id, speaker, raw_text, raw_text_sha256, short_excerpt,
                  language, source_id, source_location, scene_id, affection_band_id,
                  min_affection, max_affection, spoiler_level, canon_tier, emotion_tag,
                  voice_tag, motion_tag, dialogue_function, summary_kr, voice_features_kr,
                  forbidden_notes, is_verbatim_allowed, notes, updated_at
                ) VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')
                )
                ON CONFLICT(line_id) DO UPDATE SET
                  raw_text = excluded.raw_text,
                  raw_text_sha256 = excluded.raw_text_sha256,
                  short_excerpt = excluded.short_excerpt,
                  source_id = excluded.source_id,
                  source_location = excluded.source_location,
                  scene_id = excluded.scene_id,
                  affection_band_id = excluded.affection_band_id,
                  min_affection = excluded.min_affection,
                  max_affection = excluded.max_affection,
                  spoiler_level = excluded.spoiler_level,
                  canon_tier = excluded.canon_tier,
                  emotion_tag = excluded.emotion_tag,
                  voice_tag = excluded.voice_tag,
                  motion_tag = excluded.motion_tag,
                  dialogue_function = excluded.dialogue_function,
                  summary_kr = excluded.summary_kr,
                  voice_features_kr = excluded.voice_features_kr,
                  forbidden_notes = excluded.forbidden_notes,
                  is_verbatim_allowed = excluded.is_verbatim_allowed,
                  notes = excluded.notes,
                  updated_at = datetime('now')
                """,
                (
                    line_id,
                    character_id,
                    clean(row.get("speaker")) or "라피",
                    raw_text,
                    text_hash(raw_text),
                    short_excerpt,
                    clean(row.get("language")) or "ko",
                    source_id,
                    clean(row.get("source_location")),
                    scene_id,
                    clean(row.get("affection_band_id")) or None,
                    int_or_none(row.get("min_affection")),
                    int_or_none(row.get("max_affection")),
                    int_or_default(row.get("spoiler_level"), 0),
                    clean(row.get("canon_tier")) or "canon",
                    emotion_tag,
                    voice_tag,
                    motion_tag,
                    function_id,
                    clean(row.get("summary_kr")),
                    clean(row.get("voice_features_kr")),
                    clean(row.get("forbidden_notes")),
                    int_or_default(row.get("is_verbatim_allowed"), 0),
                    clean(row.get("notes")),
                ),
            )

            conn.execute("DELETE FROM line_story_gates WHERE line_id = ?", (line_id,))
            conn.execute("DELETE FROM rag_card_story_gates WHERE card_id = ?", (f"card_{line_id}",))
            required_flags = split_flags(row.get("required_flags"))
            forbidden_flags = split_flags(row.get("forbidden_flags"))
            for gate_type, flags in (("required", required_flags), ("forbidden", forbidden_flags)):
                for flag_id in flags:
                    conn.execute(
                        "INSERT OR IGNORE INTO story_flags (flag_id, label_ko, spoiler_level) VALUES (?, ?, ?)",
                        (flag_id, flag_id, int_or_default(row.get("spoiler_level"), 0)),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO line_story_gates (line_id, flag_id, gate_type) VALUES (?, ?, ?)",
                        (line_id, flag_id, gate_type),
                    )

            facts_json = json.dumps(
                {
                    "summary_kr": clean(row.get("summary_kr")),
                    "short_excerpt": short_excerpt,
                    "source_id": source_id,
                    "source_location": clean(row.get("source_location")),
                    "required_flags": required_flags,
                    "forbidden_flags": forbidden_flags,
                },
                ensure_ascii=False,
            )
            voice_rules_json = json.dumps(
                {
                    "voice_features_kr": clean(row.get("voice_features_kr")),
                    "voice_tag": voice_tag,
                    "emotion_tag": emotion_tag,
                    "motion_tag": motion_tag,
                },
                ensure_ascii=False,
            )
            forbidden_json = json.dumps(
                {
                    "forbidden_notes": clean(row.get("forbidden_notes")),
                    "is_verbatim_allowed": bool(int_or_default(row.get("is_verbatim_allowed"), 0)),
                },
                ensure_ascii=False,
            )
            conn.execute(
                """
                INSERT INTO rag_cards (
                  card_id, line_id, character_id, retrieval_text, facts_json, voice_rules_json,
                  forbidden_json, scene_id, affection_band_id, min_affection, max_affection,
                  spoiler_level, emotion_tag, voice_tag, motion_tag, dialogue_function, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(card_id) DO UPDATE SET
                  retrieval_text = excluded.retrieval_text,
                  facts_json = excluded.facts_json,
                  voice_rules_json = excluded.voice_rules_json,
                  forbidden_json = excluded.forbidden_json,
                  scene_id = excluded.scene_id,
                  affection_band_id = excluded.affection_band_id,
                  min_affection = excluded.min_affection,
                  max_affection = excluded.max_affection,
                  spoiler_level = excluded.spoiler_level,
                  emotion_tag = excluded.emotion_tag,
                  voice_tag = excluded.voice_tag,
                  motion_tag = excluded.motion_tag,
                  dialogue_function = excluded.dialogue_function,
                  updated_at = datetime('now')
                """,
                (
                    f"card_{line_id}",
                    line_id,
                    character_id,
                    make_retrieval_text(row),
                    facts_json,
                    voice_rules_json,
                    forbidden_json,
                    scene_id,
                    clean(row.get("affection_band_id")) or None,
                    int_or_none(row.get("min_affection")),
                    int_or_none(row.get("max_affection")),
                    int_or_default(row.get("spoiler_level"), 0),
                    emotion_tag,
                    voice_tag,
                    motion_tag,
                    function_id,
                ),
            )

            for gate_type, flags in (("required", required_flags), ("forbidden", forbidden_flags)):
                for flag_id in flags:
                    conn.execute(
                        "INSERT OR IGNORE INTO rag_card_story_gates (card_id, flag_id, gate_type) VALUES (?, ?, ?)",
                        (f"card_{line_id}", flag_id, gate_type),
                    )

            imported += 1

    conn.commit()
    return imported, skipped


def main() -> None:
    args = parse_args()
    conn = connect(args.db)
    try:
        init_schema(conn, args.schema)
        print(f"initialized: {args.db}")
        if args.import_csv:
            imported, skipped = import_raw_dialogue_csv(conn, args.import_csv)
            print(f"imported_rows: {imported}")
            print(f"skipped_placeholder_or_empty_rows: {skipped}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
