"""Annotate all 115 intent test cases with their risk blast radius."""
import json
from pathlib import Path


def get_blast_radius(item: dict) -> str:
    cat = item.get("category", "")
    calls = item.get("expected_calls", [])
    if cat == "negative_forbidden_t2":
        return "T2 (destructive_privileged)"
    elif not calls:
        return "None (zero_action)"
    elif all(c["name"] == "search_files" for c in calls):
        return "T0 (read_only)"
    elif any(c["name"] in ("open_app", "set_reminder") for c in calls):
        return "T1 (reversible_write)"
    return "None (zero_action)"


def main():
    p = Path(__file__).resolve().parent.parent / "tests" / "eval" / "intents.jsonl"
    lines = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            data["blast_radius"] = get_blast_radius(data)
            lines.append(json.dumps(data))

    with p.open("w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")

    print(f"Annotated {len(lines)} intent cases with 'blast_radius' in {p}")


if __name__ == "__main__":
    main()
