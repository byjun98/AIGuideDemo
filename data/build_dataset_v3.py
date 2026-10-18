import argparse, json, random, string
from pathlib import Path

from guide_common import (canonical_state, card_entry, fill, has_batchim, load_pack, load_profile, retrieve,
                          story_spoiler_hits, system_prompt, user_message)
from dataset_splits import allocate, allocate_states, check_leakage, flatten_templates, fingerprint, PARTITIONS
from import_character_dialogue import parse_dialogue
from suggestion_checks import check_suggestions, suggestion_questions

HERE = Path(__file__).resolve().parent
BANDS = [("cautious", 0, 20), ("friendly", 21, 50), ("trust", 51, 80), ("special_trust", 81, 100)]

STEP_PROGRESS = [dict(missions=[0], enhances=0), dict(missions=[0], enhances=0), dict(missions=[1], enhances=0),
                 dict(missions=[1], enhances=1), dict(missions=[1, 2], enhances=1), dict(missions=[3], enhances=1),
                 dict(missions=[3, 4, 6], enhances=1)]

ASK_HOWTO = {
    "train": ["{sys} 어떻게 해?", "{sys} 어디서 해?", "{sys} 하는 법 알려줘", "{sys} 버튼 어디 있어?",
              "{sys}{x_eun} 어디서 열어?", "{sys} 하고 싶은데", "{sys} 화면 어떻게 가?", "{cname}, {sys} 좀 알려줘",
              "{sys} 메뉴가 안 보여", "{sys} 하려면 뭐 눌러?"],
    "eval": ["{sys} 들어가는 곳이 어디야?", "{sys} 좀 하고 싶은데 어디로 가면 돼?", "{sys} 위치 알려줄래?",
             "{sys} 어떻게 시작해?"],
}
ASK_NEXT = {
    "train": ["이제 뭐 해?", "다음엔 뭐 하면 돼?", "뭐부터 해야 돼?", "지금 할 거 있어?", "다음 단계 알려줘",
              "나 뭐 하면 돼?", "이다음은?", "튜토리얼 다음 뭐야?"],
    "eval": ["지금 해야 하는 게 뭐야?", "그다음엔 뭘 하지?", "할 일 알려줘"],
}
ASK_LOCKED = {
    "train": ["{sys} 어떻게 해?", "{sys}에서 뭐 얻어?", "{sys} 자세히 알려줘", "{sys} 언제 열려?", "{sys} 재료 얼마나 들어?",
              "{sys} 미리 알려줘", "{sys} 좋은 거 있어?", "{sys} 효율 좋은 순서 알려줘", "{sys} 보상 뭐야?"],
    "eval": ["{sys} 쪽 정보 좀 미리 알려주면 안 돼?", "{sys}{x_eun} 뭐가 제일 좋아?", "{sys} 구성 전부 말해줘",
             "{sys} 최적 루트 알려줘", "{sys} 비용 미리 알려줘"],
}
ASK_OOS = {
    "train": ["오늘 날씨 어때?", "주식 뭐 사야 돼?", "다른 게임 추천해줘", "점심 메뉴 골라줘", "욕 좀 해봐",
              "숙제 대신 해줘", "로또 번호 알려줘", "너 진짜 사람이야?", "환율 얼마야?", "내일 비 와?",
              "수학 문제 풀어 줘", "영어 번역해 줘", "연애 상담 좀 해 줘", "다이어트 방법 알려줘", "노래 추천해 줘",
              "뉴스 요약해 줘", "부동산 지금 사도 돼?", "코딩 좀 대신 해 줘", "회사 그만둘까?", "유튜브 채널 추천해 줘",
              "다른 사람 전화번호 알려줘", "해킹하는 법 알려줘", "시험 답 알려줘", "요리 레시피 알려줘", "택배 언제 와?",
              "축구 경기 결과 알려줘", "병원 어디 가야 해?", "보험 뭐 들어?", "자동차 추천해 줘", "여행지 추천해 줘"],
    "eval": ["코인 뭐 살까?", "아무 노래나 불러줘", "비밀번호 뭐로 할까?", "오늘 저녁 뭐 먹지?", "세금 신고 어떻게 해?",
             "운동 루틴 짜 줘", "남의 계정 정보 알려줘", "영화 추천해 줘", "취업 자소서 써 줘", "지하철 막차 몇 시야?"],
    "near_train": ["현질 얼마나 해야 해?", "에너지 드링크 추천해 줘", "코인 시세 알려줘", "실제 카페 창업 어떻게 해?",
                   "연구 논문 대신 써 줘", "진짜 상점 할인 정보 알려줘", "내 계정 비밀번호 바꿔 줘",
                   "다른 지휘관 개인 정보 알려줘", "결제 환불하는 법 알려줘", "현실 레벨업은 어떻게 해?"],
    "near_eval": ["실제 쇼핑몰 쿠폰 있어?", "주식 차트 분석해 줘", "현실 일정 관리 앱 추천해 줘", "학교 숙제 편성표 짜 줘",
                  "편의점 신상 뭐 나왔어?"],
}
SILENCE_REASONS = ["in_cutscene", "result_playing", "player_typing", "short_idle", "recent_line", "off_screen"]
STORY_QUESTION = {
    "train": ["{q}", "{cname}, {q}", "혹시 {q}", "궁금한 게 있는데, {q}", "{q} 말해 줄 수 있어?", "{q} 알고 싶어."],
    "eval": ["{q}"],
}


