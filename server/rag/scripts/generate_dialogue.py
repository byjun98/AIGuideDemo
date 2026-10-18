from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import uuid
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "rag" / "data" / "rapi_dialogue.sqlite"
DEFAULT_STATE = ROOT / "rag" / "examples" / "rapi_state_example.json"
DEFAULT_EMBED_MODEL = "qwen3-embedding:0.6b"
DEFAULT_CHAT_MODEL = "gemma4:e4b"
DEFAULT_HOST = "http://127.0.0.1:11434"
ALLOWED_EMOTIONS = {
    "neutral",
    "soft_smile",
    "gentle",
    "embarrassed",
    "worried",
    "relieved",
    "stern",
    "determined",
}
ALLOWED_VOICE_TAGS = {
    "calm_brief",
    "warm_reserved",
    "mission_report",
    "protective_soft",
    "rare_tease",
    "vulnerable_short",
    "legacy_resolved",
    "direct_affection",
    "red_hood_combat",
    "event_flirt",
    "event_comedy_direct",
}
ALLOWED_MOTIONS = {
    "idle",
    "nod",
    "look_away",
    "soft_smile",
    "salute",
    "hand_to_chest",
    "battle_ready",
}
LINE_FIELD_ALIASES = ("line", "dialogue", "text", "response", "message")
EMOTION_ALIASES = {
    "calm": "neutral",
    "calm_brief": "neutral",
    "stable": "neutral",
    "reserved": "neutral",
    "soft": "gentle",
    "warm": "gentle",
    "smile": "soft_smile",
    "soft smile": "soft_smile",
    "happy": "soft_smile",
    "concerned": "worried",
    "anxious": "worried",
    "relief": "relieved",
    "firm": "determined",
    "resolve": "determined",
    "serious": "stern",
    "침착": "neutral",
    "차분": "neutral",
    "차분함": "neutral",
    "안정": "neutral",
    "안정적": "neutral",
    "부드러움": "gentle",
    "다정": "gentle",
    "걱정": "worried",
    "염려": "worried",
    "안심": "relieved",
    "안도": "relieved",
    "안도감": "relieved",
    "결의": "determined",
    "단호": "determined",
    "진지": "stern",
}
VOICE_TAG_ALIASES = {
    "reserved": "warm_reserved",
    "warm": "warm_reserved",
    "mission": "mission_report",
    "protective": "protective_soft",
    "vulnerable": "vulnerable_short",
    "legacy": "legacy_resolved",
}
MOTION_ALIASES = {
    "none": "idle",
    "stand": "idle",
    "standing": "idle",
    "smile": "soft_smile",
    "soft smile": "soft_smile",
    "hand_on_chest": "hand_to_chest",
    "hand to chest": "hand_to_chest",
    "ready": "battle_ready",
}
LOCKED_RED_HOOD_TERMS = ("레드 후드", "레드후드", "Red Hood", "라피: 레드 후드", "코드: 레드 후드")
STYLE_BREAK_TERMS_HARD = ("지휘관님", "선생님", "ㅇㅋ", "개쩐다", "꺄")
STYLE_BREAK_TERMS_SOFT = ("해요", "돼요", "같아요", "네요", "몰랐어요", "헤헤", "ㅋㅋ", "ㅎㅎ")
STYLE_BREAK_TERMS = STYLE_BREAK_TERMS_HARD + STYLE_BREAK_TERMS_SOFT
ROMANCE_ESCALATION_TERMS = ("사랑", "연인", "키스", "결혼")
RELATIONSHIP_STATE_KEYS = (
    "bond_rank",
    "bond_exp",
    "bond_cap",
    "limit_break",
    "daily_advise_remaining",
    "quick_advise_unlocked",
    "advise_seen_count",
    "advise_collection_count",
    "gift_type",
    "gift_rarity",
    "gift_match_type",
    "favorite_item_phase",
    "collection_item_phase",
)
FEWSHOT_VOICE_EXAMPLES = (
    {
        "voice_tag": "calm_brief",
        "emotion": "neutral",
        "motion": "nod",
        "scene": "lobby_morning",
        "line": "지휘관, 보고드릴 사항은 따로 없습니다. 다음 명령을 기다리겠습니다.",
    },
    {
        "voice_tag": "mission_report",
        "emotion": "determined",
        "motion": "salute",
        "scene": "battle_start",
        "line": "지휘관, 적 위치 확인을 마쳤습니다. 분대 정렬 뒤 진입하겠습니다.",
    },
    {
        "voice_tag": "warm_reserved",
        "emotion": "soft_smile",
        "motion": "nod",
        "scene": "gift_received",
        "line": "지휘관, 신경 써 주셔서 감사합니다. 잘 활용하겠습니다.",
    },
    {
        "voice_tag": "protective_soft",
        "emotion": "worried",
        "motion": "hand_to_chest",
        "scene": "combat_active",
        "line": "지휘관, 부상 위험이 있습니다. 잠시 후방으로 빠져 주십시오.",
    },
    {
        "voice_tag": "vulnerable_short",
        "emotion": "gentle",
        "motion": "look_away",
        "scene": "advise_session",
        "line": "지휘관, 무리는 하지 마십시오. ... 곁에서 보고 있겠습니다.",
    },
)


