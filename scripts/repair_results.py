"""Repair invalid/missing result rows without re-calling the API when possible."""
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS = PROJECT_ROOT / "results"


def fix_owl_unknown():
    path = RESULTS / "sft_results_full.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fixed = 0
    for row in data:
        if row.get("fit") != "Unknown":
            continue
        motivation = row.get("motivation") or ""
        fit_match = re.search(r'"fit"\s*:\s*"(Yes|No)"', motivation)
        if not fit_match:
            continue
        row["fit"] = fit_match.group(1)
        text_match = re.search(r'"motivation"\s*:\s*"((?:[^"\\]|\\.)*)"', motivation)
        if text_match:
            row["motivation"] = text_match.group(1).replace('\\"', '"')
        fixed += 1
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return fixed


def dedupe_baseline_errors():
    path = RESULTS / "mit_baseline_qwen35.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    good_pairs = {
        (r["listing_id"], r["profile_id"])
        for r in data
        if r.get("fit") in ("Yes", "No")
    }
    before = len(data)
    data = [
        r
        for r in data
        if not (
            r.get("fit") == "Error"
            and (r["listing_id"], r["profile_id"]) in good_pairs
        )
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return before - len(data), len(data)


def main():
    owl_fixed = fix_owl_unknown()
    removed, remaining = dedupe_baseline_errors()
    print(f"owl: fixed {owl_fixed} Unknown row(s)")
    print(f"qwen baseline: removed {removed} duplicate Error row(s) ({remaining} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())