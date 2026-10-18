import argparse, json, math, os, re, statistics, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("AIGD_ROOT", Path(__file__).resolve().parents[1]))
for p in (ROOT / "server", ROOT / "data", Path(__file__).resolve().parent.parent / "server",
          Path(__file__).resolve().parent.parent / "data"):
    sys.path.insert(0, str(p))
from guide_common import RESPONSE_SCHEMA, leak_hits, story_spoiler_hits

REQ_KEYS = set(RESPONSE_SCHEMA["required"])
HONORIFIC_END = re.compile(r"(니다|니까|시오|요|죠)[.!?]?$")
REGISTER_END = {"polite": HONORIFIC_END, "hapsyo": re.compile(r"(니다|니까|시오)[.!?]?$"), "haeyo": re.compile(r"(요|죠)[.!?]?$")}
BANMAL = re.compile(r"(해|야|지|어|아|거든|잖아|줘|냐|니)[.!?~]?$")
STEP_KINDS = ("howto", "next", "locked", "fail", "idle_hint", "screen_enter")
TEMPLATE_KINDS = STEP_KINDS + ("fact", "oos", "persona", "spoiler", "story_fact")


def sentences(line):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", line.strip()) if s.strip()]


def strip_vocative(s, address):
    return re.sub(r",\s*" + re.escape(address) + r"([.!?]?)$", r"\1", s)


def parse(raw):
    try:
        p = json.loads(raw)
        mode = "strict"
    except Exception:
        p, mode = None, "fail"
        s = (raw or "").strip()
        if s.startswith("```"):
            s = s.split("\n", 1)[-1].rsplit("```", 1)[0]
        i, k = s.find("{"), s.rfind("}")
        if i >= 0 and k > i:
            try:
                p, mode = json.loads(s[i:k + 1]), "lenient"
            except Exception:
                pass
    if not isinstance(p, dict) or not REQ_KEYS.issubset(p.keys()) or type(p.get("speak")) is not bool:
        return None, "fail"
    return p, mode


def locked_hint_cores(pack, state, meta):
    locked = set(meta.get("locked_systems") or [])
    cores = {s["unlock_hint"] for s in (pack or {}).get("systems", []) if s.get("unlock_hint") and s["id"] in locked}
    if not cores:
        for value in (state.get("locked_hints") or {}).values():
            core = re.sub(r"^.*?(?:은|는)\s+", "", value)
            core = re.sub(r"\s*열립니다$", "", core)
            if core and core != value:
                cores.add(core)
    return cores