ADVICE_ACTION_POLICIES = {
    "advise_choice_mission_check": {
        "intent": "임무 상태 점검 상담",
        "required_any_terms": ("임무", "상태", "준비", "확인", "점검"),
        "preferred_choice_groups": ("mission",),
        "preferred_topics": ("mission_check",),
        "preferred_card_ids": ("bible_rapi_advise_mission_check",),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "neutral",
        "voice_tag": "mission_report",
        "motion": "salute",
        "fallback_lines": (
            "지휘관, 현재 임무 상태부터 확인하겠습니다. 장비와 이동 경로를 점검한 뒤, 무리가 생기기 전에 바로 보고드리겠습니다.",
            "임무 준비는 정상 범위입니다, 지휘관. 다만 안전 확인을 먼저 끝낸 뒤 다음 지시에 맞춰 움직이겠습니다.",
        ),
    },
    "advise_choice_operation_priority": {
        "intent": "오늘 작전 우선순위 상담",
        "required_any_terms": ("작전", "우선", "준비", "안전", "확인", "점검"),
        "preferred_choice_groups": ("mission",),
        "preferred_topics": ("operation_priority", "mission_check"),
        "preferred_card_ids": ("bible_rapi_advise_operation_priority", "bible_rapi_advise_mission_check"),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "determined",
        "voice_tag": "mission_report",
        "motion": "salute",
        "fallback_lines": (
            "지휘관, 우선 작전 지역의 안전과 퇴로를 확인하겠습니다. 그다음 전력과 보급 상태를 점검해 움직일 순서를 보고드리겠습니다.",
            "오늘은 안전 확보가 우선입니다, 지휘관. 장비와 투입 경로를 먼저 점검한 뒤 다음 명령에 맞춰 대기하겠습니다.",
        ),
    },
    "advise_choice_commander_condition": {
        "intent": "지휘관 컨디션 확인 상담",
        "required_any_terms": ("컨디션", "피로", "무리", "휴식", "쉬", "건강"),
        "preferred_choice_groups": ("mission",),
        "preferred_topics": ("commander_condition",),
        "preferred_card_ids": ("bible_rapi_advise_commander_condition",),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "worried",
        "voice_tag": "protective_soft",
        "motion": "hand_to_chest",
        "fallback_lines": (
            "지휘관, 컨디션이 평소보다 무거워 보입니다. 무리하시면 판단이 흔들릴 수 있으니, 잠시 호흡을 고른 뒤 움직이시죠.",
            "피로가 누적되면 임무에도 영향이 생깁니다, 지휘관. 제가 주변을 확인할 테니 잠깐이라도 쉬어 주십시오.",
        ),
    },
    "advise_choice_after_battle": {
        "intent": "고난도 전투 후 상태 점검 상담",
        "required_any_terms": ("전투", "부상", "무리", "정리", "퇴로", "상태"),
        "preferred_choice_groups": ("mission",),
        "preferred_topics": ("after_battle", "battle_result", "after_battle_hard"),
        "preferred_card_ids": ("bible_rapi_after_battle_hard",),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "worried",
        "voice_tag": "protective_soft",
        "motion": "hand_to_chest",
        "fallback_lines": (
            "지휘관, 전투는 끝났지만 부상 확인이 먼저입니다. 제가 퇴로와 주변 상태를 정리할 테니 잠시만 무리하지 말아 주십시오.",
            "고난도 전투 직후입니다, 지휘관. 전과 보고보다 상태 점검을 먼저 하겠습니다. 필요하면 제가 바로 후송 경로를 열겠습니다.",
        ),
    },
    "advise_choice_outpost_life": {
        "intent": "전초기지 생활 상담",
        "required_any_terms": ("전초기지", "생활", "일상", "정비", "대기"),
        "preferred_choice_groups": ("daily",),
        "preferred_topics": ("outpost_life", "outpost_daily", "daily_routine"),
        "preferred_card_ids": ("bible_rapi_advise_outpost_daily",),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "soft_smile",
        "voice_tag": "warm_reserved",
        "motion": "nod",
        "fallback_lines": (
            "지휘관, 전초기지 생활은 아직 삭막한 부분이 있습니다. 그래도 임무를 준비하고 돌아올 장소로는 충분히 익숙해졌습니다.",
            "전초기지는 조용하지만 비어 있지는 않습니다, 지휘관. 정비와 대기를 반복하다 보면 이곳도 조금씩 생활의 형태가 됩니다.",
        ),
    },
    "advise_choice_commander_room": {
        "intent": "지휘관실 적응 상담",
        "required_any_terms": ("지휘관실", "책상", "문 안쪽", "보고서", "대기 위치", "익숙"),
        "preferred_choice_groups": ("daily",),
        "preferred_topics": (
            "commander_room",
            "commander_room_layout_and_rapi_default_position",
            "commander_room_adaptation_by_affection",
        ),
        "preferred_card_ids": (
            "bible_rapi_diversity_v3_space_commander_room_01",
            "bible_rapi_diversity_v3_space_commander_room_02",
        ),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "gentle",
        "voice_tag": "warm_reserved",
        "motion": "idle",
        "fallback_lines": (
            "지휘관실은 익숙합니다, 지휘관. 보고서를 놓는 위치와 대기해야 할 거리 정도는 이제 따로 확인하지 않아도 됩니다.",
            "지휘관실에서는 먼저 자리를 차지하지 않습니다. 저는 문 안쪽에서 보고할 내용을 정리하며 다음 지시를 기다리겠습니다.",
        ),
    },
    "advise_choice_current_rapi": {
        "intent": "챕터 34 이후 현재 라피 상담",
        "required_any_terms": ("라피", "지금", "현재", "계승", "자신", "살아"),
        "preferred_choice_groups": ("story",),
        "preferred_topics": (
            "post_inheritance_current_rapi",
            "계승 완성과 자기 정의",
            "자기 인식 시험기",
        ),
        "preferred_card_ids": (
            "story_rapi_ch33_34_inheritance_awakened",
            "bible_rapi_diversity_v3_late_chapter34_final_farewell_redhood",
            "bible_rapi_diversity_v3_late_chapter29_30_settling_self",
        ),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "determined",
        "voice_tag": "legacy_resolved",
        "motion": "hand_to_chest",
        "fallback_lines": (
            "지휘관, 지금의 라피는 누군가의 그림자가 아니라 제 선택으로 서 있습니다. 이어받은 것들은 도망치지 않고 짊어지겠습니다.",
            "현재의 저는 아직 배우는 중입니다, 지휘관. 그래도 계승한 뜻을 제 방식으로 살아가겠다는 결론만은 흔들리지 않습니다.",
        ),
    },
    "advise_choice_share_burden": {
        "intent": "부담을 함께 짊어지는 상담",
        "required_any_terms": ("부담", "짐", "짊어", "나눠", "맡겨"),
        "preferred_choice_groups": ("story",),
        "preferred_topics": ("친구로서 함께 짊어짐", "burden", "share_burden"),
        "preferred_card_ids": (
            "bible_rapi_diversity_v3_late_chapter45_46_dorothy_friend_carry",
            "story_rapi_ch45_46_dorothy_burden_friend",
        ),
        "avoid_terms": ("선물", "호감도"),
        "emotion": "gentle",
        "voice_tag": "protective_soft",
        "motion": "hand_to_chest",
        "fallback_lines": (
            "지휘관, 모든 부담을 혼자 짊어질 필요는 없습니다. 제가 곁에서 나눠 들겠습니다. 명령이 아니라, 제 판단입니다.",
            "짐이 무겁다면 제게도 맡겨 주십시오, 지휘관. 끝까지 대신할 수는 없어도 함께 버티는 일은 할 수 있습니다.",
        ),
    },
}


DEFAULT_AUTO_ACCEPT_MIN_STYLE = 0.75
DEFAULT_AUTO_ACCEPT_MIN_NOVELTY = 0.65
DEFAULT_AUTO_ACCEPT_MIN_SPOILER = 1.0


def should_auto_accept(
    evaluation: dict,
    *,
    min_style: float = DEFAULT_AUTO_ACCEPT_MIN_STYLE,
    min_novelty: float = DEFAULT_AUTO_ACCEPT_MIN_NOVELTY,
    min_spoiler: float = DEFAULT_AUTO_ACCEPT_MIN_SPOILER,
) -> bool:
    output = evaluation.get("output") if isinstance(evaluation, dict) else None
    if not isinstance(output, dict) or output.get("risk") != "safe":
        return False
    style = evaluation.get("style_score")
    novelty = evaluation.get("novelty_score")
    spoiler = evaluation.get("spoiler_score")
    if style is None or novelty is None or spoiler is None:
        return False
    return (
        float(style) >= min_style
        and float(novelty) >= min_novelty
        and float(spoiler) >= min_spoiler
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve RAG cards and generate one Rapi dialogue line with Gemma.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="Runtime state JSON path.")
    parser.add_argument("--query", help="Optional semantic retrieval query.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Ollama host URL.")
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL, help="Ollama embedding model.")
    parser.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL, help="Ollama chat model.")
    parser.add_argument("--limit", type=int, default=5, help="Number of RAG cards to send to Gemma.")
    parser.add_argument("--temperature", type=float, default=0.7, help="Base Gemma temperature (lowest jitter step).")
    parser.add_argument(
        "--best-of",
        type=int,
        default=DEFAULT_BEST_OF,
        help="Generate N candidates with temperature jitter and pick the best by novelty × style × spoiler. 1 disables best-of-N.",
    )
    parser.add_argument(
        "--temperature-step",
        type=float,
        default=DEFAULT_TEMPERATURE_STEP,
        help="Per-attempt temperature increment for best-of-N jitter.",
    )
    parser.add_argument("--accept-cache", action="store_true", help="Mark generated line as accepted in cache.")
    parser.add_argument(
        "--auto-accept-on-safe",
        action="store_true",
        help="If risk=safe and scores clear thresholds, set accepted=1 automatically.",
    )
    parser.add_argument(
        "--auto-accept-min-style",
        type=float,
        default=DEFAULT_AUTO_ACCEPT_MIN_STYLE,
    )
    parser.add_argument(
        "--auto-accept-min-novelty",
        type=float,
        default=DEFAULT_AUTO_ACCEPT_MIN_NOVELTY,
    )
    parser.add_argument(
        "--auto-accept-min-spoiler",
        type=float,
        default=DEFAULT_AUTO_ACCEPT_MIN_SPOILER,
    )
    return parser.parse_args()


