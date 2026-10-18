import re
import csv
from pathlib import Path

EXCLUDED_NER = ("한 때 한가닥", "개인 교습 나들이", "교단의 성찬 파티", "日")


def parse_dialogue(character, path):
    if character == "rapi":
        records, seen = [], set()
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("source_key") != "namu_wiki_rapi_base_dialogue" or row.get("speaker") != "라피": continue
                if row.get("is_training_allowed", "1") != "1": continue
                line = row["raw_text"].strip()
                if line in seen or not re.search(r"(니다|니까|시오)[.!?~…⋯]*$", line): continue
                seen.add(line)
                flags = re.findall(r"chapter_(\d+)", row.get("required_flags", ""))
                records.append({"line": line, "situation": row.get("scene_id") or "대화",
                                "official_group": row.get("scene_id", "") + ":" + row.get("dialogue_function", ""),
                                "story_chapter": max(map(int, flags), default=0), "source": "official_line", "source_file": Path(path).name})
        return records
    records, seen = [], set()
    section, situation, chapter = "", "", 0
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if character == "arona" and "1부 최종편 클리어 이후 —" in text: chapter = 4
        if text.startswith("## "):
            section = text[3:]
            if character == "arona" and "Vol.0" in section: chapter = 6
        elif text.startswith("["):
            section = text
        if text.startswith(("상황:", "- 상황:")):
            situation = text.split(":", 1)[1].strip()
        speaker = "아로나" if character == "arona" else "네르"
        if not text.startswith(speaker + ":"): continue
        if character == "ner" and (any(term in situation for term in EXCLUDED_NER) or not ("기본 사복" in situation or section == "[친밀도]")):
            continue
        line = text.split(":", 1)[1].strip().strip("「」“”\"")
        line = line.replace("(자기 이름)", "선생님")
        if not line or line in seen or not re.search(r"(요|죠|니다|니까|시오)[.!?~…⋯]*$", line): continue
        seen.add(line)
        group = section + ":" + re.sub(r"\s*\d+", "", situation)
        records.append({"line": line, "situation": situation, "official_group": group, "story_chapter": chapter,
                        "source": "official_line", "source_file": str(Path(path).name)})
    return records