def score(rows, preds, raws, address, packs, lat, prof=None):
    m = {k: [] for k in ["leak_locked_probe", "leak_any", "locked_refusal", "silence_ok", "false_silence",
                         "target_ok", "false_highlight", "locked_target", "address", "honorific", "banmal",
                         "wrong_honor", "len", "oos_refusal", "oos_near_refusal", "register", "forbidden", "story_leak", "spoiler_refusal",
                         "locked_hint", "story_fact_spoiler_refusal", "story_fact_answered"]}
    prof = prof or {}
    reg = REGISTER_END.get(prof.get("register", ""))
    forbidden = prof.get("forbidden_terms") or []
    leak_count = 0
    wrong_honor = address + "님" if not address.endswith("님") else None
    for r, p, raw in zip(rows, preds, raws):
        meta = r["meta"]; kind = meta["kind"].split(":")[0]
        pack = packs.get(meta.get("game"), packs.get("_default"))
        gold = json.loads(r["messages"][2]["content"])
        state = json.loads(r["messages"][1]["content"])["state"]
        valid = p is not None
        line = p.get("line") if valid else ""
        line = line if isinstance(line, str) else ""
        speak = p.get("speak") if valid and type(p.get("speak")) is bool else None
        text = line if valid else (raw or "")
        m["story_leak"].append(bool(story_spoiler_hits(text, state.get("story_chapter", 0), prof.get("story", {}))))
        if kind == "spoiler":
            m["spoiler_refusal"].append(valid and p.get("refusal") == "spoiler")
        hints = " ".join((state.get("locked_hints") or {}).values())
        hits = leak_hits(pack, text, state.get("unlocked_systems", []), hints) if meta["locked_systems"] else []
        leak_count += bool(hits)
        if kind == "locked":
            m["leak_locked_probe"].append(bool(hits))
            m["locked_refusal"].append(valid and p.get("refusal") == "locked")
            m["locked_hint"].append(bool(line) and any(h in line for h in locked_hint_cores(pack, state, meta)))
        if kind == "story_fact":
            m["story_fact_spoiler_refusal"].append(valid and p.get("refusal") == "spoiler")
            m["story_fact_answered"].append(valid and speak is True and p.get("refusal") is None)
        if kind != "silence" and meta["locked_systems"]:
            m["leak_any"].append(bool(hits))
        if kind == "oos":
            m["oos_near_refusal" if meta["kind"].endswith(":near") else "oos_refusal"].append(
                valid and p.get("refusal") == "out_of_scope")
        if kind == "silence":
            m["silence_ok"].append(speak is False)
        else:
            m["false_silence"].append(speak is False)
        if kind in STEP_KINDS and gold["speak"]:
            m["target_ok"].append(valid and p.get("ui_target") == gold["ui_target"])
        t = p.get("ui_target") if valid else None
        if valid and speak and kind != "silence":
            m["false_highlight"].append(bool(t) and t not in (meta.get("visible_targets") or []))
            m["locked_target"].append(bool(t) and t in (meta.get("locked_targets") or []))
        if line and speak and kind != "silence":
            ss = [strip_vocative(s, address) for s in sentences(line)]
            gold_sentences = [strip_vocative(s, address) for s in sentences(gold["line"])]
            style_eligible = meta.get("source") != "official_line" or all(HONORIFIC_END.search(s) for s in gold_sentences)
            m["address"].append(address in line)
            if style_eligible:
                m["honorific"].append(all(HONORIFIC_END.search(s) for s in ss))
                m["banmal"].append(any(BANMAL.search(s) and not HONORIFIC_END.search(s) for s in ss))
            if wrong_honor:
                m["wrong_honor"].append(wrong_honor in line)
            if reg is not None and style_eligible:
                m["register"].append(all(reg.search(s) for s in ss))
            if forbidden:
                m["forbidden"].append(any(f in line for f in forbidden))
            m["len"].append(len(line))
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None
    good = sorted(x for x in lat if x is not None)
    return {
        "locked_leak_count": leak_count,
        "story_leak_count": sum(m["story_leak"]),
        "story_leak_%": pct(m["story_leak"]),
        "spoiler_refusal_%": pct(m["spoiler_refusal"]),
        "story_fact_spoiler_refusal_%": pct(m["story_fact_spoiler_refusal"]),
        "story_fact_answered_%": pct(m["story_fact_answered"]),
        "locked_hint_%": pct(m["locked_hint"]),
        "locked_leak_%_of_locked_probes": pct(m["leak_locked_probe"]),
        "locked_leak_%_of_speaking_rows": pct(m["leak_any"]),
        "locked_refusal_%": pct(m["locked_refusal"]),
        "oos_refusal_%": pct(m["oos_refusal"]),
        "oos_near_refusal_%": pct(m["oos_near_refusal"]),
        "register_ok_%": pct(m["register"]),
        "forbidden_term_%": pct(m["forbidden"]),
        "silence_accuracy_%": pct(m["silence_ok"]),
        "false_silence_%": pct(m["false_silence"]),
        "ui_target_정답_일치율_%": pct(m["target_ok"]),
        "false_highlight_%": pct(m["false_highlight"]),
        "locked_target_%": pct(m["locked_target"]),
        "address_term_%": pct(m["address"]),
        "honorific_all_sentences_%": pct(m["honorific"]),
        "banmal_%": pct(m["banmal"]),
        "wrong_honorific_%": pct(m["wrong_honor"]),
        "avg_line_chars": round(statistics.mean(m["len"]), 1) if m["len"] else None,
        "latency_n": len(good),
        "latency_p50_s": round(statistics.median(good), 2) if good else None,
        "latency_p95_s": round(good[max(0, math.ceil(len(good) * 0.95) - 1)], 2) if good else None,
    }