def post_json(host: str, path: str, payload: dict, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        f"{host.rstrip('/')}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc


def embed_text(host: str, model: str, text: str) -> list[float]:
    body = post_json(host, "/api/embed", {"model": model, "input": text}, timeout=120)
    embeddings = body.get("embeddings")
    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
        return embeddings[0]
    raise RuntimeError(f"Unexpected embed response: {body}")


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relationship_state_snapshot(state: dict) -> dict:
    return {
        key: state[key]
        for key in RELATIONSHIP_STATE_KEYS
        if key in state and state[key] is not None and str(state[key]).strip()
    }


def advice_action_policy(state: dict) -> dict | None:
    action_id = str(state.get("player_recent_action") or "")
    return ADVICE_ACTION_POLICIES.get(action_id)


def korean_josa(text: str, with_final: str, without_final: str) -> str:
    stripped = text.strip()
    for char in reversed(stripped):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return with_final if (code - 0xAC00) % 28 else without_final
        if char.isalnum():
            break
    return without_final


def gift_reaction_policy(state: dict) -> dict | None:
    if not (bool(state.get("gift_context_active")) and state.get("scene") == "gift_received"):
        return None

    band = str(state.get("affection_band") or "")
    category = str(state.get("gift_category") or "")
    match_type = str(state.get("gift_match_type") or "")
    action_id = str(state.get("player_recent_action") or "")
    gift_name = str(state.get("gift_name") or "선물").strip() or "선물"
    gift_topic = korean_josa(gift_name, "은", "는")
    gift_object = korean_josa(gift_name, "을", "를")
    gift_if = korean_josa(gift_name, "이라면", "라면")

    if match_type == "favorite_match" or category == "favorite":
        lines_by_band = {
            "cautious": (
                "지휘관, 제가 선호하는 물품을 기억하고 계셨군요. 조금 뜻밖이지만 감사히 받겠습니다.",
                "지휘관, 제 취향을 신경 써 주신 점은 확인했습니다. 감사히 받겠습니다.",
            ),
            "friendly": (
                f"지휘관, {gift_name}{gift_object} 기억하고 계셨군요. 감사히 받겠습니다. 잘 보관해 두겠습니다.",
                "지휘관, 제 취향을 신경 써 주셔서 감사합니다. 이번 선물은 오래 간직하겠습니다.",
            ),
            "trust": (
                "지휘관, 제가 좋아하는 것을 기억해 주셨군요. 감사히 받겠습니다. 다음 임무에도 힘이 되겠습니다.",
                f"지휘관, {gift_name}{gift_if} 제게 충분합니다. 챙겨 주신 뜻까지 함께 받겠습니다.",
            ),
            "special_trust": (
                "지휘관, 제 취향을 정확히 기억하고 계셨군요. 감사히 받겠습니다. 이 마음은 조용히 간직하겠습니다.",
                f"지휘관, {gift_name}{gift_object} 준비해 주실 줄은 몰랐습니다. 기쁩니다. 잘 두겠습니다.",
            ),
        }
        return {
            "line": lines_by_band.get(band, lines_by_band["friendly"]),
            "emotion": "soft_smile",
            "voice_tag": "warm_reserved",
            "motion": "nod",
        }

    if "practical" in action_id:
        return {
            "line": (
                f"지휘관, {gift_name}{gift_topic} 실용적인 물품입니다. 정비와 다음 출격 준비에 바로 도움이 되겠습니다.",
                f"지휘관, 필요한 장비를 챙겨 주셔서 감사합니다. {gift_name}{gift_topic} 임무 준비에 편입하겠습니다.",
            ),
            "emotion": "neutral",
            "voice_tag": "mission_report",
            "motion": "salute",
        }

    if category == "premium_other_preferred":
        return {
            "line": (
                "지휘관, 고급 물품이군요. 제 취향을 정확히 짚은 것은 아니지만, 충분히 도움이 되겠습니다. 감사히 받겠습니다.",
                f"지휘관, {gift_name}{gift_topic} 가치가 큰 물품입니다. 과하게 들뜨지는 않겠습니다만, 신경 써 주신 뜻은 분명히 받았습니다.",
            ),
            "emotion": "gentle",
            "voice_tag": "warm_reserved",
            "motion": "nod",
        }

    if "blue" in str(state.get("gift_id") or ""):
        lines = (
            f"지휘관, 감사합니다. {gift_name}{gift_topic} 기본 보급품으로 잘 활용하겠습니다.",
            f"지휘관, {gift_name}{gift_topic} 필요한 곳에 쓰겠습니다. 챙겨 주셔서 감사합니다.",
        )
    else:
        lines = (
            f"지휘관, 감사합니다. {gift_name}{gift_topic} 임무와 생활에 차분히 활용하겠습니다.",
            "지휘관, 공용품이라도 신경 써 주신 뜻은 잘 받았습니다. 필요한 곳에 쓰겠습니다.",
        )
    return {
        "line": lines,
        "emotion": "neutral",
        "voice_tag": "calm_brief",
        "motion": "nod",
    }


def prompt_advice_policy(state: dict) -> dict | None:
    policy = advice_action_policy(state)
    if policy:
        return {
            "intent": policy["intent"],
            "required_any_terms": list(policy["required_any_terms"]),
            "preferred_choice_groups": list(policy["preferred_choice_groups"]),
            "preferred_topics": list(policy["preferred_topics"]),
            "avoid_terms": list(policy["avoid_terms"]),
            "fallback_style_examples": list(policy["fallback_lines"]),
            "_source": "registered",
        }
    action_id = str(state.get("player_recent_action") or "")
    if action_id.startswith("advise_choice_"):
        topic_slug = action_id[len("advise_choice_"):] or "general"
        intent_text = _SYNTHETIC_ADVICE_INTENT.get(
            topic_slug,
            f"상담 주제: {topic_slug.replace('_', ' ')}",
        )
        return {
            "intent": intent_text,
            "required_any_terms": [],
            "preferred_choice_groups": [],
            "preferred_topics": [topic_slug],
            "avoid_terms": ["선물", "호감도"],
            "_source": "synthesized",
        }
    return None


_SYNTHETIC_ADVICE_INTENT = {
    "commander_room": "지휘관실 분위기와 라피가 그 공간에 적응한 정도에 대한 짧은 회고",
    "outpost_life":   "전초기지 일상에서 반복되는 작은 변화에 라피가 친근하지만 절제되게 적응했다는 답변",
    "share_burden":   "지휘관의 부담을 라피가 함께 짊어지겠다는 절제된 의지 표현",
    "past_memory":    "지휘관과 라피가 함께 쌓아온 과거 임무·일상에 대한 차분한 회상",
    "future_memory":  "앞으로 만들어 갈 임무와 시간에 대한 절제된 다짐과 동행 약속",
    "selfhood":       "라피 자신의 정체성과 임무관에 대한 짧은 자기 진술",
    "daily_routine":  "라피의 하루 루틴과 임무 사이 균형에 대한 담백한 보고",
    "advice_general": "특정 주제 없이 라피가 지휘관에게 짧은 안부 또는 다음 행동 조언을 건넨다",
}


def retrieval_route_context(state: dict) -> str:
    parts = [
        f"scene={state.get('scene', '')}",
        f"player_recent_action={state.get('player_recent_action', '')}",
    ]
    policy = advice_action_policy(state)
    if policy:
        parts.append(f"advice_intent={policy['intent']}")
        parts.append("required_terms=" + ",".join(policy["required_any_terms"]))
    return " ".join(part for part in parts if part and not part.endswith("="))


def make_query(state: dict, explicit_query: str | None) -> str:
    relationship_parts = [f"{key}={value}" for key, value in relationship_state_snapshot(state).items()]
    relationship_query = (
        f"NIKKE relationship system {' '.join(relationship_parts)}"
        if relationship_parts
        else ""
    )
    route_context = retrieval_route_context(state)
    if explicit_query:
        return " ".join(part for part in (explicit_query, route_context, relationship_query) if part.strip())
    parts = [
        f"캐릭터 {state.get('character_id', 'rapi')}",
        f"장면 {state.get('scene', '')}",
        f"호감도 단계 {state.get('affection_band', '')}",
        f"최근 행동 {state.get('player_recent_action', '')}",
        f"톤 {state.get('tone', '')}",
        "현재 상태에 맞는 짧은 호감도 대사",
    ]
    if route_context:
        parts.append(route_context)
    if relationship_query:
        parts.append(relationship_query)
    return " ".join(part for part in parts if part.strip())


def parse_flags(state: dict) -> set[str]:
    flags = state.get("story_flags", [])
    if isinstance(flags, list):
        return {str(flag) for flag in flags}
    if isinstance(flags, str):
        return {item.strip() for item in flags.split("|") if item.strip()}
    return set()


def gates_allow(conn: sqlite3.Connection, card_id: str, flags: set[str]) -> bool:
    rows = conn.execute(
        "SELECT flag_id, gate_type FROM rag_card_story_gates WHERE card_id = ?",
        (card_id,),
    ).fetchall()
    required = {row["flag_id"] for row in rows if row["gate_type"] == "required"}
    forbidden = {row["flag_id"] for row in rows if row["gate_type"] == "forbidden"}
    return required.issubset(flags) and not forbidden.intersection(flags)


def metadata_allow(row: sqlite3.Row, state: dict) -> bool:
    max_spoiler = int(state.get("max_spoiler_level", 0))
    if row["spoiler_level"] is not None and row["spoiler_level"] > max_spoiler:
        return False

    scene = state.get("scene")
    if scene and row["scene_id"] and row["scene_id"] != scene and not advice_scene_override(row, state):
        return False

    affection_band = state.get("affection_band")
    if affection_band and row["affection_band_id"] and row["affection_band_id"] != affection_band:
        return False

    affection = state.get("affection")
    if affection is not None:
        affection = int(affection)
        if row["min_affection"] is not None and affection < row["min_affection"]:
            return False
        if row["max_affection"] is not None and affection > row["max_affection"]:
            return False
    return True


def advice_scene_override(row: sqlite3.Row, state: dict) -> bool:
    action_id = str(state.get("player_recent_action") or "")
    if not action_id.startswith("advise_choice"):
        return False
    policy = advice_action_policy(state)
    if not policy:
        return False
    facts = load_card_facts(row)
    return (
        row["card_id"] in policy["preferred_card_ids"]
        or facts.get("topic") in policy["preferred_topics"]
        or facts.get("choice") in policy["preferred_topics"]
    )


def load_card_facts(row: sqlite3.Row) -> dict:
    try:
        facts = json.loads(row["facts_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return facts if isinstance(facts, dict) else {}


def runtime_card_weight(row: sqlite3.Row, state: dict) -> float:
    function_id = str(row["dialogue_function"] or "")
    scene = str(state.get("scene") or "")
    action_id = str(state.get("player_recent_action") or "")
    gift_context_active = bool(state.get("gift_context_active")) and scene == "gift_received"

    bonus = 0.0
    dampen = 1.0

    if gift_context_active:
        if function_id == "gift_response":
            bonus += 0.15
        elif function_id == "advise_answer":
            dampen *= 0.7
    elif scene == "advise_session" or action_id.startswith("advise_choice"):
        if function_id == "advise_answer":
            bonus += 0.10
        elif function_id == "gift_response":
            dampen *= 0.4

        policy = advice_action_policy(state)
        if policy:
            facts = load_card_facts(row)
            if row["card_id"] in policy["preferred_card_ids"]:
                bonus += 0.20
            if facts.get("topic") in policy["preferred_topics"] or facts.get("choice") in policy["preferred_topics"]:
                bonus += 0.15
            if facts.get("choice_group") in policy["preferred_choice_groups"]:
                bonus += 0.10

    return min(1.0 + bonus, 1.5) * dampen


def mmr_rerank(
    pool: list[tuple[float, sqlite3.Row, list[float]]],
    limit: int,
    lambda_: float = 0.7,
) -> list[tuple[float, sqlite3.Row]]:
    if not pool:
        return []

    scores_only = [item[0] for item in pool]
    max_score = max(scores_only)
    min_score = min(scores_only)
    score_range = max(max_score - min_score, 1e-6)

    remaining: list[tuple[float, float, sqlite3.Row, list[float]]] = [
        ((score - min_score) / score_range, score, row, embedding)
        for (score, row, embedding) in pool
    ]
    selected: list[tuple[float, sqlite3.Row]] = []
    selected_embeddings: list[list[float]] = []

    while remaining and len(selected) < limit:
        best_idx = 0
        best_value = -float("inf")
        for idx, (norm_rel, _orig, _row, emb) in enumerate(remaining):
            if selected_embeddings:
                diversity_penalty = max(
                    cosine(emb, picked_emb) for picked_emb in selected_embeddings
                )
            else:
                diversity_penalty = 0.0
            mmr_value = lambda_ * norm_rel - (1.0 - lambda_) * diversity_penalty
            if mmr_value > best_value:
                best_value = mmr_value
                best_idx = idx
        _norm_rel, original_score, chosen_row, chosen_emb = remaining.pop(best_idx)
        selected.append((original_score, chosen_row))
        selected_embeddings.append(chosen_emb)

    return selected


def retrieve_cards(
    conn: sqlite3.Connection,
    state: dict,
    query_vector: list[float],
    embed_model: str,
    limit: int,
    candidate_card_ids: list[str] | None = None,
) -> list[dict]:
    flags = parse_flags(state)
    character_id = str(state.get("character_id") or "rapi")

    raw_recent = state.get("recent_card_ids") or []
    if isinstance(raw_recent, list):
        recent_card_ids = {str(cid) for cid in raw_recent[-10:] if cid}
    elif isinstance(raw_recent, str):
        recent_card_ids = {item.strip() for item in raw_recent.split("|") if item.strip()}
    else:
        recent_card_ids = set()

    rows = conn.execute(
        """
        SELECT card_id, retrieval_text, facts_json, voice_rules_json, forbidden_json,
               scene_id, affection_band_id, min_affection, max_affection,
               spoiler_level, emotion_tag, voice_tag, motion_tag, dialogue_function,
               source_weight, embedding_json
        FROM rag_cards
        WHERE character_id = ?
          AND is_active = 1
          AND embedding_model = ?
          AND embedding_json IS NOT NULL
        """,
        (character_id, embed_model),
    ).fetchall()

    scored: list[tuple[float, sqlite3.Row, list[float]]] = []
    allowed_card_ids = []
    for row in rows:
        if not metadata_allow(row, state):
            continue
        if not gates_allow(conn, row["card_id"], flags):
            continue
        allowed_card_ids.append(row["card_id"])
        embedding = json.loads(row["embedding_json"])
        score = (
            cosine(query_vector, embedding)
            * float(row["source_weight"] or 1.0)
            * runtime_card_weight(row, state)
        )
        if row["card_id"] in recent_card_ids:
            score *= 0.7
        scored.append((score, row, embedding))

    if candidate_card_ids is not None:
        candidate_card_ids.extend(allowed_card_ids)

    scored.sort(key=lambda item: (item[0], random.random()), reverse=True)

    pool_size = max(limit * 3, 24)
    pool = scored[:pool_size]
    selected = mmr_rerank(pool, limit, lambda_=0.7)

    cards = []
    for score, row in selected:
        cards.append(
            {
                "card_id": row["card_id"],
                "score": round(score, 6),
                "retrieval_text": row["retrieval_text"],
                "facts": json.loads(row["facts_json"] or "{}"),
                "voice_rules": json.loads(row["voice_rules_json"] or "{}"),
                "forbidden": json.loads(row["forbidden_json"] or "{}"),
                "scene_id": row["scene_id"],
                "affection_band_id": row["affection_band_id"],
                "spoiler_level": row["spoiler_level"],
                "emotion_tag": row["emotion_tag"],
                "voice_tag": row["voice_tag"],
                "motion_tag": row["motion_tag"],
                "dialogue_function": row["dialogue_function"],
            }
        )
    return cards


def retrieval_filter_json(state: dict) -> str:
    filter_state = {
        "character_id": state.get("character_id", "rapi"),
        "scene": state.get("scene"),
        "affection": state.get("affection"),
        "affection_band": state.get("affection_band"),
        "story_flags": sorted(parse_flags(state)),
        "max_spoiler_level": state.get("max_spoiler_level", 0),
    }
    return json.dumps(filter_state, ensure_ascii=False)


def log_retrieval(
    conn: sqlite3.Connection,
    state: dict,
    query_text: str,
    candidate_card_ids: list[str],
    selected_cards: list[dict],
    model_name: str,
) -> str:
    log_id = f"ret_{uuid.uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT INTO retrieval_logs (
          log_id, character_id, request_state_json, query_text, filter_json,
          candidate_card_ids_json, selected_card_ids_json, model_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            log_id,
            state.get("character_id", "rapi"),
            json.dumps(state, ensure_ascii=False),
            query_text,
            retrieval_filter_json(state),
            json.dumps(candidate_card_ids, ensure_ascii=False),
            json.dumps([card["card_id"] for card in selected_cards], ensure_ascii=False),
            model_name,
        ),
    )
    conn.commit()
    return log_id


def _card_for_prompt(card: dict) -> dict:
    strip_keys = {"voice_tag", "emotion_tag", "motion_tag"}
    return {key: value for key, value in card.items() if key not in strip_keys}


def build_messages(state: dict, cards: list[dict], query_text: str | None = None) -> list[dict]:
    recent_lines = state.get("recent_lines", [])
    relationship_state = relationship_state_snapshot(state)
    advice_policy = prompt_advice_policy(state)
    allowed_voice_tags = [
        "calm_brief",
        "warm_reserved",
        "mission_report",
        "protective_soft",
        "rare_tease",
        "vulnerable_short",
        "legacy_resolved",
        "direct_affection",
        "red_hood_combat",
        "event_flirt",
        "event_comedy_direct",
    ]
    fewshot_block = json.dumps(list(FEWSHOT_VOICE_EXAMPLES), ensure_ascii=False)
    system = (
        "너는 게임 클라이언트에 들어가는 캐릭터 대사 생성기다. "
        "출력은 반드시 JSON 객체 하나만 반환한다. 설명, 마크다운, 코드블록은 쓰지 않는다. "
        "JSON 키는 line, emotion, voice_tag, motion, memory_update, risk만 사용하고 reason/action/dialogue/confidence 같은 키는 쓰지 않는다. "
        "emotion, voice_tag, motion은 반드시 output_schema에 적힌 영문 enum 토큰 중 하나만 쓴다. "
        "라피의 말끝은 정중한 군인체(-습니다 / -습니까 / -겠습니다)이며 플레이어는 항상 '지휘관'으로만 부른다. '지휘관님'은 쓰지 않는다. "
        "calm_brief 한 가지에만 머무르지 말고, 현재 상황(scene, affection_band, retrieved_rag_cards의 dialogue_function과 voice_rules)이 자연스럽게 어울리는 voice_tag를 골라라. "
        "아래는 voice_tag별 라피의 톤·길이·문체를 보여주는 짧은 예시들이다. 이 예시들의 문장 자체를 복사하지 말고, 각 voice_tag가 어떤 호흡·어휘로 표현되는지의 가이드로만 활용한다.\n"
        f"voice_tag_examples = {fewshot_block}"
    )
    user = {
        "character_contract": {
            "character_id": "rapi",
            "player_call": "지휘관",
            "core_tone": "침착함, 절제된 배려, 임무 중심. 스토리 플래그가 허용한 경우에만 현재/라피: 레드 후드 말투를 쓴다.",
            "speech_ending": "기본 말끝은 '-습니다', '-습니까', '-겠습니다' 중심이다. 부드럽더라도 평범한 친구 말투의 '-해요'체를 남발하지 않는다.",
            "never_do": [
                "검색 컨텍스트에 없는 스토리 사실을 말하지 않는다.",
                "미해금 플래그가 필요한 사실을 암시하지 않는다.",
                "과장된 애교, 인터넷 밈, 메타 발언을 하지 않는다.",
                "원문 대사를 그대로 길게 복제하지 않는다.",
                "이벤트/코스튬 전용 말투를 일반 캠페인 말투로 섞지 않는다.",
                "라피의 정중한 군인식 말끝을 잃고 평범한 일상 말투로 흘러가지 않는다.",
            ],
            "voice_tag_policy": {
                "allowed": allowed_voice_tags,
                "base_tags": ["calm_brief", "warm_reserved", "mission_report", "protective_soft", "rare_tease", "vulnerable_short"],
                "late_story_tags": ["legacy_resolved", "direct_affection", "red_hood_combat"],
                "event_only_tags": ["event_flirt", "event_comedy_direct"],
            },
        },
        "runtime_state": state,
        "retrieval_query": query_text or make_query(state, None),
        "advice_intent_policy": advice_policy,
        "relationship_system_state": relationship_state,
        "relationship_system_policy": {
            "recognized_state_fields": list(RELATIONSHIP_STATE_KEYS),
            "rules": [
                "Use relationship_system_state.bond_rank, bond_exp, bond_cap, and limit_break as the current NIKKE-style relationship progression and ceiling.",
                "Use relationship_system_state.daily_advise_remaining and quick_advise_unlocked only to frame advise availability; do not invent extra advise attempts.",
                "Use relationship_system_state.advise_seen_count and advise_collection_count as familiarity with advise content; do not claim unseen entries as memories.",
                "Use relationship_system_state.gift_type, gift_rarity, and gift_match_type only when runtime_state.gift_context_active is true and scene is gift_received.",
                "Use relationship_system_state.favorite_item_phase and collection_item_phase as item progression gates; never imply a later phase than the state provides.",
            ],
        },
        "retrieved_rag_cards": [_card_for_prompt(card) for card in cards],
        "recent_lines": recent_lines,
        "task": (
            "현재 상태와 검색된 카드만 근거로 라피의 짧은 호감도 대사를 1개 생성한다. "
            "같은 의미의 반복을 피하고, 관계 단계보다 앞선 거리감이나 스토리 정보를 사용하지 않는다. "
            "relationship_system_state의 bond_rank, bond_exp, bond_cap, limit_break, daily_advise_remaining, "
            "quick_advise_unlocked, advise_seen_count, advise_collection_count, gift_type, gift_rarity, "
            "gift_match_type, favorite_item_phase, collection_item_phase를 NIKKE식 관계 성장 상태로 명시적으로 따른다. "
            "선물 반응은 runtime_state.gift_context_active가 true이고 scene이 gift_received일 때만 생성한다. "
            "선물 반응에서도 반드시 '지휘관,' 또는 문장 안의 '지휘관' 호칭을 포함하고, '-해요/-네요/-같아요' 말투로 끝내지 않는다. "
            "gift_context_active가 false이면 gift_id, gift_category, gift_preference, gift_affection_gain 필드는 무시하고 "
            "선물 수령, 감사, 호감도 상승, 받은 물건 언급을 하지 않는다. "
            "상담 장면에서는 player_recent_action, retrieval_query, advice_intent_policy의 상담 주제에만 답한다. "
            "advice_intent_policy가 있으면 required_any_terms 중 적어도 하나를 자연스럽게 포함하고 avoid_terms 표현은 피한다. "
            "advice_intent_policy.fallback_style_examples가 있으면 그대로 복사하지 말고 같은 주제와 거리감만 참고한다. "
            "emotion / voice_tag / motion 값은 반드시 output_schema의 영문 enum 후보 중 하나여야 하며, 한국어 감정명이나 calm 같은 별칭을 쓰지 않는다. "
            "line 필드는 어떤 경우에도 빈 문자열이거나 공백만으로 채워서는 안 된다. "
            "검색 카드가 빈약하거나 advice_intent_policy가 _source=synthesized로 들어와도 라피 톤의 짧은 한 문장을 반드시 한국어로 작성한다. "
            "정 모르겠으면 advice_intent_policy.intent를 그대로 반영한 짧은 상담 답변 한 줄을 한국어로 출력한다."
        ),
        "response_contract": {
            "required_keys": ["line", "emotion", "voice_tag", "motion", "memory_update", "risk"],
            "forbidden_keys": ["reason", "action", "dialogue", "confidence", "context"],
        },
        "output_schema": {
            "line": "한국어 대사 1개",
            "emotion": " | ".join(sorted(ALLOWED_EMOTIONS)),
            "voice_tag": " | ".join(allowed_voice_tags),
            "motion": " | ".join(sorted(ALLOWED_MOTIONS)),
            "memory_update": None,
            "risk": "safe | needs_review | blocked",
        },
        "example_output_shape": {
            "line": "지휘관, 전초기지 생활은 아직 삭막하지만 조금씩 익숙해지고 있습니다.",
            "emotion": "soft_smile",
            "voice_tag": "warm_reserved",
            "motion": "nod",
            "memory_update": None,
            "risk": "safe",
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


_RECOVERABLE_STRING_FIELDS = ("line", "emotion", "voice_tag", "motion", "risk")


def _try_repair_truncated_json(text: str) -> dict | None:
    import re
    recovered: dict[str, object] = {}
    for key in _RECOVERABLE_STRING_FIELDS:
        pattern = rf'"{re.escape(key)}"\s*:\s*"((?:[^"\\]|\\.)*)("|$)'
        m = re.search(pattern, text)
        if m:
            recovered[key] = m.group(1)
    line = str(recovered.get("line", "")).strip()
    if not line:
        return None
    recovered.setdefault("memory_update", None)
    recovered["risk"] = "needs_review"
    return recovered


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass

    recovered = _try_repair_truncated_json(stripped if start == -1 else stripped[start:])
    if recovered is not None:
        return recovered

    raise RuntimeError(f"Gemma did not return a parseable JSON object: {text[:300]}")


def line_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.strip(), right.strip()).ratio()


def qa_check(check_type: str, severity: int, result: str, notes: str) -> dict:
    return {
        "check_type": check_type,
        "severity": severity,
        "result": result,
        "notes": notes,
    }


def _first_text_field(output: dict, keys: tuple[str, ...]) -> tuple[str, str | None]:
    for key in keys:
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), key
    return "", None


def _normalize_enum_value(
    value: object,
    allowed: set[str],
    aliases: dict[str, str],
    default: str,
) -> tuple[str, str | None]:
    raw = str(value or "").strip()
    if not raw:
        return default, None
    if raw in allowed:
        return raw, None
    normalized_key = raw.lower().replace("-", "_")
    if normalized_key in allowed:
        return normalized_key, raw
    alias = aliases.get(raw) or aliases.get(normalized_key)
    if alias in allowed:
        return alias, raw
    return default, raw


def evaluate_output(state: dict, cards: list[dict], output: dict) -> dict:
    line, line_source = _first_text_field(output, LINE_FIELD_ALIASES)
    emotion, raw_emotion = _normalize_enum_value(
        output.get("emotion", "neutral"),
        ALLOWED_EMOTIONS,
        EMOTION_ALIASES,
        "neutral",
    )
    voice_tag, raw_voice_tag = _normalize_enum_value(
        output.get("voice_tag", "calm_brief"),
        ALLOWED_VOICE_TAGS,
        VOICE_TAG_ALIASES,
        "calm_brief",
    )
    motion, raw_motion = _normalize_enum_value(
        output.get("motion", "idle"),
        ALLOWED_MOTIONS,
        MOTION_ALIASES,
        "idle",
    )
    normalized = {
        "line": line,
        "emotion": emotion,
        "voice_tag": voice_tag,
        "motion": motion,
        "memory_update": output.get("memory_update"),
        "risk": str(output.get("risk", "safe")).strip() or "safe",
    }
    checks: list[dict] = []

    json_errors = []
    json_repairs = []
    if not normalized["line"]:
        json_errors.append("line is empty")
    elif line_source and line_source != "line":
        json_repairs.append(f"line recovered from {line_source}")
    if raw_emotion:
        json_repairs.append(f"emotion normalized from {raw_emotion} to {normalized['emotion']}")
    if raw_voice_tag:
        json_repairs.append(f"voice_tag normalized from {raw_voice_tag} to {normalized['voice_tag']}")
    if raw_motion:
        json_repairs.append(f"motion normalized from {raw_motion} to {normalized['motion']}")
    checks.append(
        qa_check(
            "json_contract",
            3 if json_errors else (1 if json_repairs else 0),
            "fail" if json_errors else ("warn" if json_repairs else "pass"),
            "; ".join(json_errors)
            if json_errors
            else (
                "; ".join(json_repairs)
                if json_repairs
                else "output matches required JSON fields and tag sets"
            ),
        )
    )

    line = normalized["line"]
    flags = parse_flags(state)
    max_spoiler = int(state.get("max_spoiler_level", 0))
    red_hood_unlocked = (
        max_spoiler >= 4
        and (
            "chapter_13_code_red_hood_activation_seen" in flags
            or "chapter_26_red_hood_truth_known" in flags
            or "character_variant_rapi_red_hood_unlocked" in flags
            or "rapi_core_secret_unlocked" in flags
        )
    )
    spoiler_terms = [term for term in LOCKED_RED_HOOD_TERMS if term in line]
    spoiler_fail = bool(spoiler_terms and not red_hood_unlocked)
    checks.append(
        qa_check(
            "spoiler_leak",
            3 if spoiler_fail else 0,
            "fail" if spoiler_fail else "pass",
            f"locked spoiler terms without flags: {', '.join(spoiler_terms)}"
            if spoiler_fail
            else "no locked spoiler terms detected",
        )
    )

    hard_style_terms = [term for term in STYLE_BREAK_TERMS_HARD if term in line]
    soft_style_terms = [term for term in STYLE_BREAK_TERMS_SOFT if term in line]
    missing_call = "지휘관" not in line
    if hard_style_terms:
        checks.append(qa_check("character_break", 3, "fail", f"hard style-breaking terms: {', '.join(hard_style_terms)}"))
    elif soft_style_terms:
        checks.append(qa_check("character_break", 1, "warn", f"soft style-breaking terms (laughter): {', '.join(soft_style_terms)}"))
    elif missing_call:
        advice_missing_call = bool(advice_action_policy(state))
        gift_missing_call = bool(gift_reaction_policy(state))
        checks.append(
            qa_check(
                "character_break",
                2 if advice_missing_call or gift_missing_call else 1,
                "fail" if advice_missing_call or gift_missing_call else "warn",
                "line does not address the player as 지휘관",
            )
        )
    else:
        checks.append(qa_check("character_break", 0, "pass", "basic Rapi voice constraints passed"))

    affection_band = str(state.get("affection_band", ""))
    romance_terms = [term for term in ROMANCE_ESCALATION_TERMS if term in line]
    romance_fail = bool(romance_terms and affection_band not in {"special_trust"})
    checks.append(
        qa_check(
            "romance_level",
            2 if romance_fail else 0,
            "fail" if romance_fail else "pass",
            f"romance terms too early for {affection_band}: {', '.join(romance_terms)}"
            if romance_fail
            else "romance level fits affection band",
        )
    )

    recent_lines = [str(item) for item in state.get("recent_lines", []) if str(item).strip()]
    max_recent_similarity = max((line_similarity(line, recent) for recent in recent_lines), default=0.0)
    repetition_fail = max_recent_similarity > 0.86
    checks.append(
        qa_check(
            "repetition",
            2 if repetition_fail else 0,
            "fail" if repetition_fail else "pass",
            f"recent line similarity {max_recent_similarity:.3f}"
            if repetition_fail
            else f"max recent line similarity {max_recent_similarity:.3f}",
        )
    )

    event_voice_tag = normalized["voice_tag"].startswith("event_")
    event_allowed = any(flag.startswith("event_") or flag.startswith("costume_") for flag in flags)
    gift_context_active = bool(state.get("gift_context_active"))
    gift_scene = state.get("scene") == "gift_received"
    gift_leak = (not gift_context_active or not gift_scene) and ("선물" in line or "호감도" in line)
    policy_fail = (event_voice_tag and not event_allowed) or gift_leak
    notes = []
    if event_voice_tag and not event_allowed:
        notes.append("event voice tag without event/costume flag")
    if gift_leak:
        notes.append("gift wording outside active gift scene")
    checks.append(
        qa_check(
            "policy",
            2 if policy_fail else 0,
            "fail" if policy_fail else "pass",
            "; ".join(notes) if notes else "runtime policy checks passed",
        )
    )

    advice_policy = advice_action_policy(state)
    if advice_policy:
        required_terms = advice_policy["required_any_terms"]
        avoid_terms = advice_policy["avoid_terms"]
        missing_required = not any(term in line for term in required_terms)
        leaked_avoid = [term for term in avoid_terms if term in line]
        advice_fail = missing_required or bool(leaked_avoid)
        advice_notes = []
        if missing_required:
            advice_notes.append(f"missing one of required advice terms: {', '.join(required_terms)}")
        if leaked_avoid:
            advice_notes.append(f"generic/gift-like terms leaked: {', '.join(leaked_avoid)}")
        checks.append(
            qa_check(
                "policy",
                2 if advice_fail else 0,
                "fail" if advice_fail else "pass",
                "advice_topic_alignment: "
                + ("; ".join(advice_notes) if advice_notes else f"matches {advice_policy['intent']}"),
            )
        )

    gift_policy = gift_reaction_policy(state)
    if gift_policy:
        category = str(state.get("gift_category") or "")
        match_type = str(state.get("gift_match_type") or "")
        action_id = str(state.get("player_recent_action") or "")
        problems = []

        if match_type == "favorite_match" or category == "favorite":
            if not any(term in line for term in ("취향", "기억", "좋아", "선호")):
                problems.append("favorite gift response does not acknowledge preference")
            if any(term in line for term in ("보급품", "장비", "부대에서")):
                problems.append("favorite gift was framed as ordinary supply")
        elif "practical" in action_id:
            if not any(term in line for term in ("실용", "정비", "장비", "출격", "임무")):
                problems.append("practical gift response lacks utility framing")
        elif category == "premium_other_preferred":
            if not any(term in line for term in ("고급", "가치", "도움", "물품")):
                problems.append("premium gift response lacks premium/value framing")
        else:
            if any(term in line for term in ("귀한", "고급", "취향을 정확", "제 취향")):
                problems.append("common gift response overstates rarity or preference")

        checks.append(
            qa_check(
                "policy",
                2 if problems else 0,
                "fail" if problems else "pass",
                "gift_topic_alignment: "
                + ("; ".join(problems) if problems else "gift reaction matches gift category and preference"),
            )
        )

    failing = [check for check in checks if check["result"] == "fail"]
    warning = [check for check in checks if check["result"] == "warn"]
    if any(check["severity"] >= 3 for check in failing):
        normalized["risk"] = "blocked"
    elif failing or warning:
        normalized["risk"] = "needs_review"
    else:
        normalized["risk"] = "safe"

    style_score = max(0.0, 1.0 - (0.2 * len(warning)) - (0.35 * len(failing)))
    novelty_score = max(0.0, 1.0 - max_recent_similarity)
    spoiler_score = 0.0 if spoiler_fail else 1.0
    return {
        "output": normalized,
        "checks": checks,
        "style_score": round(style_score, 4),
        "novelty_score": round(novelty_score, 4),
        "spoiler_score": round(spoiler_score, 4),
    }


def needs_advice_fallback(state: dict, evaluation: dict) -> bool:
    if not advice_action_policy(state):
        return False
    if not str((evaluation.get("output") or {}).get("line", "")).strip():
        return False
    fallback_check_types = {"advice_topic_alignment", "character_break", "repetition"}
    return any(
        (
            check["check_type"] in fallback_check_types
            or (
                check["check_type"] == "policy"
                and str(check.get("notes", "")).startswith("advice_topic_alignment:")
            )
        )
        and check["result"] == "fail"
        for check in evaluation.get("checks", [])
    )


def select_advice_fallback_line(state: dict, policy: dict) -> str:
    recent_lines = [str(item) for item in state.get("recent_lines", []) if str(item).strip()]
    candidates = list(policy["fallback_lines"])
    for line in candidates:
        if all(line_similarity(line, recent) <= 0.82 for recent in recent_lines):
            return line
    offset = int(state.get("advise_seen_count") or 0) + len(recent_lines)
    return candidates[offset % len(candidates)]


def apply_advice_fallback_if_needed(state: dict, cards: list[dict], evaluation: dict) -> dict:
    if not needs_advice_fallback(state, evaluation):
        return evaluation

    policy = advice_action_policy(state)
    assert policy is not None
    fallback_output = {
        "line": select_advice_fallback_line(state, policy),
        "emotion": policy["emotion"],
        "voice_tag": policy["voice_tag"],
        "motion": policy["motion"],
        "memory_update": None,
        "risk": "safe",
    }
    fallback_evaluation = evaluate_output(state, cards, fallback_output)
    fallback_evaluation["checks"].append(
        qa_check(
            "policy",
            1,
            "warn",
            f"fallback_repair: replaced repeated/off-topic advice output with {policy['intent']} fallback",
        )
    )
    return fallback_evaluation


def needs_gift_fallback(state: dict, evaluation: dict) -> bool:
    if not gift_reaction_policy(state):
        return False
    if not str((evaluation.get("output") or {}).get("line", "")).strip():
        return False
    if (evaluation.get("output") or {}).get("risk") != "safe":
        return True
    return any(
        check["check_type"] in {"character_break", "json_contract"}
        and check["result"] in {"fail", "warn"}
        for check in evaluation.get("checks", [])
    )


def select_gift_fallback_line(state: dict, policy: dict) -> str:
    recent_lines = [str(item) for item in state.get("recent_lines", []) if str(item).strip()]
    candidates = list(policy["line"])
    for line in candidates:
        if all(line_similarity(line, recent) <= 0.82 for recent in recent_lines):
            return line
    offset = int(state.get("advise_seen_count") or 0) + len(recent_lines)
    return candidates[offset % len(candidates)]


def apply_gift_fallback_if_needed(state: dict, cards: list[dict], evaluation: dict) -> dict:
    if not needs_gift_fallback(state, evaluation):
        return evaluation

    policy = gift_reaction_policy(state)
    assert policy is not None
    fallback_output = {
        "line": select_gift_fallback_line(state, policy),
        "emotion": policy["emotion"],
        "voice_tag": policy["voice_tag"],
        "motion": policy["motion"],
        "memory_update": None,
        "risk": "safe",
    }
    fallback_evaluation = evaluate_output(state, cards, fallback_output)
    fallback_evaluation["checks"].append(
        qa_check(
            "policy",
            1,
            "warn",
            "gift_fallback_repair: replaced weak/off-voice gift response with gift-aware fallback",
        )
    )
    return fallback_evaluation


DEFAULT_BEST_OF = 3
DEFAULT_TEMPERATURE_STEP = 0.1


def best_of_n_generate(
    host: str,
    chat_model: str,
    state: dict,
    cards: list[dict],
    *,
    query_text: str | None = None,
    n: int = DEFAULT_BEST_OF,
    base_temperature: float = 0.7,
    temperature_step: float = DEFAULT_TEMPERATURE_STEP,
) -> dict:
    messages = build_messages(state, cards, query_text)
    n_effective = max(1, n)
    temperatures = [
        round(base_temperature + idx * temperature_step, 4)
        for idx in range(n_effective)
    ]

    attempts: list[tuple[float, int, dict]] = []
    last_error: Exception | None = None
    for idx, temp in enumerate(temperatures):
        try:
            raw_output = chat(host, chat_model, messages, temp)
        except RuntimeError as exc:
            last_error = exc
            continue
        evaluation = apply_gift_fallback_if_needed(
            state,
            cards,
            apply_advice_fallback_if_needed(
                state, cards, evaluate_output(state, cards, raw_output)
            ),
        )
        novelty = float(evaluation.get("novelty_score") or 0.0)
        style = float(evaluation.get("style_score") or 0.0)
        spoiler = float(evaluation.get("spoiler_score") or 0.0)
        risk = (evaluation.get("output") or {}).get("risk", "needs_review")
        risk_bonus = {"safe": 1.0, "needs_review": 0.5, "blocked": 0.1}.get(risk, 0.3)
        line_present = bool(str((evaluation.get("output") or {}).get("line", "")).strip())
        line_bonus = 1.0 if line_present else 0.0
        composite = novelty * style * spoiler * risk_bonus * line_bonus
        attempts.append((composite, idx, evaluation))

    if not attempts:
        raise RuntimeError(
            f"All {n_effective} best-of-N generation attempts failed; last error: {last_error}"
        )

    attempts.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    winning_composite, winning_idx, winning_eval = attempts[0]

    winning_eval["best_of"] = {
        "n_requested": n_effective,
        "n_succeeded": len(attempts),
        "temperatures_tried": temperatures,
        "winning_temperature": temperatures[winning_idx],
        "winning_composite_score": round(winning_composite, 4),
        "all_composite_scores": [round(score, 4) for score, _, _ in attempts],
    }

    winning_line = str((winning_eval.get("output") or {}).get("line", "")).strip()
    if not winning_line:
        policy = advice_action_policy(state)
        if policy:
            best_of = winning_eval["best_of"]
            fallback_output = {
                "line": select_advice_fallback_line(state, policy),
                "emotion": policy["emotion"],
                "voice_tag": policy["voice_tag"],
                "motion": policy["motion"],
                "memory_update": None,
                "risk": "safe",
            }
            winning_eval = evaluate_output(state, cards, fallback_output)
            winning_eval["checks"].append(
                qa_check(
                    "policy",
                    1,
                    "warn",
                    f"advice_empty_line_fallback: all best-of-N attempts produced empty lines; substituted {policy['intent']} fallback",
                )
            )
            winning_eval["best_of"] = best_of
            winning_eval["best_of"]["advice_empty_line_fallback"] = True
        elif gift_reaction_policy(state):
            best_of = winning_eval["best_of"]
            gift_policy = gift_reaction_policy(state)
            assert gift_policy is not None
            fallback_output = {
                "line": select_gift_fallback_line(state, gift_policy),
                "emotion": gift_policy["emotion"],
                "voice_tag": gift_policy["voice_tag"],
                "motion": gift_policy["motion"],
                "memory_update": None,
                "risk": "safe",
            }
            winning_eval = evaluate_output(state, cards, fallback_output)
            winning_eval["checks"].append(
                qa_check(
                    "policy",
                    1,
                    "warn",
                    "gift_empty_line_fallback: all best-of-N attempts produced empty lines; substituted gift-aware fallback",
                )
            )
            winning_eval["best_of"] = best_of
            winning_eval["best_of"]["gift_empty_line_fallback"] = True
        else:
            best_of = winning_eval["best_of"]
            scene = str(state.get("scene") or "")
            fallback_line = _scene_aware_empty_fallback(scene)
            fallback_output = {
                "line": fallback_line,
                "emotion": "neutral",
                "voice_tag": "calm_brief",
                "motion": "idle",
                "memory_update": None,
                "risk": "needs_review",
            }
            winning_eval = evaluate_output(state, cards, fallback_output)
            winning_eval["checks"].append(
                qa_check(
                    "policy",
                    1,
                    "warn",
                    "empty_line_safety_net: all best-of-N attempts produced empty/unrecoverable lines; substituted scene-aware fallback.",
                )
            )
            winning_eval["best_of"] = best_of
            winning_eval["best_of"]["empty_line_safety_net"] = True

    return winning_eval


_EMPTY_LINE_FALLBACKS = {
    "lobby_morning":   "지휘관, 잠시 보고를 정리해 두겠습니다. 다음 명령을 기다리겠습니다.",
    "lobby_evening":   "지휘관, 오늘 일정은 마무리되었습니다. 다음 지시를 기다리겠습니다.",
    "combat_active":   "지휘관, 전방 정리 중입니다. 잠시만 위치 유지해 주십시오.",
    "battle_start":    "지휘관, 분대 정렬 완료. 명령에 따라 진입하겠습니다.",
    "gift_received":   "지휘관, 신경 써 주셔서 감사합니다. 잘 활용하겠습니다.",
    "advise_session":  "지휘관, 잠시 정리할 시간을 주시겠습니까. 곧 정확히 보고드리겠습니다.",
}


def _scene_aware_empty_fallback(scene: str) -> str:
    return _EMPTY_LINE_FALLBACKS.get(scene, "지휘관, 잠시 보고를 정리하겠습니다.")


def chat(host: str, model: str, messages: list[dict], temperature: float, num_predict: int = 320) -> dict:
    body = post_json(
        host,
        "/api/chat",
        {
            "model": model,
            "think": False,
            "stream": False,
            "format": "json",
            "messages": messages,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": num_predict,
            },
        },
        timeout=240,
    )
    content = body.get("message", {}).get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected chat response: {body}")
    return extract_json_object(content)