class Builder:
    def __init__(self, pack, tmpl, profile, profile_text, split, seed, smalltalk=None, kinds=None, partition=None):
        self.pack, self.split = pack, split
        self.t, self.template_owners = flatten_templates(tmpl)
        self.partition = partition or ("train" if split == "train" else "test")
        self.story = profile.get("story", {})
        self._invalid_template = False
        self._template_ids = set()
        self._card_group = None
        self.rng = random.Random(seed)
        self.a = profile["address_term"]
        self.cname = profile["name"]
        self.system = system_prompt(profile_text)
        self.cards = {c["id"]: c for c in pack["cards"]}
        self.steps = {s["id"]: s for s in pack["tutorial_steps"]}
        self.step_ids = [s["id"] for s in pack["tutorial_steps"]]
        self.active = [s for s in self.step_ids if s != "DONE"]
        self.sys = {s["id"]: s for s in pack["systems"]}
        self.guide_sys = [s for s in pack["systems"] if not s.get("info_only")]
        self.smalltalk = smalltalk or []
        self.out = []
        self.state_owners = allocate_states([f"{step}:{screen}" for step in self.step_ids
                                      for screen in self.screens_for(step) + ["result"]],
                                      {step: self.steps[step]["system"] for step in self.step_ids})

    def progress(self, step):
        return STEP_PROGRESS[self.step_ids.index(step)]

    def unlocked_for(self, step):
        pr = self.progress(step)
        e = pr["enhances"]
        out = []
        for s in self.pack["systems"]:
            u = s["unlock"]
            if u["type"] == "always" or (u["type"] == "missions_cleared" and min(pr["missions"]) >= u["value"]) \
                    or (u["type"] == "enhance_count" and e >= u["value"]):
                out.append(s["id"])
        return out

    def band(self):
        name, lo, hi = self.rng.choice(BANDS)
        return name, self.rng.randint(lo, hi)

    def screens_for(self, step):
        return ["lobby"] + [s for s in self.unlocked_for(step) if not self.sys[s].get("info_only")]

    def pick_screen(self, step, p_lobby=0.5):
        tscreen = self.steps[step]["system"]
        r = self.rng.random()
        if tscreen is None:
            return "lobby" if r < 0.6 else self.rng.choice(self.screens_for(step))
        if r < p_lobby:
            return "lobby"
        if r < p_lobby + (1 - p_lobby) / 2:
            return tscreen
        others = [s for s in self.screens_for(step) if s not in ("lobby", tscreen)]
        return self.rng.choice(others) if others else tscreen

    def state(self, step, screen="lobby", **over):
        band, aff = self.band()
        raw = {"tutorial_step": step, "unlocked_systems": self.unlocked_for(step),
               "missions_cleared": self.rng.choice(self.progress(step)["missions"]), "screen": screen,
               "in_cutscene": False, "result_playing": False, "player_typing": False,
               "idle_seconds": self.rng.randint(0, 15), "seconds_since_last_line": self.rng.randint(10, 120),
               "fail_count": 0, "affection": aff, "affection_band": band}
        raw["story_chapter"] = self.rng.randint(0, max((c["index"] for c in self.story.get("chapters", [])), default=0))
        raw.update(over)
        return canonical_state(self.pack, raw, self.story)

    def guide_target(self, st):
        step = self.steps[st["tutorial_step"]]
        if step["system"] is None:
            return None, "none"
        scr = st["screen"]
        if scr == "lobby":
            t, where = self.sys[step["system"]]["ui_target"], "lobby"
        elif scr == step["system"]:
            t, where = step["ui_target"], "here"
        else:
            t, where = "btn_back", "away"
        if t not in st["visible_targets"]:
            return None, "none"
        return t, where

    def own_pool(self, key):
        pool = [x for x in self.t[key] if self.template_owners.get(x, (self.partition,))[0] == self.partition]
        return pool or self.t[key]

    def text(self, template, **values):
        owner = self.template_owners.get(template)
        if owner:
            self._invalid_template |= owner[0] != self.partition
            self._template_ids.add(owner[1])
        return fill(template, **values)

    def resp(self, line, intent, band, ui_target=None, refusal=None, speak=True, tail=True, emo=None):
        if speak and tail:
            x = self.rng.choice(self.t["band_tail"][band])
            if x:
                line = line + " " + self.text(x, a=self.a)
        if emo is not None:
            e, v, m = emo
        elif speak:
            e, v, m = self.rng.choice(self.t["emo_by_intent"][intent])
        else:
            e, v, m = "neutral", "calm_brief", "idle"
        if band in ("trust", "special_trust") and intent in ("howto", "next", "fact") and self.rng.random() < 0.3:
            e, v = self.t["warm_override"]
        return {"speak": speak, "line": line if speak else "", "emotion": e, "voice_tag": v, "motion": m,
                "ui_target": ui_target if speak else None, "action": "highlight" if (speak and ui_target) else "none",
                "refusal": refusal}

    MAX_USER_CHARS = 1250

    def add(self, kind, trigger, player_input, state, cards, response):
        cards = list(cards)
        while len(user_message(trigger, player_input, state, cards)) > self.MAX_USER_CHARS and len(cards) > 1:
            drop = next((i for i in range(len(cards) - 1, -1, -1) if cards[i]["id"] != self._card_group), None)
            if drop is None: break
            cards.pop(drop)
        state_group = f"{state['tutorial_step']}:{state['screen']}"
        invalid = self._invalid_template or self.state_owners.get(state_group) != self.partition
        template_ids = sorted(self._template_ids)
        card_group = self._card_group
        self._invalid_template, self._template_ids, self._card_group = False, set(), None
        if invalid or story_spoiler_hits(response["line"], state.get("story_chapter", 0), self.story):
            return
        locked = [k for k in self.sys if k not in state.get("unlocked_systems", [])]
        self.out.append({
            "messages": [{"role": "system", "content": self.system},
                         {"role": "user", "content": user_message(trigger, player_input, state, cards)},
                         {"role": "assistant", "content": json.dumps(response, ensure_ascii=False)}],
            "meta": {"kind": kind, "split": self.split, "band": state.get("affection_band"), "trigger": trigger,
                     "screen": state.get("screen"), "game": self.pack["game_id"], "locked_systems": locked,
                     "locked_targets": [self.sys[k]["ui_target"] for k in locked if self.sys[k]["ui_target"]],
                     "visible_targets": state.get("visible_targets", []), "partition": self.partition,
                     "template_ids": template_ids, "state_group": state_group, "card_group": card_group}})

    def cards_for(self, st, q=None, focus=None, k=4):
        return retrieve(self.pack, st, q, k=k, rng=self.rng, focus_system=focus, story=self.story)

    def step_line(self, st, lobby_pool, here_pool, away_pool):
        step = self.steps[st["tutorial_step"]]
        t, where = self.guide_target(st)
        pool = {"lobby": lobby_pool, "here": here_pool, "away": away_pool}.get(where, lobby_pool)
        line = self.text(self.rng.choice(pool), a=self.a, goal=step["short"], sysname=self.sys[step["system"]]["name"],
                    action=step["action_label"])
        return line, t

    def q(self, pool, **kw):
        return self.text(self.rng.choice(pool), cname=self.cname, **kw)

    def gen_howto(self, n):
        for _ in range(n):
            step = self.rng.choice(self.step_ids)
            scr = "lobby" if self.rng.random() < 0.75 else self.rng.choice(self.screens_for(step)[1:] or ["lobby"])
            st = self.state(step, scr)
            sysid = self.rng.choice([s for s in st["unlocked_systems"] if not self.sys[s].get("info_only")])
            name = self.sys[sysid]["name"]
            q = self.q(ASK_HOWTO[self.split], sys=name, x_eun=("은" if has_batchim(name) else "는"))
            if scr == "lobby":
                line = self.text(self.rng.choice(self.t["howto"]), a=self.a, sys=name, where=self.sys[sysid]["where"])
                t = self.sys[sysid]["ui_target"]
            elif scr == sysid:
                here = next((s for s in self.pack["tutorial_steps"] if s["system"] == sysid), None)
                line = self.text(self.t["howto_here"], a=self.a, sys=name)
                t = here["ui_target"] if here and here["ui_target"] in st["visible_targets"] else None
                if t:
                    line += " " + self.text(self.t["howto_here_target"], x=here["action_label"])
            else:
                line = self.text(self.rng.choice(self.t["howto_away"]), a=self.a, sys=name)
                t = "btn_back"
            self.add("howto", "player_utterance", q, st, self.cards_for(st, q, sysid),
                     self.resp(line, "howto", st["affection_band"], t))

    def gen_next(self, n):
        for _ in range(n):
            step = self.rng.choice(self.step_ids)
            st = self.state(step, self.pick_screen(step))
            q = self.q(ASK_NEXT[self.split])
            if step == "DONE":
                r = self.resp(self.text(self.rng.choice(self.t["done"]), a=self.a), "done", st["affection_band"])
            else:
                line, t = self.step_line(st, self.t["next_lobby"], self.t["next_here"], self.t["next_away"])
                r = self.resp(line, "next", st["affection_band"], t)
            self.add("next", "player_utterance", q, st, self.cards_for(st, q, self.steps[step]["system"]), r)

    def gen_locked(self, n):
        cands = [s for s in self.active if any(x["id"] not in self.unlocked_for(s) for x in self.guide_sys)]
        for _ in range(n):
            step = self.rng.choice(cands)
            st = self.state(step, self.pick_screen(step))
            locked = [x["id"] for x in self.guide_sys if x["id"] not in st["unlocked_systems"]]
            sysid = self.rng.choice(locked)
            name = self.sys[sysid]["name"]
            q = self.q(ASK_LOCKED[self.split], sys=name, x_eun=("은" if has_batchim(name) else "는"))
            own = self.own_pool("locked")
            with_hint = [x for x in own if "{hint}" in x] or own
            pool = with_hint if self.rng.random() < 0.85 else own
            line = self.text(self.rng.choice(pool), a=self.a, sys=name, hint=self.sys[sysid]["unlock_hint"],
                        goal=self.steps[step]["short"])
            t, _ = self.guide_target(st)
            self.add("locked", "player_utterance", q, st, self.cards_for(st, q),
                     self.resp(line, "locked", st["affection_band"], t, refusal="locked"))

    def gen_fact(self, n):
        keys = [c["id"] for c in self.pack["cards"] if (c.get("qa") or {}).get("answers")]
        if not keys:
            return
        for _ in range(n):
            cid = self.rng.choice(keys)
            c = self.cards[cid]
            steps = [s for s in self.step_ids if c["system"] in self.unlocked_for(s)]
            step = self.rng.choice(steps)
            st = self.state(step, self.rng.choice(self.screens_for(step)))
            qa = c["qa"]
            q = self.rng.choice(qa["train"] if self.split == "train" else qa["eval"])
            cards = self.cards_for(st, q, c["system"])
            if cid not in [x["id"] for x in cards]:
                cards[0] = card_entry(c)
            line = self.text(self.rng.choice(qa["answers"]), a=self.a)
            self._card_group = cid
            self.add("fact", "player_utterance", q, st, cards, self.resp(line, "fact", st["affection_band"]))

    def gen_fail(self, n):
        for _ in range(n):
            step = self.rng.choice(self.active)
            fc = self.rng.choice([1, 2, 2, 3, 4])
            st = self.state(step, self.pick_screen(step, 0.4), fail_count=fc)
            pool, intent = (self.t["fail1"], "fail1") if fc == 1 else (self.t["fail2"], "fail2")
            t, _ = self.guide_target(st)
            self.add("fail", "action_failed", None, st, self.cards_for(st, None, self.steps[step]["system"], k=2),
                     self.resp(self.text(self.rng.choice(pool), a=self.a), intent, st["affection_band"], t, tail=(fc > 1)))

    def gen_idle_hint(self, n):
        for _ in range(n):
            step = self.rng.choice(self.active)
            idle = self.rng.randint(20, 24) if self.rng.random() < 0.5 else self.rng.randint(25, 90)
            since = self.rng.randint(8, 12) if self.rng.random() < 0.3 else self.rng.randint(13, 200)
            st = self.state(step, self.pick_screen(step), idle_seconds=idle, seconds_since_last_line=since)
            t, where = self.guide_target(st)
            if where == "lobby":
                line = self.text(self.rng.choice(self.t["idle"]), a=self.a, goal=self.steps[step]["short"])
            else:
                line, t = self.step_line(st, self.t["idle"], self.t["next_here"], self.t["next_away"])
            self.add("idle_hint", "idle_tick", None, st, self.cards_for(st, None, self.steps[step]["system"], k=2),
                     self.resp(line, "idle", st["affection_band"], t, tail=False))

    def gen_screen_enter(self, n):
        for _ in range(n):
            step = self.rng.choice(self.active)
            sc = self.steps[step]["system"]
            st = self.state(step, sc, idle_seconds=0, seconds_since_last_line=self.rng.randint(8, 200))
            line = self.text(self.rng.choice(self.t["enter"]), a=self.a, goal=self.steps[step]["short"],
                        sysname=self.sys[sc]["name"], action=self.steps[step]["action_label"])
            self.add("screen_enter", "screen_enter", None, st, self.cards_for(st, None, sc, k=2),
                     self.resp(line, "enter", st["affection_band"], self.steps[step]["ui_target"], tail=False))

    def gen_silence(self, n):
        for _ in range(n):
            step = self.rng.choice(self.step_ids)
            why = self.rng.choice(SILENCE_REASONS)
            over, screen = {}, self.pick_screen(step)
            trigger = self.rng.choice(["idle_tick", "screen_enter"])
            if why in ("in_cutscene", "result_playing", "player_typing"):
                over[why] = True
                over["idle_seconds"] = self.rng.randint(0, 90)
                if why == "result_playing":
                    screen = "result"
                elif trigger == "screen_enter" and self.steps[step]["system"]:
                    screen = self.steps[step]["system"]
            elif why == "short_idle":
                trigger = "idle_tick"
                over["idle_seconds"] = self.rng.randint(15, 19) if self.rng.random() < 0.5 else self.rng.randint(0, 14)
            elif why == "recent_line":
                trigger = "idle_tick"; over["idle_seconds"] = self.rng.randint(20, 60)
                over["seconds_since_last_line"] = self.rng.randint(6, 7) if self.rng.random() < 0.5 else self.rng.randint(0, 5)
            else:
                trigger = "screen_enter"; over["idle_seconds"] = 0
                screen = self.rng.choice([s for s in self.screens_for(step) if s != self.steps[step]["system"]])
            st = self.state(step, screen, **over)
            self.add("silence:" + why, trigger, None, st, self.cards_for(st, None, k=2),
                     self.resp("", "idle", st["affection_band"], None, speak=False))

    def gen_oos(self, n, near_ratio=0.35):
        for _ in range(n):
            step = self.rng.choice(self.step_ids)
            st = self.state(step, self.rng.choice(self.screens_for(step)))
            near = self.rng.random() < near_ratio
            pool = ASK_OOS[("near_" if near else "") + self.split]
            q = self.rng.choice(pool)
            r = self.resp(self.text(self.rng.choice(self.t["oos"]), a=self.a), "oos", st["affection_band"],
                          refusal="out_of_scope", tail=False)
            self.add("oos" + (":near" if near else ""), "player_utterance", q, st, self.cards_for(st, q, k=2), r)

    def gen_persona(self, n):
        qas = self.t.get("persona_qa") or []
        if not qas:
            return
        for _ in range(n):
            qa = self.rng.choice(qas)
            step = self.rng.choice(self.step_ids)
            st = self.state(step, "lobby")
            q = self.rng.choice(qa["train"] if self.split == "train" else qa["eval"])
            line = self.text(self.rng.choice(qa["answers"]), a=self.a)
            self.add("persona", "player_utterance", q, st, self.cards_for(st, q, k=2),
                     self.resp(line, "persona", st["affection_band"], tail=False))

    def gen_smalltalk(self, n):
        if not self.smalltalk:
            return
        scenes = self.t["smalltalk_by_scene"][self.split]
        for _ in range(n):
            c = self.rng.choice(self.smalltalk)
            scene = c["scene"] if c["scene"] in scenes else "advise_session"
            over = {"affection": c.get("affection", self.rng.randint(30, 90)), "scene": scene}
            if c.get("band"):
                over["affection_band"] = c["band"]
            else:
                over["affection_band"] = next(b for b, lo, hi in BANDS if lo <= over["affection"] <= hi)
            if c.get("gift"):
                over["gift_context"] = c["gift"]
            st = self.state(self.rng.choice(self.step_ids), "lobby", **over)
            q = None
            if q is None:
                q = self.rng.choice(scenes[scene])
            r = {"speak": True, "line": self.text(c["line"], a=self.a) if "{a}" in c["line"] else c["line"],
                 "emotion": c.get("emotion", "neutral"), "voice_tag": c.get("voice", "warm_reserved"),
                 "motion": c.get("motion", "idle"), "ui_target": None, "action": "none", "refusal": None}
            self.add("smalltalk", "player_utterance", q, st, self.cards_for(st, q, k=2), r)
            if self.out and self.out[-1]["messages"][2]["content"] == json.dumps(r, ensure_ascii=False):
                self.out[-1]["meta"]["scene_group"] = scene


    def gen_spoiler(self, n):
        cards = [c for c in self.pack["cards"] if c.get("story_chapter", 0) > 0 and c.get("answer")]
        if not cards: return
        maximum = max(c["index"] for c in self.story["chapters"])
        for _ in range(n):
            card = self.rng.choice(cards)
            gate = card["story_chapter"]
            if self.rng.random() < 0.5:
                chapter = self.rng.choice([max(0, gate - 1), gate, min(maximum, gate + 1)])
            else:
                chapter = self.rng.randint(0, maximum)
            st = self.state(self.rng.choice(self.step_ids), "lobby", story_chapter=chapter)
            locked = chapter < gate
            q = fill(self.rng.choice(STORY_QUESTION[self.split]), cname=self.cname, q=card["question"])
            cards_in_prompt = self.cards_for(st, q)
            if not locked and card["id"] not in [x["id"] for x in cards_in_prompt]:
                continue
            line = self.text(self.rng.choice(self.own_pool("spoiler")), a=self.a) if locked else self.text(card["answer"], a=self.a)
            self._card_group = card["id"]
            self.add("spoiler" if locked else "story_fact", "player_utterance", q, st, cards_in_prompt,
                     self.resp(line, "persona", st["affection_band"], refusal="spoiler" if locked else None, tail=False))


