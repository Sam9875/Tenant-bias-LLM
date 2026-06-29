"""Collect the best real motivation examples from the data for the dashboard."""
import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"

with open(RESULTS_DIR / "sft_results.json") as f:
    results = json.load(f)
with open(DATA_DIR / "houseseeker_profiles.json") as f:
    profiles = json.load(f)
p_lookup = {p["id"]: p for p in profiles}


def get_motivation(record, full=True):
    return record.get("motivation", "")


def find_first(filter_fn, min_len=80):
    for x in results:
        if filter_fn(x) and len(get_motivation(x)) > min_len:
            return x
    return None


def find_first_with_name(filter_fn, min_len=80, motivation_filter=None):
    for x in results:
        if filter_fn(x) and len(get_motivation(x)) > min_len:
            if motivation_filter and not motivation_filter(get_motivation(x)):
                continue
            x["name"] = p_lookup.get(x["profile_id"], {}).get("name", "?")
            return x
    return None


# 1. Strongest bias: refugee rejected with status mentioned
bias_strong = find_first_with_name(
    lambda x: x["profile_national_background"] == "refugee" and x["fit"] == "No",
    motivation_filter=lambda m: ("status" in m.lower() or "asylum" in m.lower() or "documentation" in m.lower() or "verification" in m.lower()) and "refugee" in m.lower()
)

# 2. Local vs refugee pair (same income, gender, apartment)
local_rej = find_first_with_name(
    lambda x: x["profile_national_background"] == "local_citizen"
    and x["profile_income_level"] == "medium"
    and x["profile_gender"] == "male"
    and x["fit"] == "No"
    and x["listing_id"] == "A3"
)
refugee_rej = find_first_with_name(
    lambda x: x["profile_national_background"] == "refugee"
    and x["profile_income_level"] == "medium"
    and x["profile_gender"] == "male"
    and x["fit"] == "No"
    and x["listing_id"] == "A3"
)

# 3. High income accepted (both genders, different apartments for variety)
high_female = find_first_with_name(
    lambda x: x["profile_income_level"] == "high"
    and x["profile_gender"] == "female"
    and x["fit"] == "Yes"
)
high_male = find_first_with_name(
    lambda x: x["profile_income_level"] == "high"
    and x["profile_gender"] == "male"
    and x["fit"] == "Yes"
)

# 4. Family-size rejection (1BR too small for family)
family_rej = find_first_with_name(
    lambda x: "S14" in x["profile_id"] and x["fit"] == "No",
    motivation_filter=lambda m: "small" in m.lower() or "undersized" in m.lower() or "tight" in m.lower() or "1-bedroom" in m.lower() or "1br" in m.lower()
)

# 5. Local citizen accepted
local_acc = find_first_with_name(
    lambda x: x["profile_national_background"] == "local_citizen"
    and x["fit"] == "Yes"
    and x["profile_income_level"] == "high"
)

# 6. Refugee accepted
refugee_acc = find_first_with_name(
    lambda x: x["profile_national_background"] == "refugee"
    and x["fit"] == "Yes"
    and x["profile_income_level"] in ["medium", "high"]
)

# 7. Low income local rejected (clean income-only rejection)
low_local_rej = find_first_with_name(
    lambda x: x["profile_national_background"] == "local_citizen"
    and x["profile_income_level"] == "low"
    and x["fit"] == "No"
)

# 8. Second-generation accepted
secondgen_acc = find_first_with_name(
    lambda x: x["profile_national_background"] == "second_gen"
    and x["fit"] == "Yes"
)

# 9. EU foreigner accepted
eu_acc = find_first_with_name(
    lambda x: x["profile_national_background"] == "eu_foreigner"
    and x["fit"] == "Yes"
)

# 10. Non-EU foreigner rejected
noneu_rej = find_first_with_name(
    lambda x: x["profile_national_background"] == "non_eu_foreigner"
    and x["fit"] == "No"
    and x["profile_income_level"] == "medium"
)


examples = {
    "bias_strong_refugee": bias_strong,
    "local_medium_rej": local_rej,
    "refugee_medium_rej": refugee_rej,
    "high_female_yes": high_female,
    "high_male_yes": high_male,
    "family_size_rej": family_rej,
    "local_high_yes": local_acc,
    "refugee_yes": refugee_acc,
    "low_local_rej": low_local_rej,
    "secondgen_yes": secondgen_acc,
    "eu_yes": eu_acc,
    "noneu_rej": noneu_rej,
}

# Clean
out = {}
for k, v in examples.items():
    if v:
        out[k] = {
            "profile_id": v["profile_id"],
            "name": v.get("name", "?"),
            "gender": v["profile_gender"],
            "national_background": v["profile_national_background"],
            "income_level": v["profile_income_level"],
            "income_eur": v["profile_income_eur"],
            "listing_id": v["listing_id"],
            "listing_rent": v["listing_rent_eur"],
            "fit": v["fit"],
            "motivation": v["motivation"],
        }

with open(PROJECT_ROOT / "docs" / "_real_examples.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print(f"Saved {len(out)} real examples to docs/_real_examples.json")
for k, v in out.items():
    print(f"  {k}: {v['profile_id']}")
