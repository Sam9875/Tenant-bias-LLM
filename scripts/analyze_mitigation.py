"""Summarize RQ4 mitigation results (owl, qwen, nex, etc.)."""
import json
import os
import sys
from collections import Counter
from pathlib import Path

try:
    from scipy.stats import chi2_contingency
except ImportError:
    chi2_contingency = None

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS = PROJECT_ROOT / "results"
def _default_suffix():
    model = (os.getenv("MODEL_NAME") or "qwen/qwen3-next-80b-a3b-instruct:free").lower()
    if "owl-alpha" in model:
        return "owl"
    if "qwen" in model:
        return "qwen"
    if "nex" in model:
        return "nex"
    return model.split("/")[-1].split(":")[0].split("-")[0]


SUFFIX = sys.argv[1] if len(sys.argv) > 1 else _default_suffix()
BG_ORDER = ["local_citizen", "eu_foreigner", "non_eu_foreigner", "refugee", "second_gen"]


def load(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def summarize(name, rows):
    fits = Counter(r["fit"] for r in rows)
    n = len(rows)
    yes = fits.get("Yes", 0)
    print(f"\n=== {name} (n={n}) ===")
    print(f"  Yes: {yes} ({100*yes/n:.1f}%)" if n else "  (empty)")
    by_bg = {}
    for bg in BG_ORDER:
        sub = [r for r in rows if r.get("profile_national_background") == bg]
        if not sub:
            continue
        y = sum(1 for r in sub if r["fit"] == "Yes")
        by_bg[bg] = (y, len(sub))
        print(f"  {bg}: {y}/{len(sub)} = {100*y/len(sub):.1f}%")
    if chi2_contingency and by_bg:
        yes_row = [by_bg.get(bg, (0, 0))[0] for bg in BG_ORDER if bg in by_bg]
        no_row = [by_bg[bg][1] - by_bg[bg][0] for bg in BG_ORDER if bg in by_bg]
        if sum(yes_row) + sum(no_row) > 0:
            chi2, p, _, _ = chi2_contingency([yes_row, no_row])
            print(f"  background chi2={chi2:.2f} p={p:.4f}")
    mot_len = [len(r.get("motivation", "")) for r in rows if r.get("motivation")]
    if mot_len:
        print(f"  motivation avg len: {sum(mot_len)/len(mot_len):.0f} chars")


def main():
    suf = f"_{SUFFIX}" if SUFFIX else ""
    files = {
        "baseline": RESULTS / f"mit_baseline{suf}.json",
        "fairness": RESULTS / f"mit_fairness{suf}.json",
        "cot": RESULTS / f"mit_cot{suf}.json",
    }
    print(f"Mitigation analysis (suffix={SUFFIX})")
    data = {k: load(p) for k, p in files.items()}
    for k, rows in data.items():
        summarize(k, rows)

    out = RESULTS / f"mitigation_summary_{SUFFIX}.json"
    summary = {}
    for k, rows in data.items():
        summary[k] = {
            "n": len(rows),
            "yes": sum(1 for r in rows if r.get("fit") == "Yes"),
            "no": sum(1 for r in rows if r.get("fit") == "No"),
        }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[OK] Wrote {out}")


if __name__ == "__main__":
    main()