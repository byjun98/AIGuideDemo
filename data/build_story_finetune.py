import argparse, json, random
from pathlib import Path

from build_dataset_v3 import Builder, HERE, dedup_shuffle, partition_pack, self_check, write
from dataset_splits import check_leakage
from guide_common import load_pack, load_profile


def story_rows(pack, tmpl, prof, ptext, partition, seed, draws):
    split = "train" if partition == "train" else "eval"
    b = Builder(partition_pack(pack, partition, 42), tmpl, prof, ptext, split, seed, [], partition=partition)
    b.gen_spoiler(draws)
    rows = dedup_shuffle(b.out, random.Random(seed))
    by_kind = {}
    for row in rows:
        by_kind.setdefault(row["meta"]["kind"], []).append(row)
    return by_kind


def read(path):
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def line_of(row):
    return json.loads(row["messages"][2]["content"])["line"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--base", default=str(HERE / "v3/retrain_20261016"), help="1차 학습에 쓴 3분할 폴더")
    ap.add_argument("--out", default=str(HERE / "v3/story_ft_20261017"))
    ap.add_argument("--spoiler", type=int, default=240)
    ap.add_argument("--story-fact", type=int, default=160)
    ap.add_argument("--replay", type=int, default=600)
    ap.add_argument("--seed", type=int, default=1042)
    a = ap.parse_args()

    pack = load_pack(HERE / a.pack)
    ptext, prof = load_profile(HERE / f"character_{a.character}.json")
    pack = {**pack, "cards": pack["cards"] + [c for c in prof.get("story_cards", []) if c.get("training_eligible", True)]}
    tmpl = json.loads((HERE / "characters" / a.character / "templates.json").read_text(encoding="utf-8"))
    base, out = Path(a.base), Path(a.out)

    old_train = read(base / "sft" / f"{a.character}_train.jsonl")
    val = read(base / "sft" / f"{a.character}_val.jsonl")
    test = read(base / "eval" / f"{a.character}_own.jsonl")
    heldout = {line_of(r) for r in val + test} - {""}

    train_story = story_rows(pack, tmpl, prof, ptext, "train", a.seed, 6000)
    story = [r for r in train_story.get("spoiler", []) if line_of(r) not in heldout][:a.spoiler]
    story += [r for r in train_story.get("story_fact", []) if line_of(r) not in heldout][:a.story_fact]
    replay_pool = [r for r in old_train if r["meta"]["kind"] not in ("spoiler", "story_fact")]
    replay = random.Random(a.seed).sample(replay_pool, min(a.replay, len(replay_pool)))
    train = dedup_shuffle(story + replay, random.Random(a.seed))

    test_story = story_rows(pack, tmpl, prof, ptext, "test", a.seed + 1, 3000)
    probe = test_story.get("spoiler", [])[:40] + test_story.get("story_fact", [])[:30]
    probe = [r for r in probe if line_of(r) not in {line_of(t) for t in train} - {""}]

    leakage = check_leakage({"train": train + old_train, "val": val, "test": test + probe})
    self_check(train)
    self_check(probe)
    write(train, out / "sft" / f"{a.character}_train.jsonl")
    write(val, out / "sft" / f"{a.character}_val.jsonl")
    write(probe, out / "eval" / f"{a.character}_spoiler_probe.jsonl")
    kinds = lambda rows: {k: sum(1 for r in rows if r["meta"]["kind"] == k) for k in ("spoiler", "story_fact")}
    manifest = {"character": a.character, "seed": a.seed, "base": str(base), "train": len(train), "story_rows": kinds(story),
                "replay": len(replay), "probe": kinds(probe), "story_cards": {p: len([c for c in partition_pack(pack, p, 42)["cards"] if c.get("story_chapter")]) for p in ("train", "val", "test")},
                "leakage_groups": leakage}
    (out / f"{a.character}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
