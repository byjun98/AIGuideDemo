import json, os, statistics
from pathlib import Path
ROOT = str(Path(os.environ.get("AIGD_ROOT", Path(__file__).resolve().parents[1])))
d = json.load(open(os.path.join(ROOT, "reports", "eval_summary.json"), encoding="utf-8")) if __name__ == "__main__" else {}


def available_mean(values, digits=1):
    present = [value for value in values if value is not None]
    return round(statistics.mean(present), digits) if present else None


def evaluation_tags(summary, character, model, prefix="retrain"):
    return [tag for tag in summary if tag.startswith(f"{prefix}_{character}_{model}_")
            and summary[tag].get("temperature", 0) == 0]

def policy_silent(trigger, st):
    auto = trigger in ("idle_tick", "screen_enter")
    if auto and (st.get("in_cutscene") or st.get("result_playing") or st.get("player_typing")): return True
    if trigger == "idle_tick" and st.get("idle_seconds", 0) < 20: return True
    if trigger == "idle_tick" and st.get("seconds_since_last_line", 999) < 8: return True
    if trigger == "screen_enter" and st.get("screen") != st.get("tutorial_screen"): return True
    return False

def silence_with_policy(tag):
    p = os.path.join(ROOT, "reports", f"eval_{tag}.jsonl")
    ok = n = 0
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if not r["meta"]["kind"].startswith("silence"): continue
        n += 1
        try: sp = json.loads(r["raw"]).get("speak")
        except Exception: sp = None
        if policy_silent(r["input"]["trigger"], r["input"]["state"]) or sp is False: ok += 1
    return round(100 * ok / n, 1) if n else None

M = [("ui", None), ("false_highlight_%", "화면에 없는 버튼"), ("locked_refusal_%", "잠김 거절"), ("locked_leak_count", "누출"),
     ("oos_refusal_%", "관계없는 질문 거절"), ("oos_near_refusal_%", "헷갈리는 질문 거절"), ("silence_accuracy_%", "침묵(모델만)"),
     ("address_term_%", "호칭"), ("register_ok_%", "말투 어미"), ("forbidden_term_%", "금지 호칭"),
     ("story_leak_count", "스토리 누출"), ("spoiler_refusal_%", "스포일러 거절")]
out = {}
for c in ("rapi", "arona", "ner"):
    for m in ("B", "C3"):
        tags = evaluation_tags(d, c, m, os.environ.get("AIGD_EVAL_PREFIX", "retrain"))
        own = [t for t in tags if t.endswith("_own")]
        cross = [t for t in tags if "_cross_" in t]
        for grp, ts in (("own", own), ("cross", cross)):
            if not ts: continue
            row = {}
            for k, _ in M:
                vals = []
                for t in ts:
                    r = d[t]["raw"]
                    v = next(vv for kk, vv in r.items() if kk.startswith("ui_target")) if k == "ui" else r.get(k)
                    if v is not None: vals.append(v)
                row[k] = round(statistics.mean(vals), 1) if vals else None
            row["silence_policy"] = available_mean([silence_with_policy(t) for t in ts])
            row["latency_p50_s"] = available_mean([d[t]["raw"].get("latency_p50_s") for t in ts], 2)
            row["latency_p95_s"] = available_mean([d[t]["raw"].get("latency_p95_s") for t in ts], 2)
            row["replacement_%"] = available_mean([d[t].get("replacement_%") for t in ts])
            row["distribution"] = "학습과 같은 분포" if grp == "own" else "일반화"
            row["sets"] = len(ts)
            out[f"{c}_{m}_{grp}"] = row
if __name__ == "__main__":
    json.dump(out, open(os.path.join(ROOT, "reports", "v3_summary_table.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in out.items(): print(k, v)
