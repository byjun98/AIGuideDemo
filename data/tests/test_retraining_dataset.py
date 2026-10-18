import json
from pathlib import Path
import subprocess
import sys

from dataset_splits import check_leakage

ROOT = Path(__file__).resolve().parents[2]


def test_arona_generation_is_reproducible_and_has_disjoint_groups(tmp_path):
    for name in ("first", "second"):
        result = subprocess.run([sys.executable, str(ROOT / "data/build_dataset_v3.py"), "--character", "arona", "--pack", "pack_bluearchive.json", "--out", str(tmp_path / name)], capture_output=True)
        assert result.returncode == 0, result.stderr.decode("utf-8")
    files = sorted((tmp_path / "first").rglob("*.json*"))
    assert len(files) == 5
    for path in files:
        assert path.read_bytes() == (tmp_path / "second" / path.relative_to(tmp_path / "first")).read_bytes()
    first = tmp_path / "first"
    paths = {"train": first / "sft/arona_train.jsonl", "val": first / "sft/arona_val.jsonl", "test": first / "eval/arona_own.jsonl"}
    rows = {key: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] for key, path in paths.items()}
    check_leakage(rows)
    assert 150 <= len(rows["val"]) <= 250
    assert sum(1 for r in rows["val"] if r["meta"]["kind"] in ("spoiler", "story_fact")) >= 20
    probe = [json.loads(line) for line in (first / "eval/arona_spoiler_probe.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["meta"]["kind"] for r in probe} == {"spoiler", "story_fact"}
    for r in rows["train"]:
        if r["meta"]["kind"] == "story_fact":
            assert r["meta"]["card_group"] in [c["id"] for c in json.loads(r["messages"][1]["content"])["cards"]]
    for partition in rows:
        kinds = {r["meta"]["kind"].split(":")[0] for r in rows[partition]}
        assert {"spoiler", "story_fact", "official_line", "smalltalk"} <= kinds
        assert all("story_chapter" in json.loads(r["messages"][1]["content"])["state"] for r in rows[partition])