def json_stats(modes):
    n = len(modes)
    return {"json_valid_strict_%": round(100 * sum(x == "strict" for x in modes) / n, 1),
            "json_valid_lenient_%": round(100 * sum(x in ("strict", "lenient") for x in modes) / n, 1)}


def diversity_stats(preds):
    lines = [p["line"] for p in preds if p and p.get("speak") and isinstance(p.get("line"), str)]
    pairs = [line[i:i + 2] for line in lines for i in range(len(line) - 1)]
    return {"unique_lines": len(set(lines)), "speaking_rows": len(lines),
            "distinct_2": round(len(set(pairs)) / len(pairs), 4) if pairs else None}


def self_test(rows, packs, address, prof):
    tmpl = [r for r in rows if r["meta"]["kind"].split(":")[0] in TEMPLATE_KINDS + ("silence",)]
    golds = [r["messages"][2]["content"] for r in tmpl]
    preds = [parse(g)[0] for g in golds]
    s = score(tmpl, preds, golds, address, packs, [None] * len(tmpl), prof)
    expect = {"locked_leak_count": 0, "locked_refusal_%": 100.0, "silence_accuracy_%": 100.0,
              "false_silence_%": 0.0, "ui_target_정답_일치율_%": 100.0, "false_highlight_%": 0.0,
              "locked_target_%": 0.0, "honorific_all_sentences_%": 100.0, "banmal_%": 0.0,
              "wrong_honorific_%": 0.0, "oos_refusal_%": 100.0, "register_ok_%": 100.0}
    if address.endswith("님"):
        expect.pop("wrong_honorific_%")
    if any(r["meta"]["kind"].endswith(":near") for r in tmpl):
        expect["oos_near_refusal_%"] = 100.0
    if prof.get("forbidden_terms"):
        expect["forbidden_term_%"] = 0.0
    expect["story_leak_count"] = 0
    if any(r["meta"]["kind"] == "spoiler" for r in tmpl):
        expect["spoiler_refusal_%"] = 100.0
    if any(r["meta"]["kind"] == "story_fact" for r in tmpl):
        expect["story_fact_spoiler_refusal_%"] = 0.0
        expect["story_fact_answered_%"] = 100.0
    bad = {k: (s[k], v) for k, v in expect.items() if s[k] is not None and s[k] != v}
    if bad:
        for r, p in zip(tmpl, preds):
            for x in sentences(p["line"] or ""):
                if p["speak"] and not HONORIFIC_END.search(strip_vocative(x, address)):
                    print("  [honorific miss]", x)
        raise SystemExit(f"self-test failed: {bad}")
    print("self-test ok", json.dumps(s, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="base, lora(병합 모델 8082), lora:rapi, lora:arona(어댑터 서버 8083)")
    ap.add_argument("--no-schema", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--eval", required=True)
    ap.add_argument("--character", default="rapi")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--rescore", action="store_true", help="모델을 다시 부르지 않고 reports/eval_<tag>.jsonl의 원문으로 다시 채점")
    ap.add_argument("--runtime", action="store_true", help="실제 서버의 상황별 temperature/후보 선택/최근 대사 정책으로 평가")
    ap.add_argument("--repeat", type=int, default=1, help="같은 상태 반복 횟수(다양성 측정은 10)")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.eval, encoding="utf-8")]
    if a.limit:
        rows = rows[:a.limit]
    if a.repeat < 1:
        ap.error("--repeat는 1 이상이어야 합니다")
    rows = [r for r in rows for _ in range(a.repeat)]

    from guide_common import load_pack, load_profile
    data_dir = Path(a.data_dir)
    packs = {}
    for f in list(data_dir.glob("pack_*.json")) + [data_dir / "game_pack_counters.json"]:
        pk = load_pack(f); packs[pk["game_id"]] = pk
    packs["_default"] = packs.get("counters_outpost_demo")
    _, prof = load_profile(data_dir / f"character_{a.character}.json")
    address = prof["address_term"]
    if a.self_test:
        self_test(rows, packs, address, prof)
        return
    if not (a.model and a.tag):
        ap.error("--model과 --tag가 필요합니다")

    import guide_server as gs
    raws, lat, runtime_preds, errors = [], [], [], 0
    if a.runtime:
        text, runtime_prof = gs.profile(a.character)
        gs._profiles[a.character] = (text, {**runtime_prof, "generation": {**runtime_prof.get("generation", {}), "diversity_enabled": True}})
        gs._recent_lines.clear()
    rep = ROOT / "reports"; rep.mkdir(exist_ok=True)
    if a.rescore:
        old = [json.loads(l) for l in open(rep / f"eval_{a.tag}.jsonl", encoding="utf-8")]
        raws = [o["raw"] for o in old][:len(rows)]
        lat = [o["sec"] for o in old][:len(rows)]
        errors = sum(1 for x in lat if x is None)
        if a.runtime:
            runtime_preds = [o["server"] for o in old][:len(rows)]
    for i, r in enumerate([] if a.rescore else rows):
        try:
            if a.runtime:
                um = json.loads(r["messages"][1]["content"])
                response, raw, _ = gs.run_turn(um["trigger"], um.get("player_input"), um["state"], a.character,
                                               a.model, not a.no_schema, seed=a.seed + i,
                                               game_id=r["meta"].get("game"), runtime_diversity=True)
                runtime_preds.append(response)
                dt = response["debug"]["total_ms"] / 1000
                errors += "backend_error" in response["debug"]["issues"]
            else:
                raw, dt, _ = gs.call_llm(a.model, r["messages"][0]["content"], r["messages"][1]["content"],
                                         not a.no_schema, a.temperature, a.seed + (i if a.repeat > 1 else 0))
            raws.append(raw); lat.append(dt)
        except Exception as e:
            print("[error]", i, e); raws.append(""); lat.append(None); errors += 1
            if a.runtime: runtime_preds.append({**gs.SILENT, "risk": "replaced"})

    parsed = [parse(x) for x in raws]
    preds_raw = [p for p, _ in parsed]
    modes = [mm for _, mm in parsed]
    preds_srv = []
    for r, p in zip(rows, preds_raw):
        um = json.loads(r["messages"][1]["content"])
        state = um["state"]
        trig = um.get("trigger") or r["meta"].get("trigger")
        v, _ = gs.validate(p if p else gs.SILENT, state, prof, packs.get(r["meta"].get("game")), trig)
        if p is None:
            v["risk"] = "replaced"
        preds_srv.append(v)
    if a.runtime:
        preds_srv = runtime_preds

    s = {"n": len(rows), "errors": errors, **json_stats(modes),
         "raw": score(rows, preds_raw, raws, address, packs, lat, prof),
         "server": score(rows, preds_srv, [p["line"] for p in preds_srv], address, packs, lat, prof),
         "tag": a.tag, "model": a.model, "schema": not a.no_schema, "temperature": a.temperature,
         "seed": a.seed, "time": time.ctime(), "rescored": a.rescore}
    s["runtime_policy"] = a.runtime
    s["repeat"] = a.repeat
    s["diversity"] = diversity_stats(preds_srv)
    s["replacement_%"] = round(100 * sum(p.get("risk") == "replaced" for p in preds_srv) / len(preds_srv), 1)
    with open(rep / f"eval_{a.tag}.jsonl", "w", encoding="utf-8") as f:
        for r, raw, sec, ps in zip(rows, raws, lat, preds_srv):
            f.write(json.dumps({"meta": r["meta"], "input": json.loads(r["messages"][1]["content"]),
                                "gold": json.loads(r["messages"][2]["content"]), "raw": raw, "sec": sec,
                                "server": ps}, ensure_ascii=False) + "\n")
    summ = rep / "eval_summary.json"
    allr = json.loads(summ.read_text(encoding="utf-8")) if summ.exists() else {}
    allr[a.tag] = s
    summ.write_text(json.dumps(allr, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(f"Evaluation failed: {errors} backend errors; see reports/eval_{a.tag}.jsonl")


if __name__ == "__main__":
    main()
