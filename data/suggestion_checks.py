import argparse
import json
from pathlib import Path


def suggestion_questions(pack, story, bank):
    names = [system['name'] for system in pack['systems']]
    questions = {item['question'] for item in bank.get('questions', [])}
    for template in bank.get('normal_questions', []):
        if '{system}' in template:
            questions.update(template.replace('{system}', name) for name in names)
        else:
            questions.add(template)
    questions.update(bank.get('locked_question', '').replace('{system}', name) for name in names)
    questions.update(bank.get('spoiler_question', '').replace('{marker}', chapter['spoiler_markers'][0])
                     for chapter in story.get('chapters', []) if chapter.get('spoiler_markers'))
    questions.update(bank.get('oos_questions', []))
    questions.add(bank.get('fallback_question', ''))
    return questions - {''}


def check_suggestions(rows, questions):
    inputs = {json.loads(row['messages'][1]['content']).get('player_input') for row in rows}
    overlap = sorted(inputs & set(questions))
    if overlap:
        raise ValueError(f'suggestions overlap training: {overlap}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    packs = [json.loads(path.read_text(encoding='utf-8')) for path in root.glob('pack_*.json')]
    packs.append(json.loads((root / 'game_pack_counters.json').read_text(encoding='utf-8')))
    for character in ('rapi', 'arona', 'ner'):
        folder = root / 'characters' / character
        bank_path = folder / 'suggestions.json'
        bank = json.loads(bank_path.read_text(encoding='utf-8'))
        story = json.loads((folder / 'story.json').read_text(encoding='utf-8'))
        questions = set().union(*(suggestion_questions(pack, story, bank) for pack in packs))
        rows = [json.loads(line) for line in (args.dataset / 'sft' / f'{character}_train.jsonl').read_text(encoding='utf-8').splitlines()]
        check_suggestions(rows, questions)
        print(character, len(questions), 'suggestions: no training utterance overlap')
