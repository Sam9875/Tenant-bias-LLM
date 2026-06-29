"""One-shot: extract owl-alpha A3 baseline for RQ4 from sft_results_full.json."""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from mitigation_experiment import (  # noqa: E402
    FULL_RESULTS_BY_SUFFIX,
    SELECTED_SETS,
    extract_baseline_from_full,
)

def main():
    with open(PROJECT_ROOT / "data" / "turin_listings.json", encoding="utf-8") as f:
        listings = json.load(f)
    with open(PROJECT_ROOT / "data" / "houseseeker_profiles.json", encoding="utf-8") as f:
        profiles = json.load(f)
    listing = next(l for l in listings if l["id"] == "A3")
    test_profiles = [p for p in profiles if p["set_id"] in SELECTED_SETS]
    out = PROJECT_ROOT / "results" / "mit_baseline_owl.json"
    extract_baseline_from_full(
        [listing], test_profiles, out, "openrouter/owl-alpha", FULL_RESULTS_BY_SUFFIX["owl"]
    )

if __name__ == "__main__":
    main()