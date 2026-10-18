from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "docs" / "라피대사.md"
DEFAULT_OUTPUT = ROOT / "rag" / "data" / "namu_dialogue_corpus.csv"

NAMU_BASE_URL = (
    "https://namu.wiki/w/%EB%9D%BC%ED%94%BC"
    "(%EC%8A%B9%EB%A6%AC%EC%9D%98%20%EC%97%AC%EC%8B%A0:%20%EB%8B%88%EC%BC%80)#s-6"
)
NAMU_RH_URL = (
    "https://namu.wiki/w/%EB%9D%BC%ED%94%BC%20:%20"
    "%EB%A0%88%EB%93%9C%20%ED%9B%84%EB%93%9C#s-6"
)

BASE_URL_MARKER = "EC%8A%B9%EB%A6%AC%EC%9D%98"
RH_URL_MARKER = "%EB%A0%88%EB%93%9C%20%ED%9B%84%EB%93%9C"


@dataclass(frozen=True)
class Variant:
    key: str
    label: str
    section: str
    url: str
    source_key: str
    source_title: str
    required_flags: tuple[str, ...]
    spoiler_level: int
    notes: str


VARIANTS: dict[str, Variant] = {
    "base": Variant(
        key="base",
        label="Base Rapi",
        section="라피 §6 대사",
        url=NAMU_BASE_URL,
        source_key="namu_wiki_rapi_base_dialogue",
        source_title="나무위키 라피(승리의 여신:니케) 대사 표",
        required_flags=("chapter_01_cleared",),
        spoiler_level=0,
        notes="기본 라피 보이스 코퍼스. 후반/이벤트 라피와 절대 혼용 금지.",
    ),
    "rh_basic": Variant(
        key="rh_basic",
        label="Rapi: Red Hood basic",
        section="라피:레드 후드 §6.1 기본",
        url=NAMU_RH_URL,
        source_key="namu_wiki_rapi_red_hood_basic_dialogue",
        source_title="나무위키 라피:레드 후드 §6.1 기본 대사 표",
        required_flags=(
            "chapter_34_rapi_inheritance_seen",
            "character_variant_rapi_red_hood_unlocked",
        ),
        spoiler_level=5,
        notes="Ch.34 계승 후 라피:레드 후드 기본 톤. 초기/기본 라피로 누출 금지.",
    ),
    "rh_red_flavor": Variant(
        key="rh_red_flavor",
        label="Rapi: Red Hood Red Flavor",
        section="라피:레드 후드 §6.2 레드 플레이버",
        url=NAMU_RH_URL,
        source_key="namu_wiki_rapi_red_hood_red_flavor_dialogue",
        source_title="나무위키 라피:레드 후드 §6.2 레드 플레이버 대사 표",
        required_flags=(
            "chapter_34_rapi_inheritance_seen",
            "character_variant_rapi_red_hood_unlocked",
            "costume_red_flavor_seen",
        ),
        spoiler_level=5,
        notes="여름 수영복 코스튬. 직설/플러팅 톤. 일반 캠페인 검색에서 격리.",
    ),
    "rh_cherryseed_red": Variant(
        key="rh_cherryseed_red",
        label="Rapi: Red Hood Cherryseed Red",
        section="라피:레드 후드 §6.3 체리시드 레드",
        url=NAMU_RH_URL,
        source_key="namu_wiki_rapi_red_hood_cherryseed_red_dialogue",
        source_title="나무위키 라피:레드 후드 §6.3 체리시드 레드 대사 표",
        required_flags=(
            "chapter_34_rapi_inheritance_seen",
            "character_variant_rapi_red_hood_unlocked",
            "costume_cherryseed_red_seen",
            "event_yes_my_commander_seen",
        ),
        spoiler_level=5,
        notes="YES MY COMMANDER 계열 침실/사적 코미디 톤. 일반 출력 절대 금지.",
    ),
}


