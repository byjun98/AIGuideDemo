import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(os.environ.get('AIGD_ROOT', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / 'server'))


def run(character, dataset):
    evaluator = ROOT / 'eval/eval_offline.py'
    for source in sorted((dataset / 'eval').glob(f'{character}_*.jsonl')):
        suffix = source.stem[len(character) + 1:]
        tag = f'runtime_{character}_C3_{suffix}'
        command = [sys.executable, '-u', str(evaluator), '--eval', str(source), '--character', character,
                   '--model', f'lora:{character}', '--tag', tag, '--runtime']
        with (ROOT / 'logs' / f'eval_{tag}.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    own = dataset / 'eval' / f'{character}_own.jsonl'
    rows = [json.loads(line) for line in own.read_text(encoding='utf-8').splitlines()]
    from guide_server import PACKS, profile, sampling_policy
    _, prof = profile(character)
    prof = {**prof, 'generation': {**prof.get('generation', {}), 'diversity_enabled': True}}
    probes, seen = [], set()
    for row in rows:
        if row['meta']['kind'].split(':')[0] not in ('smalltalk', 'persona'): continue
        user = json.loads(row['messages'][1]['content'])
        question = user.get('player_input')
        if question in seen or sampling_policy(user['trigger'], question, user['state'], prof, PACKS[row['meta']['game']])[1] < 2: continue
        seen.add(question)
        probes.append(row)
        if len(probes) == 3: break
    if not probes:
        raise RuntimeError(f'No held-out casual probes for {character}')
    for index, probe in enumerate(probes):
        probe_path = ROOT / 'reports' / f'diversity_probe_{character}_{index}.jsonl'
        probe_path.write_text(json.dumps(probe, ensure_ascii=False) + '\n', encoding='utf-8')
        for policy in ('baseline', 'runtime'):
            tag = f'diversity_{character}_{index}_{policy}'
            command = [sys.executable, '-u', str(evaluator), '--eval', str(probe_path), '--character', character,
                       '--model', f'lora:{character}', '--tag', tag, '--repeat', '10', '--temperature', '0.3']
            if policy == 'runtime':
                command.append('--runtime')
            with (ROOT / 'logs' / f'eval_{tag}.log').open('w', encoding='utf-8') as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='data/v3/retrain_20261016')
    args = parser.parse_args()
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'logs').mkdir(exist_ok=True)
    for name in ('rapi', 'arona', 'ner'):
        run(name, ROOT / args.dataset)
