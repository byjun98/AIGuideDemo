import argparse
import hashlib
import json
from pathlib import Path
import re


def chapter_for(character, heading, text, history=False):
    value = heading + "\n" + text
    if character == "arona":
        stages = [(6, ("2부", "Vol.0", "화분")), (5, ("1부 이후", "셰마타")),
                  (4, ("최종편", "프라나", "프레나파테스", "아트라하시스", "A.R.O.N.A"))]
        if history: stages += [(3, ("Vol.3", "에덴조약")), (2, ("Vol.2", "데카그라마톤")), (1, ("Vol.1",))]
    else:
        stages = [(2, ("시즌 3 이후", "선배 사제 복귀")), (1, ("과거", "불량", "목수", "갱생", "계시를 받고"))]
    return max((index for index, markers in stages if any(m in value for m in markers)), default=0)


def make_cards(character, path, history=False):
    cards = []
    heading = "기본 설정"
    source = Path(path)
    for number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or set(line) <= {"=", "-"}: continue
        if line.startswith(("[", "##")) and len(line) < 130:
            heading = line.strip("[]# ")
            continue
        if not re.match(r"^(?:- |\d+\. )", line): continue
        text = re.sub(r"^(?:- |\d+\. )", "", line)
        if len(text) < 25 or any(term in text for term in ("정리 기준:", "원문 URL:", "주의:", "사용법")): continue
        tags = [name for name, markers in (("uncertain", ("추정", "가능성", "해석", "평가")), ("discarded", ("폐기", "초기 설정"))) if any(m in text for m in markers)]
        prefix = "[" + ", ".join(tags) + "] " if tags else ""
        digest = hashlib.sha256((source.name + ":" + str(number) + ":" + text).encode()).hexdigest()[:12]
        cards.append({"id": f"{character}_source_{digest}", "system": None, "story_chapter": chapter_for(character, heading, text, history),
                      "min_affection": 100 if character == "ner" and "편지" in heading + text else 0,
                      "text": prefix + heading + ": " + text, "tags": tags,
                      "source": source.name, "source_line": number, "training_eligible": False})
    return cards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--character", required=True, choices=("arona", "ner"))
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cards = make_cards(args.character, args.settings) + make_cards(args.character, args.history, True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.character, len(cards), "runtime-only lore cards")


if __name__ == "__main__": main()