@dataclass(frozen=True)
class SituationTag:
    slug: str
    scene_id: str
    affection_band_id: str
    min_aff: int
    max_aff: int
    emotion_tag: str
    voice_tag: str
    motion_tag: str
    dialogue_function: str
    summary_kr: str
    voice_features_kr: str


SITUATION_TAGS: dict[str, SituationTag] = {
    "획득": SituationTag(
        "acquisition", "lobby_morning", "cautious", 0, 20,
        "neutral", "calm_brief", "salute", "greeting",
        "획득 직후 첫 인사. 명령 대기 보고 톤.",
        "짧고 공적, 명령 수령 의지 표현",
    ),
    "대화": SituationTag(
        "talk", "lobby_morning", "cautious", 0, 20,
        "neutral", "calm_brief", "idle", "idle",
        "로비 대기 중 짧은 대사. 임무 중심.",
        "절제된 군인 톤, 1문장 권장",
    ),
    "방치": SituationTag(
        "idle_neglect", "lobby_evening", "cautious", 0, 20,
        "neutral", "calm_brief", "idle", "idle",
        "장시간 무응답 시 짧은 점검 발화.",
        "지휘관 호출 짧은 일성, 비난 톤 금지",
    ),
    "호감도 10 대사": SituationTag(
        "bond10_talk", "lobby_morning", "special_trust", 81, 100,
        "gentle", "warm_reserved", "soft_smile", "affection_response",
        "Bond10 최대 호감 단계 일상 대사. 절제된 보호/곁에 있겠다는 신뢰 표현.",
        "호칭은 지휘관 유지, 친밀감은 어휘가 아니라 톤으로",
    ),
    "호감도 10 방치": SituationTag(
        "bond10_idle", "lobby_evening", "special_trust", 81, 100,
        "soft_smile", "warm_reserved", "idle", "affection_response",
        "Bond10 idle. 조용히 곁에 있음을 알리는 짧은 발화.",
        "기다림에 부정 감정 없음, 안정감 강조",
    ),
    "필드 이동": SituationTag(
        "field_move", "field_move", "cautious", 0, 20,
        "determined", "mission_report", "battle_ready", "battle_result",
        "필드 이동 명령 복창.",
        "이동 명령에 대한 짧은 보고",
    ),
    "필드 터치": SituationTag(
        "field_touch", "field_move", "cautious", 0, 20,
        "neutral", "calm_brief", "salute", "idle",
        "필드 터치 응답.",
        "명령 대기 짧은 응답",
    ),
    "적 조우": SituationTag(
        "encounter", "field_encounter", "cautious", 0, 20,
        "stern", "mission_report", "battle_ready", "battle_result",
        "적 조우 시 교전 개시 보고.",
        "전투 진입 결의, 짧은 외침",
    ),
    "스쿼드 편성": SituationTag(
        "squad_deploy", "squad_deploy", "cautious", 0, 20,
        "determined", "mission_report", "salute", "idle",
        "스쿼드 출격 합류 보고.",
        "출격 의지 명료한 짧은 보고",
    ),
    "궁극기 준비": SituationTag(
        "ult_ready", "combat_active", "cautious", 0, 20,
        "determined", "mission_report", "battle_ready", "battle_result",
        "궁극기 충전 완료 신호.",
        "준비 완료 1단어/짧은 외침",
    ),
    "궁극기": SituationTag(
        "ult", "combat_active", "cautious", 0, 20,
        "determined", "mission_report", "battle_ready", "battle_result",
        "궁극기 발동.",
        "결의/명령형 짧은 외침",
    ),
    "풀 버스트": SituationTag(
        "full_burst", "combat_active", "cautious", 0, 20,
        "determined", "mission_report", "battle_ready", "battle_result",
        "풀 버스트 명령.",
        "전방 사격 외침, 임팩트형",
    ),
    "레벨업": SituationTag(
        "levelup", "lobby_morning", "friendly", 21, 50,
        "neutral", "calm_brief", "nod", "affection_response",
        "성장 데이터 보고형 코멘트.",
        "분석적/관찰적 어조, 자기 데이터 인식",
    ),
    "선물": SituationTag(
        "gift", "gift_received", "friendly", 21, 50,
        "soft_smile", "warm_reserved", "nod", "gift_response",
        "선물 수령 시 절제된 감사.",
        "감사를 짧게, 과한 애교 금지",
    ),
    "호감도 상승": SituationTag(
        "affection_up", "advise_session", "friendly", 21, 50,
        "soft_smile", "warm_reserved", "nod", "affection_response",
        "호감도 상승 시 반응. 보답/기대 표현.",
        "고마움/책임감 톤, 직설적 연애 표현 금지",
    ),
    "전투 시작": SituationTag(
        "battle_start", "battle_start", "cautious", 0, 20,
        "determined", "mission_report", "battle_ready", "battle_result",
        "전투 시작 외침.",
        "교전 개시 짧은 보고",
    ),
    "장전": SituationTag(
        "reload", "combat_active", "cautious", 0, 20,
        "neutral", "calm_brief", "battle_ready", "battle_result",
        "재장전 작업 보고.",
        "짧은 작업 외침",
    ),
    "적 처치": SituationTag(
        "kill", "combat_active", "cautious", 0, 20,
        "determined", "mission_report", "battle_ready", "battle_result",
        "적 격파 확인.",
        "타겟 클리어 보고",
    ),
    "사망": SituationTag(
        "down", "combat_down", "cautious", 0, 20,
        "worried", "vulnerable_short", "idle", "battle_result",
        "전투 무력화 시 동료에게 후방 부탁.",
        "취약성 짧게 노출, 회피 의지 표현",
    ),
    "승리": SituationTag(
        "victory", "after_battle_win", "cautious", 0, 20,
        "relieved", "calm_brief", "salute", "battle_result",
        "전투 승리 후 마무리 보고.",
        "다음 작전 이동 의지",
    ),
    "전초기지": SituationTag(
        "outpost", "outpost", "friendly", 21, 50,
        "neutral", "calm_brief", "idle", "idle",
        "전초기지 환경 idle 코멘트.",
        "환경/숙소 평가 짧게",
    ),
}

