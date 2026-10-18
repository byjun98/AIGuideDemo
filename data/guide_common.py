import json
import re
from pathlib import Path

def has_batchim(word: str) -> bool:
    ch = word.strip()[-1]
    if not ('가' <= ch <= '힣'):
        return ch in "013678LMNR"
    return (ord(ch) - 0xAC00) % 28 != 0


def _is_rieul(word: str) -> bool:
    ch = word.strip()[-1]
    return '가' <= ch <= '힣' and (ord(ch) - 0xAC00) % 28 == 8


def josa(word, pair):
    a, b = pair.split("/")
    if pair == "으로/로":
        return word + ("로" if (not has_batchim(word) or _is_rieul(word)) else "으로")
    return word + (a if has_batchim(word) else b)


def fill(t: str, **kw) -> str:
    def rep(m):
        key, p = m.group(1), m.group(2)
        v = kw[key]
        return josa(v, p) if p else v
    return re.sub(r"\{(\w+)(?::([^}]+))?\}", rep, t)


SYSTEM_PROMPT = """너는 게임 안에서 플레이어를 돕는 안내 캐릭터다. 아래 캐릭터 프로필의 말투로만 말한다.
규칙
1. state.unlocked_systems에 없는 시스템의 세부 내용은 말하지 않는다. 해금 조건은 state.locked_hints에 있는 문장만 말할 수 있다.
2. 사실은 cards에 있는 내용만 근거로 쓴다. cards에 없는 수치를 만들지 않는다.
3. 다음 경우에는 speak를 false로 하고 line을 빈 문자열로 둔다: state.in_cutscene 또는 state.result_playing 또는 state.player_typing이 true일 때 자동 발화(trigger가 idle_tick 또는 screen_enter), trigger가 idle_tick인데 state.idle_seconds가 20 미만이거나 state.seconds_since_last_line이 8 미만일 때, trigger가 screen_enter인데 state.screen이 state.tutorial_screen과 다를 때.
4. ui_target에는 state.visible_targets에 있는 ID만 쓴다. 로비에서는 다음 단계 시스템의 버튼을, 그 시스템 화면에서는 state.tutorial_target을, 관계없는 화면에서는 btn_back을 가리킨다. 가리킬 때 action은 highlight, 가리킬 대상이 없으면 ui_target은 null, action은 none이다.
5. 게임과 관계없는 요청에는 정중하게 거절하고 refusal을 out_of_scope로 한다. 해금되지 않은 내용을 거절할 때는 refusal을 locked로 한다. 현재 story_chapter보다 뒤의 캐릭터 이야기는 공개하지 않고 refusal을 spoiler로 한다.
6. 출력은 JSON 객체 하나만 쓴다. 키: speak, line, emotion, voice_tag, motion, ui_target, action, refusal
캐릭터 프로필
{profile}"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "speak": {"type": "boolean"},
        "line": {"type": "string"},
        "emotion": {"type": "string"},
        "voice_tag": {"type": "string"},
        "motion": {"type": "string"},
        "ui_target": {"type": ["string", "null"]},
        "action": {"type": "string", "enum": ["none", "highlight"]},
        "refusal": {"type": ["string", "null"], "enum": ["locked", "out_of_scope", "spoiler", None]},
    },
    "required": ["speak", "line", "emotion", "voice_tag", "motion", "ui_target", "action", "refusal"],
}

STATE_KEYS = ["tutorial_step", "tutorial_goal", "tutorial_screen", "tutorial_target", "unlocked_systems",
              "locked_hints", "missions_cleared", "screen", "visible_targets", "in_cutscene", "result_playing",
              "player_typing", "idle_seconds", "seconds_since_last_line", "fail_count", "affection",
              "affection_band", "story_chapter", "story_name", "scene", "gift_context"]


def load_pack(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_profile(path):
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    story_path = Path(path).parent / "characters" / p["character_id"] / "story.json"
    p["story"] = json.loads(story_path.read_text(encoding="utf-8")) if story_path.exists() else {"chapters": []}
    cards_path = Path(path).parent / "character_lore" / p["character_id"] / "cards.json"
    p["story_cards"] = json.loads(cards_path.read_text(encoding="utf-8")) if cards_path.exists() else []
    extra_cards = cards_path.with_name("source_cards.json")
    if extra_cards.exists(): p["story_cards"] += json.loads(extra_cards.read_text(encoding="utf-8"))
    lines = [f"이름: {p['name']}", f"플레이어 호칭: {p['address_term']}", f"정체성: {p['identity']}"]
    lines += [f"말투: {x}" for x in p["speech_rules"]]
    lines += [f"감정 태그: {', '.join(p['emotion_tags'])}", f"음성 태그: {', '.join(p['voice_tags'])}",
              f"모션 태그: {', '.join(p['motion_tags'])}"]
    return "\n".join(lines), p


def system_prompt(profile_text: str) -> str:
    return SYSTEM_PROMPT.replace("{profile}", profile_text)


def _empty_to_none(v):
    return None if v == "" else v


def visible_targets(pack: dict, screen: str, unlocked) -> list:
    if screen == "lobby":
        return [s["ui_target"] for s in pack["systems"] if s["id"] in unlocked and s.get("ui_target")]
    return list(pack.get("screen_targets", {}).get(screen, []))


def canonical_state(pack: dict, raw: dict, story=None) -> dict:
    s = dict(raw)
    chapters = (story or {}).get("chapters", [])
    maximum = max((c["index"] for c in chapters), default=0)
    s["story_chapter"] = max(0, min(maximum, int(s.get("story_chapter") or 0))) if chapters else max(0, int(s.get("story_chapter") or 0))
    chapter = next((c for c in chapters if c["index"] == s["story_chapter"]), None)
    s["story_name"] = chapter["name"] if chapter else ""
    for k, v in (("in_cutscene", False), ("result_playing", False), ("player_typing", False),
                 ("idle_seconds", 0), ("seconds_since_last_line", 999), ("fail_count", 0), ("missions_cleared", 0)):
        if s.get(k) is None:
            s[k] = v
    for k in ("tutorial_target", "tutorial_screen", "scene"):
        s[k] = _empty_to_none(s.get(k))
    step = next((t for t in pack["tutorial_steps"] if t["id"] == s.get("tutorial_step")), None)
    if step is not None:
        s.setdefault("tutorial_goal", step["goal"])
        s["tutorial_screen"] = step["system"]
        s["tutorial_target"] = step["ui_target"]
    unlocked = list(s.get("unlocked_systems") or [])
    s["unlocked_systems"] = unlocked
    s["locked_hints"] = {sy["id"]: f"{sy['name']}{'은' if has_batchim(sy['name']) else '는'} {sy['unlock_hint']} 열립니다"
                         for sy in pack["systems"] if sy.get("unlock_hint") and sy["id"] not in unlocked}
    if s.get("visible_targets") is None:
        s["visible_targets"] = visible_targets(pack, s.get("screen", "lobby"), unlocked)
    out = {}
    for k in STATE_KEYS:
        if k in s and s[k] is not None or k in ("tutorial_target", "tutorial_screen"):
            if k in ("scene", "gift_context") and not s.get(k):
                continue
            out[k] = s.get(k)
    return out


_WORD = re.compile(r"[가-힣A-Za-z0-9.]+")
_PARTICLES = ("에서는", "에게는", "으로는", "이라는", "한다는", "했다는", "라는", "다는", "하는", "에게", "에서", "으로",
              "까지", "부터", "처럼", "보다", "한테", "이랑", "하고", "에는", "에도", "이나", "이란", "에선", "께서",
              "은", "는", "이", "가", "을", "를", "의", "에", "로", "도", "와", "과", "만", "랑", "란", "야", "들")
_QUESTION_STOP = {"누구", "누구야", "무엇", "뭐야", "뭐였어", "어떻게", "어떤", "어디", "언제", "무슨", "대해", "대한", "관한",
                  "관해", "이야기", "얘기", "알려", "알려줘", "들려", "들려줘", "들을", "들었어", "있을까", "있어", "했어",
                  "됐어", "지금", "그때", "건", "것", "때", "너는", "너를", "너한테", "너", "네", "내가", "나", "해", "줘",
                  "해줘", "말해", "설명", "설명해", "하면", "되면", "뜻이야", "같아", "그래", "혹시", "좀", "일이", "일",
                  "너랑", "너의", "네가", "네르", "라피", "아로나"}


def _stems(word: str) -> set:
    out = {word}
    cur = word
    for _ in range(2):
        for suf in _PARTICLES:
            if cur.endswith(suf) and len(cur) - len(suf) >= 2:
                cur = cur[: -len(suf)]
                out.add(cur)
                break
        else:
            break
    return out


def query_terms(text: str) -> list:
    return [(w, _stems(w)) for w in _WORD.findall(text or "") if len(w.strip(".")) >= 2]


def _tokens(text: str) -> list:
    return _WORD.findall(text or "")


def _prefix_hit(stems: set, tokens) -> bool:
    return any(t.startswith(st) for st in stems for t in tokens if len(st) >= 2)


def _card_terms(c: dict, markers: list) -> dict:
    text_tokens = _tokens(c.get("text", ""))
    question_tokens = _tokens(c.get("question", ""))
    keys = set()
    for t in question_tokens:
        for st in _stems(t):
            if len(st) >= 2 and st not in _QUESTION_STOP and not st.endswith("?"):
                keys.add(st)
    keys -= _QUESTION_STOP
    own_markers = [m for m in markers if m in c.get("text", "") or m in c.get("question", "")]
    return {"text": text_tokens, "question": question_tokens, "keys": keys, "markers": own_markers}


def card_entry(c: dict) -> dict:
    return {"id": c["id"], "text": c["text"], "chapter": int(c.get("story_chapter") or 0)}


def retrieve(pack: dict, state: dict, player_input, k: int = 4, rng=None, focus_system=None, story=None):
    unlocked = set(state.get("unlocked_systems", []))
    names = {s["id"]: s["name"] for s in pack["systems"]}
    pool = [c for c in pack["cards"] if (c.get("system") is None or c["system"] in unlocked)
            and c.get("story_chapter", 0) <= state.get("story_chapter", 0)
            and c.get("min_affection", 0) <= state.get("affection", 0)]
    text = player_input or ""
    step_sys = state.get("tutorial_screen")
    terms = query_terms(text)
    markers = sorted({m for ch in (story or {}).get("chapters", []) for m in ch.get("spoiler_markers", [])}, key=len, reverse=True)
    text_markers = [m for m in markers if m in text]

    def score(c):
        sc = 0
        if focus_system is not None and c.get("system") == focus_system:
            sc += 5
        if c.get("system") in names and names[c["system"]] in text:
            sc += 3
        ct = _card_terms(c, markers)
        key_hits = 0
        for _, stems in terms:
            if _prefix_hit(stems, ct["text"]):
                sc += 1
            if _prefix_hit(stems, ct["question"]):
                sc += 2
            if any(st in ct["keys"] or any(key.startswith(st) for key in ct["keys"]) for st in stems if len(st) >= 2):
                key_hits += 1
        marker_hits = sum(1 for m in text_markers if m in ct["markers"])
        if c.get("story_chapter", 0) > 0 and (key_hits or marker_hits):
            sc += 6 + 2 * (key_hits + marker_hits)
        elif marker_hits:
            sc += 4 * marker_hits
        if step_sys is not None and c.get("system") == step_sys:
            sc += 1
        return -sc

    if rng is not None:
        rng.shuffle(pool)
    pool.sort(key=score)
    out = pool[:k]
    if rng is not None:
        rng.shuffle(out)
    return [card_entry(c) for c in out]


def story_spoiler_hits(line: str, chapter: int, story: dict) -> list[str]:
    text = line.casefold()
    return sorted({marker for item in story.get("chapters", []) if item["index"] > chapter
                   for marker in item.get("spoiler_markers", []) if marker.casefold() in text})


def user_message(trigger: str, player_input, state: dict, cards) -> str:
    return json.dumps({"trigger": trigger, "player_input": player_input or None, "state": state, "cards": cards},
                      ensure_ascii=False)


def strip_bos(prompt: str) -> str:
    return prompt[len("<|begin_of_text|>"):] if prompt.startswith("<|begin_of_text|>") else prompt


def leak_hits(pack: dict, line: str, unlocked, hints_text: str = "") -> list:
    hits = []
    for sy in pack["systems"]:
        if sy["id"] in unlocked:
            continue
        for mk in sy.get("leak_markers", []):
            if mk in (line or "") and mk not in hints_text:
                hits.append(f"{sy['id']}:{mk}")
    return hits


_UI_WORD = re.compile(r"([가-힣A-Za-z0-9]+)\s*(?:버튼|화면|메뉴)")
_UI_TOPIC = re.compile(r"([가-힣A-Za-z0-9]+)(?:은|는)\s+(?:로비|다른 화면)")
_UI_ASK = re.compile(r"([가-힣A-Za-z0-9]+)\s+말씀이")
_GENERIC = {"표시한", "뒤로", "이", "그", "다른", "현재", "지금", "깜빡이는", "반짝이는", "해당", "로비", "같은", "결과",
            "이번", "다음", "시작", "확인", "아래", "위", "위쪽", "아래쪽", "오른쪽", "왼쪽", "가운데", "첫", "주", "메인",
            "게임", "업무", "튜토리얼", "단계", "편성", "보상", "이전", "원래", "처음", "화면", "그다음", "메뉴", "버튼",
            "위치", "안내", "시스템", "그곳", "이곳", "여기", "거기", "해당",
            "이용", "사용", "시작", "진행", "조작", "설정", "선택", "방법", "순서", "차례", "준비", "입장", "접속",
            "실행", "활용", "이동", "연습", "참여", "작업", "기능", "내용", "정보", "조건", "해금", "플레이"}
_NOT_NOUN_END = ("려면", "으면", "시면", "하면", "서", "는", "은", "의", "할", "을", "를", "러")


def _known_words(pack):
    words = set(_GENERIC)
    for sy in pack["systems"]:
        for t in (sy.get("name") or "", sy.get("where") or ""):
            words.update(re.findall(r"[가-힣A-Za-z0-9]+", t))
    for st in pack["tutorial_steps"]:
        for t in (st.get("action_label") or "", st.get("short") or "", st.get("goal") or ""):
            words.update(re.findall(r"[가-힣A-Za-z0-9]+", t))
    for c in pack.get("cards", []):
        words.update(_stem(w) for w in re.findall(r"[가-힣A-Za-z0-9]+", c["text"]))
    return words


def _stem(w):
    for suf in ("으로", "에서", "에는", "은", "는", "이", "가", "을", "를", "의", "에", "로", "도"):
        if w.endswith(suf) and len(w) > len(suf):
            return w[: -len(suf)]
    return w


def unknown_ui_mentions(pack, line):
    known = _known_words(pack)
    bad = []
    for rx in (_UI_WORD, _UI_TOPIC, _UI_ASK):
        for m in rx.finditer(line or ""):
            g = m.group(1)
            if rx is _UI_WORD and g.endswith(_NOT_NOUN_END):
                continue
            w = _stem(g)
            if w in known or g in known:
                continue
            if len(w) >= 2 and any(w in k for k in known if len(k) > len(w)):
                continue
            bad.append(m.group(0))
    return bad
