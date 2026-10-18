import hashlib
import json
import random

PARTITIONS = ("train", "val", "test")
RESPONSE_POOLS = ("howto", "howto_away", "next_lobby", "next_here", "next_away", "done", "locked", "fail1", "fail2", "idle", "enter", "oos", "spoiler")


def allocate(groups, seed=42, val_ratio=.1, test_ratio=.15):
    groups = sorted(set(groups))
    random.Random(seed).shuffle(groups)
    n = len(groups)
    test = max(1, round(n * test_ratio)) if n > 1 else 0
    val = max(1, round(n * val_ratio)) if n > 2 else 0
    return {g: "test" if i < test else "val" if i < test + val else "train" for i, g in enumerate(groups)}


def annotate_templates(template, seed=42):
    for key in RESPONSE_POOLS:
        pool = template.get(key, [])
        if not pool or isinstance(pool[0], dict):
            continue
        allocation = allocate(range(len(pool)), seed)
        template[key] = [{"line": text, "split": allocation[i], "template_id": f"{key}:{i}"} for i, text in enumerate(pool)]
    for i, qa in enumerate(template.get("persona_qa", [])):
        if qa["answers"] and isinstance(qa["answers"][0], str):
            allocation = allocate(range(len(qa["answers"])), seed + i)
            qa["answers"] = [{"line": text, "split": allocation[j], "template_id": f"persona:{i}:{j}"} for j, text in enumerate(qa["answers"])]
    return template


def flatten_templates(template):
    owners = {}
    def walk(value):
        if isinstance(value, dict) and "line" in value and "template_id" in value:
            owners[value["line"]] = (value["split"], value["template_id"])
            return value["line"]
        if isinstance(value, dict): return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list): return [walk(v) for v in value]
        return value
    flat = walk(template)
    for key in ("howto_here", "howto_here_target"):
        if key in flat: owners[flat[key]] = ("train", key)
    return flat, owners


def allocate_states(groups, step_systems, seed=42):
    result = {}
    for category in ("lobby", "tutorial", "other"):
        selected = []
        for group in groups:
            step, screen = group.split(":", 1)
            kind = "lobby" if screen == "lobby" else "tutorial" if screen == step_systems[step] else "other"
            if kind == category: selected.append(group)
        result.update(allocate(selected, seed))
    return result


def check_leakage(partitions):
    seen = {key: {} for key in ("line", "template_ids", "state_group", "card_group", "scene_group", "official_group")}
    for partition, rows in partitions.items():
        for row in rows:
            answer = json.loads(row["messages"][2]["content"])
            values = {**row["meta"], "line": answer["line"]}
            for key, owners in seen.items():
                items = values.get(key) or []
                if isinstance(items, str): items = [items]
                for item in items:
                    if item in owners and owners[item] != partition:
                        raise ValueError(f"Split leakage ({key}): {owners[item]} / {partition}: {item}")
                    owners[item] = partition
    return {key: len(owners) for key, owners in seen.items()}


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