SITUATION_PREFIXES = sorted(SITUATION_TAGS.keys(), key=len, reverse=True)


def find_tag(situation: str) -> SituationTag | None:
    for prefix in SITUATION_PREFIXES:
        if situation.startswith(prefix):
            return SITUATION_TAGS[prefix]
    return None


_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")


def strip_md_links(text: str) -> str:
    return _LINK_RE.sub(r"\1", text)


def normalize_dialogue(text: str) -> str:
    text = strip_md_links(text)
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


CSV_FIELDS = [
    "line_id", "character_id", "speaker", "raw_text", "language",
    "source_key", "source_title", "source_url", "source_type",
    "reliability_tier", "rights_scope", "source_location",
    "scene_id", "affection_band_id", "min_affection", "max_affection",
    "spoiler_level", "canon_tier", "emotion_tag", "voice_tag", "motion_tag",
    "dialogue_function", "required_flags", "forbidden_flags",
    "short_excerpt", "summary_kr", "voice_features_kr",
    "forbidden_notes", "notes", "is_verbatim_allowed", "is_training_allowed",
]


def detect_variant(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("## ") and "대사" in stripped:
        if BASE_URL_MARKER in stripped and RH_URL_MARKER not in stripped:
            return "base"
        return None
    if stripped.startswith("### "):
        if "기본" in stripped:
            return "rh_basic"
        if "레드 플레이버" in stripped:
            return "rh_red_flavor"
        if "체리시드 레드" in stripped:
            return "rh_cherryseed_red"
    return None


def parse_md(md_path: Path) -> list[tuple[Variant, str, str]]:
    rows: list[tuple[Variant, str, str]] = []
    current: Variant | None = None
    table_state = "none"
    for line in md_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        is_table_row = stripped.startswith("|")
        if not is_table_row:
            table_state = "none"
            variant_key = detect_variant(line)
            if variant_key is not None:
                current = VARIANTS.get(variant_key)
            elif stripped.startswith("## ") and current is not None:
                current = None if "레드 후드" not in stripped else current
            continue
        if current is None:
            continue
        cells = [c.strip() for c in stripped.split("|")]
        cells = [c for c in cells if c != ""]
        if not cells:
            continue
        if table_state == "none":
            table_state = "header"
            continue
        if table_state == "header":
            if all(re.match(r"^[-:\s]+$", c) for c in cells):
                table_state = "data"
            continue
        if table_state == "data" and len(cells) >= 2:
            situation = cells[0]
            dialogue_raw = "|".join(cells[1:])
            rows.append((current, situation, dialogue_raw))
    return rows


def build_csv_rows(parsed: list[tuple[Variant, str, str]]) -> list[dict]:
    output: list[dict] = []
    counters: dict[tuple[str, str], int] = {}
    for variant, situation, dialogue_raw in parsed:
        tag = find_tag(situation)
        if tag is None:
            print(f"[warn] unmapped situation skipped: variant={variant.key} situation={situation!r}")
            continue
        clean_dialogue = normalize_dialogue(dialogue_raw)
        if not clean_dialogue:
            continue
        key = (variant.key, tag.slug)
        counters[key] = counters.get(key, 0) + 1
        idx = counters[key]
        line_id = f"namu_{variant.key}_{tag.slug}_{idx:02d}"
        excerpt_chars = clean_dialogue[:12]
        short_excerpt = f"{excerpt_chars}..." if len(clean_dialogue) > 12 else excerpt_chars
        forbidden_notes = (
            "원문 그대로 출력 금지. 말투/길이/어휘 패턴 추출용 코퍼스. "
            f"{variant.label} 톤이 다른 변형으로 새지 않도록 격리."
        )
        notes = f"{variant.section} | namu wiki C-tier reference"
        output.append({
            "line_id": line_id,
            "character_id": "rapi",
            "speaker": "라피",
            "raw_text": clean_dialogue,
            "language": "ko",
            "source_key": variant.source_key,
            "source_title": variant.source_title,
            "source_url": variant.url,
            "source_type": "wiki",
            "reliability_tier": "C",
            "rights_scope": "private_reference",
            "source_location": f"{variant.section} / {situation}",
            "scene_id": tag.scene_id,
            "affection_band_id": tag.affection_band_id,
            "min_affection": tag.min_aff,
            "max_affection": tag.max_aff,
            "spoiler_level": variant.spoiler_level,
            "canon_tier": "community",
            "emotion_tag": tag.emotion_tag,
            "voice_tag": tag.voice_tag,
            "motion_tag": tag.motion_tag,
            "dialogue_function": tag.dialogue_function,
            "required_flags": "|".join(variant.required_flags),
            "forbidden_flags": "",
            "short_excerpt": short_excerpt,
            "summary_kr": f"[{variant.label} / {situation}] {tag.summary_kr}",
            "voice_features_kr": tag.voice_features_kr,
            "forbidden_notes": forbidden_notes,
            "notes": notes,
            "is_verbatim_allowed": 0,
            "is_training_allowed": 1,
        })
    return output


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    parsed = parse_md(args.input)
    rows = build_csv_rows(parsed)
    write_csv(rows, args.output)

    by_variant: dict[str, int] = {}
    for r in rows:
        v = r["source_key"]
        by_variant[v] = by_variant.get(v, 0) + 1
    print(f"input: {args.input}")
    print(f"output: {args.output}")
    print(f"total_rows: {len(rows)}")
    for v, c in sorted(by_variant.items()):
        print(f"  {v}: {c}")


if __name__ == "__main__":
    main()