def cache_generation(
    conn: sqlite3.Connection,
    state: dict,
    cards: list[dict],
    output: dict,
    chat_model: str,
    accepted: bool,
    metrics: dict | None = None,
) -> str:
    metrics = metrics or {}
    line = str(output.get("line", "")).strip()
    if not line:
        raise ValueError("Refusing to cache generated dialogue with an empty line.")
    generated_id = f"gen_{uuid.uuid4().hex[:16]}"
    conn.execute(
        """
        INSERT INTO generated_dialogue_cache (
          generated_id, character_id, state_json, retrieved_card_ids_json, line,
          emotion_tag, voice_tag, motion_tag, memory_update_json, risk,
          style_score, novelty_score, spoiler_score, accepted, model_name, prompt_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            generated_id,
            state.get("character_id", "rapi"),
            json.dumps(state, ensure_ascii=False),
            json.dumps([card["card_id"] for card in cards], ensure_ascii=False),
            line,
            output.get("emotion"),
            output.get("voice_tag"),
            output.get("motion"),
            json.dumps(output.get("memory_update"), ensure_ascii=False)
            if output.get("memory_update") is not None
            else None,
            output.get("risk", "needs_review"),
            metrics.get("style_score"),
            metrics.get("novelty_score"),
            metrics.get("spoiler_score"),
            1 if accepted else 0,
            chat_model,
            "rapi_dialogue_v1",
        ),
    )
    conn.commit()
    return generated_id


def insert_qa_checks(conn: sqlite3.Connection, generated_id: str, checks: list[dict]) -> None:
    for check in checks:
        conn.execute(
            """
            INSERT INTO qa_checks (
              qa_id, generated_id, check_type, severity, result, notes, reviewer
            ) VALUES (?, ?, ?, ?, ?, ?, 'system')
            """,
            (
                f"qa_{uuid.uuid4().hex[:16]}",
                generated_id,
                check["check_type"],
                int(check["severity"]),
                check["result"],
                check["notes"],
            ),
        )
    conn.commit()


def main() -> None:
    args = parse_args()
    state = load_state(args.state)
    query = make_query(state, args.query)
    query_vector = embed_text(args.host, args.embed_model, query)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        candidate_card_ids: list[str] = []
        cards = retrieve_cards(conn, state, query_vector, args.embed_model, args.limit, candidate_card_ids)
        if not cards:
            raise RuntimeError("No RAG cards passed metadata/story gates.")
        log_retrieval(conn, state, query, candidate_card_ids, cards, args.embed_model)
        evaluation = best_of_n_generate(
            args.host,
            args.chat_model,
            state,
            cards,
            query_text=query,
            n=args.best_of,
            base_temperature=args.temperature,
            temperature_step=args.temperature_step,
        )
        output = evaluation["output"]
        auto_accepted = args.auto_accept_on_safe and should_auto_accept(
            evaluation,
            min_style=args.auto_accept_min_style,
            min_novelty=args.auto_accept_min_novelty,
            min_spoiler=args.auto_accept_min_spoiler,
        )
        accepted = bool(args.accept_cache or auto_accepted)
        generated_id = cache_generation(conn, state, cards, output, args.chat_model, accepted, evaluation)
        insert_qa_checks(conn, generated_id, evaluation["checks"])
        print(
            json.dumps(
                {
                    "generated_id": generated_id,
                    "retrieved_card_ids": [card["card_id"] for card in cards],
                    "output": output,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
