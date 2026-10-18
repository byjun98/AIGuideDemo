import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("offline_eval_test", ROOT / "eval/eval_offline.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_string_false_is_invalid_json_contract():
    output = {"speak": "false", "line": "", "emotion": "neutral", "voice_tag": "calm_brief", "motion": "idle", "ui_target": None, "action": "none", "refusal": None}
    assert evaluation.parse(json.dumps(output)) == (None, "fail")


def test_p95_uses_nearest_rank_for_small_samples():
    assert evaluation.score([], [], [], "선생님", {}, [1, 10])["latency_p95_s"] == 10


def test_diversity_counts_only_spoken_lines():
    result = evaluation.diversity_stats([{'speak': True, 'line': 'abcd'}, {'speak': True, 'line': 'abcd'}, {'speak': False, 'line': ''}])
    assert result == {'unique_lines': 1, 'speaking_rows': 2, 'distinct_2': .5}


def test_retraining_summary_excludes_old_adapters_and_other_temperatures():
    spec = importlib.util.spec_from_file_location('summary_for_test', ROOT / 'eval/summarize_v3.py')
    summary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summary)
    reports = {'v3_arona_C3_own': {'temperature': 0}, 'retrain_arona_C3_own': {'temperature': 0},
               'retrain_arona_C3_t0p3_own': {'temperature': .3}}
    assert summary.evaluation_tags(reports, 'arona', 'C3') == ['retrain_arona_C3_own']