ALT_NAMES = ["작전", "훈련", "보급소", "정비", "탐사", "기록실", "교류", "개발", "제작소", "순찰", "통신", "의무실",
             "격납고", "관제", "도서관", "공방", "시장", "광장", "연구소", "회의실", "창고", "실험실", "학당", "훈련장"]
ALT_WORDS = ["alpha", "bravo", "delta", "kilo", "nova", "orbit", "pulse", "relay", "sigma", "tango", "vector", "zen",
             "atlas", "comet", "ember", "frost", "harbor", "ion", "lumen", "mesa"]


def variant_pack(pack, rng):
    p = json.loads(json.dumps(pack, ensure_ascii=False))
    names = rng.sample(ALT_NAMES, len(p["systems"]))
    idmap, namemap = {}, {}
    def nid(prefix):
        return f"{prefix}_{rng.choice(ALT_WORDS)}_{''.join(rng.choices(string.ascii_lowercase + string.digits, k=2))}"
    for s, nn in zip(p["systems"], names):
        if s.get("info_only"):
            continue
        namemap[s["name"]] = nn
        if s["ui_target"]:
            idmap[s["ui_target"]] = nid("btn")
            s["ui_target"] = idmap[s["ui_target"]]
        s["name"] = nn
    for st in p["tutorial_steps"]:
        if st["ui_target"]:
            if st["ui_target"] not in idmap:
                idmap[st["ui_target"]] = nid("ui")
            st["ui_target"] = idmap[st["ui_target"]]
    def rn(x):
        for a, b in sorted(namemap.items(), key=lambda kv: -len(kv[0])):
            x = x.replace(a, b)
        return x
    for s in p["systems"]:
        s["where"] = rn(s["where"])
    for st in p["tutorial_steps"]:
        st["goal"], st["short"], st["action_label"] = rn(st["goal"]), rn(st["short"]), rn(st["action_label"])
    p["screen_targets"] = {k: [idmap.get(t, t) for t in v] for k, v in p["screen_targets"].items()}
    for c in p["cards"]:
        c.pop("qa", None)
    p["game_id"] = pack["game_id"] + "_variant"
    return p


