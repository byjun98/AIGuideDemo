import json
import sqlite3
from pathlib import Path

def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def ensure_card_references(conn: sqlite3.Connection, card: dict) -> None:
    for key, table, column in (("scene_id", "scenes", "scene_id"),
                               ("dialogue_function", "dialogue_functions", "function_id"),
                               ("emotion_tag", "emotion_tags", "emotion_tag"),
                               ("voice_tag", "voice_tags", "voice_tag"),
                               ("motion_tag", "motion_tags", "motion_tag")):
        value = card.get(key)
        if value is not None:
            if key == "voice_tag":
                conn.execute("INSERT OR IGNORE INTO voice_tags (voice_tag, label_ko, prompt_hint) VALUES (?, ?, '')", (value, value))
            else:
                conn.execute(f"INSERT OR IGNORE INTO {table} ({column}, label_ko) VALUES (?, ?)", (value, value))

def upsert_scene(conn: sqlite3.Connection, scene_id: str, label_ko: str, description: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO scenes (scene_id, label_ko, description) VALUES (?, ?, ?)",
        (scene_id, label_ko, description),
    )

def upsert_dialogue_function(conn: sqlite3.Connection, function_id: str, label_ko: str, description: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO dialogue_functions (function_id, label_ko, description) VALUES (?, ?, ?)",
        (function_id, label_ko, description),
    )

def upsert_story_flag(conn: sqlite3.Connection, flag: dict) -> None:
    label = flag.get("label_ko") or flag.get("description", "").strip()[:60]
    if not label:
        label = flag["flag_id"].replace("_", " ")
    conn.execute(
        """
        INSERT INTO story_flags (flag_id, label_ko, description, spoiler_level)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(flag_id) DO UPDATE SET
            label_ko = excluded.label_ko,
            description = excluded.description,
            spoiler_level = excluded.spoiler_level
        """,
        (
            flag["flag_id"],
            label,
            flag.get("description", ""),
            int(flag.get("spoiler_level", 0)),
        ),
    )

def upsert_card(conn: sqlite3.Connection, card: dict) -> None:
    ensure_card_references(conn, card)

    def js(value):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

    conn.execute(
        """
        INSERT INTO rag_cards (
            card_id, character_id, retrieval_text, facts_json, voice_rules_json,
            forbidden_json, scene_id, affection_band_id, min_affection, max_affection,
            spoiler_level, emotion_tag, voice_tag, motion_tag, dialogue_function,
            source_weight, is_active, embedding_model, embedding_json
        ) VALUES (
            :card_id, :character_id, :retrieval_text, :facts_json, :voice_rules_json,
            :forbidden_json, :scene_id, :affection_band_id, :min_affection, :max_affection,
            :spoiler_level, :emotion_tag, :voice_tag, :motion_tag, :dialogue_function,
            :source_weight, :is_active, :embedding_model, :embedding_json
        )
        ON CONFLICT(card_id) DO UPDATE SET
            retrieval_text    = excluded.retrieval_text,
            facts_json        = excluded.facts_json,
            voice_rules_json  = excluded.voice_rules_json,
            forbidden_json    = excluded.forbidden_json,
            scene_id          = excluded.scene_id,
            affection_band_id = excluded.affection_band_id,
            min_affection     = excluded.min_affection,
            max_affection     = excluded.max_affection,
            spoiler_level     = excluded.spoiler_level,
            emotion_tag       = excluded.emotion_tag,
            voice_tag         = excluded.voice_tag,
            motion_tag        = excluded.motion_tag,
            dialogue_function = excluded.dialogue_function,
            source_weight     = excluded.source_weight,
            is_active         = excluded.is_active,
            embedding_model   = NULL,
            embedding_dimension = NULL,
            embedding_json    = NULL,
            updated_at        = datetime('now')
        """,
        {
            "card_id":           card["card_id"],
            "character_id":      card.get("character_id", "rapi"),
            "retrieval_text":    card["retrieval_text"],
            "facts_json":        js(card.get("facts_json") or card.get("facts")) or "{}",
            "voice_rules_json":  js(card.get("voice_rules_json") or card.get("voice_rules")) or "{}",
            "forbidden_json":    js(card.get("forbidden_json") or card.get("forbidden")) or "{}",
            "scene_id":          card.get("scene_id"),
            "affection_band_id": card.get("affection_band_id"),
            "min_affection":     card.get("min_affection"),
            "max_affection":     card.get("max_affection"),
            "spoiler_level":     card.get("spoiler_level", 0),
            "emotion_tag":       card.get("emotion_tag"),
            "voice_tag":         card.get("voice_tag"),
            "motion_tag":        card.get("motion_tag"),
            "dialogue_function": card.get("dialogue_function"),
            "source_weight":     card.get("source_weight", 0.95),
            "is_active":         int(card.get("is_active", 1)),
            "embedding_model":   card.get("embedding_model"),
            "embedding_json":    card.get("embedding_json"),
        },
    )

def upsert_story_gate(conn: sqlite3.Connection, card_id, gate=None, gate_type=None) -> None:
    if isinstance(card_id, dict):
        data = card_id
    elif isinstance(gate, dict):
        data = {"card_id": card_id, **gate}
    else:
        data = {"card_id": card_id, "flag_id": gate, "gate_type": gate_type}
    flag = data["flag_id"]
    conn.execute("INSERT OR IGNORE INTO story_flags (flag_id, label_ko) VALUES (?, ?)", (flag, flag))
    conn.execute("INSERT OR IGNORE INTO rag_card_story_gates (card_id, flag_id, gate_type) VALUES (?, ?, ?)",
                 (data["card_id"], flag, data.get("gate_type") or "required"))

