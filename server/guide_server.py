import json, os, sys, time
from collections import deque
from threading import Lock
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(os.environ.get("AIGD_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "data"))
from guide_common import (RESPONSE_SCHEMA, canonical_state, fill, leak_hits, load_pack, load_profile, unknown_ui_mentions,
                          retrieve, story_spoiler_hits, strip_bos, system_prompt, user_message)

PACK_PATH = Path(os.environ.get("AIGD_PACK", ROOT / "data/game_pack_counters.json"))
PROFILE_DIR = ROOT / "data"
ADAPTER_URL = os.environ.get("AIGD_ADAPTER_URL", "http://127.0.0.1:8083")
ADAPTER_ORDER = json.loads(os.environ.get("AIGD_ADAPTER_ORDER", '["rapi", "arona", "ner"]'))
_loaded_ids = None


def loaded_adapter_ids():
    global _loaded_ids
    if not _loaded_ids:
        try:
            response = requests.get(ADAPTER_URL + "/lora-adapters", timeout=5)
            response.raise_for_status()
            _loaded_ids = [a["id"] for a in response.json()]
        except Exception:
            return []
    return _loaded_ids
ENDPOINTS = {
    "base": os.environ.get("AIGD_BASE_URL", "http://127.0.0.1:8081"),
    "lora": os.environ.get("AIGD_LORA_URL", "http://127.0.0.1:8082"),
}
LOG = ROOT / "logs/server_turns.jsonl"

PACK = load_pack(PACK_PATH)
PACKS = {PACK["game_id"]: PACK}
for _f in sorted((ROOT / "data").glob("pack_*.json")):
    _p = load_pack(_f); PACKS[_p["game_id"]] = _p
SYS_TARGET = {s["id"]: s["ui_target"] for s in PACK["systems"]}
REQ_KEYS = RESPONSE_SCHEMA["required"]
SILENT = {"speak": False, "line": "", "emotion": "neutral", "voice_tag": "calm_brief", "motion": "idle",
          "ui_target": None, "action": "none", "refusal": None}

_profiles = {}
_recent_lines = {}
_history_lock = Lock()


def sampling_policy(trigger, text, state, prof, pack):
    settings = prof.get("generation", {})
    if not settings.get("diversity_enabled") or trigger != "player_utterance":
        return 0.3, 1
    text = text or ""
    if story_spoiler_hits(text, state.get("story_chapter", 0), prof.get("story", {})):
        return 0.3, 1
    if any(s["name"] in text or s["id"] in text for s in pack["systems"]):
        return 0.3, 1
    casual = settings.get("casual_markers", ["안녕", "반가", "자기소개", "넌 누구", "너는 누구", "좋아해", "기분", "고마워", "피곤", "쉬자", "보고 싶"])
    if text in prof.get("casual_questions", []) or any(word in text for word in casual):
        return min(0.8, max(0.3, settings.get("casual_temperature", 0.75))), 2
    return min(0.5, settings.get("fact_temperature", 0.3)), 1


def remember_line(character_id, line):
    if line:
        with _history_lock:
            _recent_lines.setdefault(character_id, deque(maxlen=10)).append(line)


def novelty(character_id, line):
    with _history_lock:
        recent = list(_recent_lines.get(character_id, ()))
    pairs = set(line[i:i + 2] for i in range(len(line) - 1))
    def overlap(old):
        other = set(old[i:i + 2] for i in range(len(old) - 1))
        return len(pairs & other) / len(pairs | other) if pairs | other else float(line == old)
    return 1 - max((overlap(old) for old in recent), default=0)


def profile(character_id: str):
    if character_id not in _profiles:
        text, p = load_profile(PROFILE_DIR / f"character_{character_id}.json")
        templates_path = PROFILE_DIR / "characters" / character_id / "templates.json"
        if templates_path.exists():
            templates = json.loads(templates_path.read_text(encoding="utf-8"))
            p["casual_questions"] = [question for scenes in templates.get("smalltalk_by_scene", {}).values()
                                     for questions in scenes.values() for question in questions]
        _profiles[character_id] = (system_prompt(text), p)
    return _profiles[character_id]


_tok = None


def build_prompt(system: str, user: str) -> str:
    global _tok
    if _tok is None:
        from transformers import AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(str(ROOT / "models/base/kanana-1.5-2.1b-instruct-2505"))
    p = _tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                 tokenize=False, add_generation_prompt=True)
    return strip_bos(p)


def call_llm(model: str, system: str, user: str, use_schema: bool = True, temperature: float = 0.3,
             seed: Optional[int] = None, timeout: float = 30):
    body = {"prompt": build_prompt(system, user), "temperature": temperature, "n_predict": 200,
            "cache_prompt": True, "stop": ["<|eot_id|>"]}
    if seed is not None:
        body["seed"] = seed
    if use_schema:
        body["json_schema"] = RESPONSE_SCHEMA
    t0 = time.perf_counter()
    if model.startswith("lora:"):
        name = model.split(":", 1)[1]
        ids = loaded_adapter_ids()
        sel = ADAPTER_ORDER.index(name) if name in ADAPTER_ORDER else -1
        if name != "base" and sel not in ids:
            raise RuntimeError(f"어댑터 {name}가 서버에 없습니다 (올라간 id: {ids})")
        body["lora"] = [{"id": i, "scale": 1.0 if i == sel else 0.0} for i in ids]
        url = ADAPTER_URL
    else:
        url = ENDPOINTS[model]
    r = requests.post(url + "/completion", json=body, timeout=timeout)
    r.raise_for_status()
    dt = time.perf_counter() - t0
    j = r.json()
    return j.get("content", ""), dt, j.get("timings", {})


def parse_lenient(raw: str):
    try:
        return json.loads(raw), "strict"
    except Exception:
        pass
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        s = s.rsplit("```", 1)[0]
    i, k = s.find("{"), s.rfind("}")
    if i >= 0 and k > i:
        try:
            return json.loads(s[i:k + 1]), "lenient"
        except Exception:
            pass
    return None, "fail"


def validate(resp: dict, state: dict, prof: dict, pack: Optional[dict] = None, trigger: Optional[str] = None):
    issues = []
    resp = {**SILENT, **{k: resp.get(k) for k in REQ_KEYS if k in resp}}
    if not isinstance(resp.get("line"), str):
        issues.append("line_not_string")
        resp["line"], resp["speak"] = "", False
    unlocked = set(state.get("unlocked_systems", []))
    pack = pack or PACK
    sys_target = {s["id"]: s["ui_target"] for s in pack["systems"] if s.get("ui_target")}
    locked_targets = {sys_target[s] for s in sys_target if s not in unlocked}
    allowed = set(state.get("visible_targets") or []) - locked_targets
    a = prof.get("address_term", "")
    fb = prof.get("fallback_lines", {})
    t = resp.get("ui_target")
    if t and t not in allowed:
        issues.append(f"ui_target_not_allowed:{t}")
        resp["ui_target"], resp["action"] = None, "none"
        if resp.get("speak"):
            resp["line"] = fill(fb.get("no_target", fb.get("default", "")), a=a)
    if resp.get("ui_target") and resp.get("action") != "highlight":
        resp["action"] = "highlight"
    if not resp.get("ui_target"):
        resp["action"] = "none"
    if not resp.get("speak"):
        resp["line"] = ""
    hints = " ".join((state.get("locked_hints") or {}).values())
    hits = leak_hits(pack, resp["line"], unlocked, hints)
    if hits:
        issues += [f"locked_fact:{h}" for h in hits]
        resp["line"] = fill(fb.get("default", ""), a=a)
        resp["refusal"] = "locked"
    if resp.get("speak") and not hits:
        made_up = unknown_ui_mentions(pack, resp["line"])
        if made_up:
            issues += [f"unknown_ui:{m}" for m in made_up]
            if trigger != "player_utterance" and resp.get("ui_target"):
                resp["line"] = fill(fb.get("point", fb.get("no_target", "")), a=a)
            else:
                resp["line"] = fill(fb.get("out_of_scope", fb.get("default", "")), a=a)
                resp["refusal"], resp["ui_target"], resp["action"] = "out_of_scope", None, "none"
    spoilers = story_spoiler_hits(resp["line"], state.get("story_chapter", 0), prof.get("story", {}))
    if spoilers:
        issues += [f"story_spoiler:{marker}" for marker in spoilers]
        resp["line"] = fill(fb.get("spoiler", fb.get("default", "")), a=a)
        resp["refusal"], resp["ui_target"], resp["action"] = "spoiler", None, "none"
    resp["risk"] = "safe" if not issues else "replaced"
    return resp, issues


class GuideRequest(BaseModel):
    trigger: str
    player_input: Optional[str] = None
    state: dict
    character_id: str = "rapi"
    model: str = "adapter"
    use_schema: bool = True
    game_id: Optional[str] = None


app = FastAPI(title="AIGuideDemo")


@app.get("/health")
def health():
    out = {}
    for k, u in list(ENDPOINTS.items()) + [("adapter", ADAPTER_URL)]:
        try:
            out[k] = requests.get(u + "/health", timeout=2).json()
        except Exception as e:
            out[k] = str(e)
    return out


def run_turn(trigger, player_input, raw_state, character_id="rapi", model="adapter", use_schema=True,
             temperature=0.3, seed=None, game_id=None, runtime_diversity=False):
    t0 = time.perf_counter()
    pack = PACKS.get(game_id or "", PACK)
    state = canonical_state(pack, raw_state)
    prof, cards, raw, llm_s, timings = {}, [], "", 0, {}
    try:
        system, prof = profile(character_id)
        pack = {**pack, "cards": pack["cards"] + prof.get("story_cards", [])}
        state = canonical_state(pack, raw_state, prof.get("story"))
        if model == "adapter":
            model = "lora:" + prof.get("lora_id", character_id)
        cards = retrieve(pack, state, player_input, story=prof.get("story"))
        user = user_message(trigger, player_input, state, cards)
        temperature, candidate_count = sampling_policy(trigger, player_input, state, prof, pack) if runtime_diversity else (temperature, 1)
        raw, llm_s, timings = call_llm(model, system, user, use_schema, temperature, seed)
    except (requests.RequestException, RuntimeError, KeyError, OSError, ValueError) as exc:
        fallback = fill(prof.get("fallback_lines", {}).get("default", ""), a=prof.get("address_term", ""))
        resp = {**SILENT, "speak": bool(fallback), "line": fallback, "risk": "replaced"}
        resp["debug"] = {"model": model, "parse": "not_run", "issues": ["backend_error"],
                         "error": str(exc), "card_ids": [c["id"] for c in cards], "llm_ms": 0,
                         "total_ms": round((time.perf_counter() - t0) * 1000), "timings": {}}
        return resp, raw, state
    parsed, parse_mode = parse_lenient(raw)
    resp, issues = validate(parsed if isinstance(parsed, dict) else SILENT, state, prof, pack, trigger)
    if not isinstance(parsed, dict):
        issues.append("parse_fail")
        resp["risk"] = "replaced"
    candidates = 1
    remaining = 30 - (time.perf_counter() - t0)
    if candidate_count > 1 and remaining > 1:
        try:
            other_raw, other_s, other_timings = call_llm(model, system, user, use_schema, temperature,
                                                        None if seed is None else seed + 1, timeout=remaining)
            candidates += 1
            llm_s += other_s
            other_parsed, other_mode = parse_lenient(other_raw)
            if isinstance(other_parsed, dict):
                other, other_issues = validate(other_parsed, state, prof, pack, trigger)
                if not other_issues and (issues or novelty(character_id, other["line"]) > novelty(character_id, resp["line"])):
                    resp, issues, raw, parse_mode, timings = other, other_issues, other_raw, other_mode, other_timings
        except (requests.RequestException, RuntimeError, KeyError, OSError, ValueError):
            pass
    if runtime_diversity and resp.get("speak"):
        remember_line(character_id, resp["line"])
    resp["debug"] = {"model": model, "parse": parse_mode, "issues": issues,
                     "temperature": temperature, "candidates": candidates,
                     "card_ids": [c["id"] for c in cards], "llm_ms": round(llm_s * 1000),
                     "total_ms": round((time.perf_counter() - t0) * 1000), "timings": timings}
    return resp, raw, state


@app.post("/guide/generate")
def generate(req: GuideRequest):
    resp, raw, _ = run_turn(req.trigger, req.player_input, req.state, req.character_id, req.model, req.use_schema,
                            game_id=req.game_id, runtime_diversity=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), "req": req.model_dump(), "resp": resp, "raw": raw},
                           ensure_ascii=False) + "\n")
    return resp