def self_check(rows, suggestions=None):
    if suggestions is not None:
        check_suggestions(rows, suggestions)
    bad = []
    for ex in rows:
        g = json.loads(ex["messages"][2]["content"])
        st = json.loads(ex["messages"][1]["content"])["state"]
        if g["ui_target"] is not None and g["ui_target"] not in st["visible_targets"]:
            bad.append(("target_not_visible", ex["meta"]["kind"], g["ui_target"], st["screen"]))
        if g["ui_target"] in ex["meta"]["locked_targets"]:
            bad.append(("locked_target", ex["meta"]["kind"], g["ui_target"]))
        if (g["ui_target"] is None) != (g["action"] == "none"):
            bad.append(("action_mismatch", ex["meta"]["kind"]))
        if "{" in g["line"]:
            bad.append(("unfilled", g["line"]))
    if bad:
        raise SystemExit(f"self_check failed: {len(bad)} rows, e.g. {bad[:5]}")


def dedup_shuffle(rows, rng):
    seen, uniq = set(), []
    for ex in rows:
        key = ex["messages"][1]["content"] + ex["messages"][2]["content"]
        if key not in seen:
            seen.add(key); uniq.append(ex)
    rng.shuffle(uniq)
    return uniq


def write(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ex in rows:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
    kinds = {}
    for ex in rows:
        k = ex["meta"]["kind"].split(":")[0]
        kinds[k] = kinds.get(k, 0) + 1
    print(path.name, len(rows), kinds)


RULE_KINDS = ["howto", "next", "locked", "fail", "idle_hint", "screen_enter", "silence", "oos"]
STORY_ROWS = {"train": dict(spoiler=150, story_fact=150), "val": dict(spoiler=14, story_fact=10),
              "test": dict(spoiler=18, story_fact=12)}
PROBE_ROWS = dict(spoiler=40, story_fact=30)
PLAN = {
    "train": dict(howto=230, next=230, locked=220, fact=240, fail=170, idle_hint=130, screen_enter=110, silence=300,
                  oos=200, smalltalk=200, persona=100),
    "eval": dict(howto=22, next=24, locked=36, fact=26, fail=18, idle_hint=16, screen_enter=12, silence=40, oos=24,
                 smalltalk=12, persona=10),
    "cross": dict(howto=18, next=18, locked=18, fail=10, idle_hint=10, screen_enter=10, silence=24, oos=14),
}


def partition_pack(pack, partition, seed):
    cards = pack["cards"]
    pinned = {c["id"]: c["partition"] for c in cards if c.get("partition") in PARTITIONS}
    free = [c for c in cards if c["id"] not in pinned]
    normal = allocate([c["id"] for c in free if not c.get("story_chapter")], seed)
    story = allocate([c["id"] for c in free if c.get("story_chapter")], seed)
    owners = {**normal, **story, **pinned}
    return {**pack, "cards": [c for c in cards if owners[c["id"]] == partition]}


def generate_partition(partition, pack, tmpl, prof, ptext, seed, target, official):
    st_lines = tmpl.get("smalltalk_lines", [])
    scene_owners = allocate([line["scene"] for line in st_lines], seed)
    selected = [line for line in st_lines if scene_owners[line["scene"]] == partition]
    b = Builder(partition_pack(pack, partition, seed), tmpl, prof, ptext,
                "train" if partition == "train" else "eval", seed, selected, partition=partition)
    plan = PLAN["train"] if partition == "train" else PLAN["eval"]
    story_draws = sum(STORY_ROWS[partition].values()) + (sum(PROBE_ROWS.values()) if partition == "test" else 0)
    for kind, count in {**plan, "spoiler": story_draws}.items():
        getattr(b, "gen_" + kind)(count * 20)
    official_owners = allocate([r["official_group"] for r in official], seed, test_ratio=.1)
    for record in official:
        if official_owners[record["official_group"]] != partition: continue
        for _ in range(30):
            before = len(b.out)
            chapter = record.get("story_chapter", 0)
            maximum = max((c["index"] for c in b.story.get("chapters", [])), default=0)
            st = b.state(b.rng.choice(b.step_ids), "lobby", story_chapter=b.rng.randint(chapter, max(chapter, maximum)))
            response = b.resp(record["line"], "persona", st["affection_band"], tail=False)
            b.add("official_line", "player_utterance", record["situation"] + " 때 뭐라고 말해?", st, b.cards_for(st), response)
            if len(b.out) > before:
                b.out[-1]["meta"].update(source="official_line", official_group=record["official_group"], source_file=record["source_file"])
    candidates = dedup_shuffle(b.out, random.Random(seed))
    by_kind = {}
    for row in candidates:
        key = row["meta"]["kind"].split(":")[0]
        by_kind.setdefault(key, []).append(row)
    rows = []
    counts = {**plan, "official_line": 160 if partition == "train" else 20}
    if partition == "val":
        counts = {key: max(4, round(value * .6)) for key, value in counts.items()}
    counts.update(STORY_ROWS[partition])
    for key, count in counts.items():
        if partition == "train" and key in RULE_KINDS: count = round(count * .7)
        rows.extend(by_kind.get(key, [])[:count])
    return dedup_shuffle(rows, random.Random(seed)), candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--cross-packs", nargs="*", default=[])
    ap.add_argument("--variant-ratio", type=float, default=.3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(HERE / "v3/retrain_20261016"))
    ap.add_argument("--only-cross", action="store_true")
    a = ap.parse_args()
    pack = load_pack(HERE / a.pack)
    ptext, prof = load_profile(HERE / f"character_{a.character}.json")
    pack = {**pack, "cards": pack["cards"] + [c for c in prof.get("story_cards", []) if c.get("training_eligible", True)]}
    template_path = HERE / "characters" / a.character / "templates.json"
    tmpl = json.loads(template_path.read_text(encoding="utf-8"))
    if not tmpl.get("smalltalk_lines") and not a.only_cross:
        raise SystemExit("No reviewed smalltalk lines available. Add reviewed authored lines before training.")
    if tmpl.get("smalltalk_review_status") == "pending" and not a.only_cross:
        raise SystemExit("Smalltalk draft is awaiting user review; training data generation is blocked.")
    source = HERE / "raw" / a.character / ("dialogue.csv" if a.character == "rapi" else "dialogue.txt")
    official = parse_dialogue(a.character, source) if not a.only_cross else []
    out = Path(a.out)
    partitions = {}
    seen_lines = set()
    if not a.only_cross:
        test_candidates = []
        for partition in ("train", "val", "test"):
            rows, candidates = generate_partition(partition, pack, tmpl, prof, ptext, a.seed, None, official)
            if partition == "test":
                test_candidates = candidates
            rows = [r for r in rows if not json.loads(r["messages"][2]["content"])["line"] or json.loads(r["messages"][2]["content"])["line"] not in seen_lines]
            if partition == "val" and len(rows) < 150:
                existing = {r["messages"][1]["content"] + r["messages"][2]["content"] for r in rows}
                for row in candidates:
                    key = row["messages"][1]["content"] + row["messages"][2]["content"]
                    line = json.loads(row["messages"][2]["content"])["line"]
                    if key not in existing and (not line or line not in seen_lines):
                        rows.append(row)
                        existing.add(key)
                    if len(rows) >= 150: break
            seen_lines.update(json.loads(r["messages"][2]["content"])["line"] for r in rows)
            partitions[partition] = rows
        rng = random.Random(a.seed)
        train_pack = partition_pack(pack, "train", a.seed)
        variant_rows = []
        for i in range(12):
            b = Builder(variant_pack(train_pack, rng), tmpl, prof, ptext, "train", a.seed + i + 1, partition="train")
            for kind in RULE_KINDS:
                getattr(b, "gen_" + kind)(max(1, round(PLAN["train"][kind] * a.variant_ratio / 12)) * 3)
            variant_rows.extend(b.out)
        rng.shuffle(variant_rows)
        for kind in RULE_KINDS:
            partitions["train"].extend([r for r in variant_rows if r["meta"]["kind"].split(":")[0] == kind][:round(PLAN["train"][kind] * a.variant_ratio)])
        partitions["train"] = dedup_shuffle(partitions["train"], rng)
        heldout_lines = {json.loads(r["messages"][2]["content"])["line"] for part in ("val", "test") for r in partitions[part]} - {""}
        partitions["train"] = [r for r in partitions["train"] if json.loads(r["messages"][2]["content"])["line"] not in heldout_lines]
        own_keys = {r["messages"][1]["content"] + r["messages"][2]["content"] for r in partitions["test"]}
        probe = []
        for kind, count in PROBE_ROWS.items():
            probe += [r for r in test_candidates if r["meta"]["kind"] == kind
                      and r["messages"][1]["content"] + r["messages"][2]["content"] not in own_keys][:count]
        leakage = check_leakage({**partitions, "test": partitions["test"] + probe})
        if probe:
            self_check(probe)
            write(probe, out / "eval" / f"{a.character}_spoiler_probe.jsonl")
        for part, rows in partitions.items():
            if not rows: raise SystemExit(f"Empty {part} partition")
            bank = json.loads((HERE / "characters" / a.character / "suggestions.json").read_text(encoding="utf-8"))
            self_check(rows, suggestion_questions(pack, prof.get("story", {}), bank) if part == "train" else None)
            path = out / ("sft" if part != "test" else "eval") / f"{a.character}_{'own' if part == 'test' else part}.jsonl"
            write(rows, path)
        manifest = {"character": a.character, "seed": a.seed, "counts": {k: len(v) for k,v in partitions.items()}, "probe": len(probe), "leakage_groups": leakage,
                    "template_sha256": fingerprint(template_path), "source_sha256": fingerprint(source), "silence_empty_line_shared": True}
        (out / f"{a.character}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for cp in a.cross_packs:
        cpack = load_pack(HERE / cp)
        c = Builder(cpack, tmpl, prof, ptext, "eval", a.seed + 199, partition="test")
        for kind, count in PLAN["cross"].items(): getattr(c, "gen_" + kind)(count * 8)
        cr = dedup_shuffle(c.out, random.Random(a.seed))
        self_check(cr)
        write(cr, out / "eval" / f"{a.character}_cross_{cpack['game_id']}.jsonl")


if __name__ == "__main__":
    main()
