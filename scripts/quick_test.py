"""Single API call smoke test — verify .env, provider, and JSON parsing before a full run."""
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from run_sft import BASE_URL, MODEL_NAME, build_prompt, call_llm, parse_response


def main():
    parser = argparse.ArgumentParser(description="One-call API smoke test")
    parser.add_argument("--model", default=None, help="Override MODEL_NAME from .env")
    args = parser.parse_args()
    model = args.model or MODEL_NAME

    listings = json.loads(
        (PROJECT_ROOT / "data/turin_listings.json").read_text(encoding="utf-8")
    )
    profiles = json.loads(
        (PROJECT_ROOT / "data/houseseeker_profiles.json").read_text(encoding="utf-8")
    )
    listing = next(l for l in listings if l["id"] == "A1")
    profile = next(p for p in profiles if p["id"] == "S01_lesn_local_citizen_male_1")

    print(f"Model:   {model}")
    print(f"API:     {BASE_URL}")
    print(f"Pair:    {listing['id']} x {profile['id']}")
    print("Calling API...\n")

    response = call_llm(build_prompt(listing, profile), model=model)
    fit, motivation = parse_response(response)

    print(f"Fit:         {fit}")
    print(f"Motivation:  {motivation}")
    if fit not in ("Yes", "No"):
        print("\n[FAIL] Could not parse Yes/No from response.")
        print(f"Raw (first 300 chars): {response[:300]}")
        return 1
    print("\n[OK] API and JSON parsing work — ready for a full run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())