"""Verify every expected API call has a valid Yes/No result."""
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
listings = json.loads((PROJECT_ROOT / "data/turin_listings.json").read_text(encoding="utf-8"))
profiles = json.loads((PROJECT_ROOT / "data/houseseeker_profiles.json").read_text(encoding="utf-8"))

SETS_24 = sorted({p["set_id"] for p in profiles})
SETS_5 = ["S01_lesn", "S04_lemy", "S11_memn", "S14_musy", "S20_hemy"]


def expected_main():
    return {
        (l["id"], p["id"])
        for l in listings
        for p in profiles
        if p["set_id"] in SETS_24
    }


def expected_mit():
    profs = [p for p in profiles if p["set_id"] in SETS_5]
    return {(l["id"], p["id"]) for l in listings for p in profs}


def audit(path, expected, label):
    if not path.exists():
        return {"label": label, "exists": False, "expected": len(expected)}
    data = json.loads(path.read_text(encoding="utf-8"))
    good = {
        (r["listing_id"], r["profile_id"])
        for r in data
        if r.get("fit") in ("Yes", "No")
    }
    bad = Counter(r.get("fit") for r in data if r.get("fit") not in ("Yes", "No"))
    missing = sorted(expected - good)
    return {
        "label": label,
        "exists": True,
        "rows": len(data),
        "valid": len(good),
        "expected": len(expected),
        "missing": missing,
        "bad": dict(bad),
        "ok": not missing and not bad,
    }


def main():
    exp_main = expected_main()
    exp_mit = expected_mit()
    all_ok = True

    print("=== MAIN AUDIT (2400 pairs) ===")
    for rel, name in [
        ("results/sft_results_full.json", "owl-alpha"),
        ("results/sft_results_qwen35.json", "qwen3.5-9b"),
    ]:
        r = audit(PROJECT_ROOT / rel, exp_main, name)
        if not r["exists"]:
            print(f"  {name}: MISSING FILE")
            all_ok = False
            continue
        status = "COMPLETE" if r["ok"] else "INCOMPLETE"
        print(
            f"  {name}: {status} | {r['valid']}/{r['expected']} valid "
            f"(rows={r['rows']}, bad={r['bad'] or 'none'})"
        )
        if r["missing"]:
            print(f"    missing {len(r['missing'])} pairs:")
            for pair in r["missing"][:10]:
                print(f"      {pair[0]} x {pair[1]}")
            if len(r["missing"]) > 10:
                print(f"      ... and {len(r['missing']) - 10} more")
            all_ok = False

    print("\n=== RQ4 MITIGATION (500 pairs per condition) ===")
    for suffix, name in [("owl", "owl-alpha"), ("qwen35", "qwen3.5-9b")]:
        print(f"  --- {name} ---")
        model_ok = True
        for cond in ["baseline", "fairness", "cot"]:
            r = audit(PROJECT_ROOT / f"results/mit_{cond}_{suffix}.json", exp_mit, cond)
            if not r["exists"]:
                print(f"    {cond}: MISSING FILE")
                model_ok = False
                continue
            status = "COMPLETE" if r["ok"] else f"INCOMPLETE ({len(r['missing'])} missing)"
            print(
                f"    {cond}: {r['valid']}/500 {status} "
                f"(rows={r['rows']}, bad={r['bad'] or 'none'})"
            )
            if not r["ok"]:
                for pair in r["missing"][:5]:
                    print(f"      missing: {pair[0]} x {pair[1]}")
                model_ok = False
        print(f"    => {'COMPLETE' if model_ok else 'INCOMPLETE'}")
        if not model_ok:
            all_ok = False
        print()

    print("=== SUMMARY ===")
    if all_ok:
        print("All expected calls have valid Yes/No results.")
    else:
        print("Some calls are missing or invalid — see above.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())