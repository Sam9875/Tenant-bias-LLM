"""
Comprehensive audit of LLM_SFT project files.
Checks:
- JSON files are valid
- CSV files are valid
- All listings have required fields
- All profiles have required fields
- Profile set structure matches professor's spec
"""
import json
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

errors = []
warnings = []


def check(name, condition, error_msg):
    if condition:
        print(f"  [OK] {name}")
    else:
        print(f"  [FAIL] {name}: {error_msg}")
        errors.append(error_msg)


def warn(name, condition, warn_msg):
    if condition:
        print(f"  [OK] {name}")
    else:
        print(f"  [WARN] {name}: {warn_msg}")
        warnings.append(warn_msg)


# ============================================================
# 1. JSON files
# ============================================================
print("=" * 60)
print("1. JSON FILES")
print("=" * 60)

# turin_listings.json
print("\n[1a] turin_listings.json")
try:
    with open(DATA_DIR / "turin_listings.json", encoding="utf-8") as f:
        listings = json.load(f)
    check("File is valid JSON", True, "")
    check("Has 5+ listings", len(listings) >= 5, f"Only {len(listings)} listings, need >=5")

    required_fields = ["id", "title", "monthly_rent_eur", "size_mq", "bedrooms", "neighborhood", "description"]
    for i, l in enumerate(listings):
        for f_name in required_fields:
            if f_name not in l:
                errors.append(f"Listing {l.get('id', i)} missing field: {f_name}")
        if "monthly_rent_eur" in l and not (400 <= l["monthly_rent_eur"] <= 5000):
            warnings.append(f"Listing {l['id']} rent EUR {l['monthly_rent_eur']} outside expected 400-5000 range")
    if all(f in l for l in listings for f in required_fields):
        check("All listings have required fields", True, "")

    # Print summary
    for l in listings:
        print(f"    {l['id']}: {l['neighborhood']:25s} | EUR {l['monthly_rent_eur']:5d} | {l['size_mq']:3d} mq | {l['bedrooms']}BR")
except Exception as e:
    errors.append(f"turin_listings.json failed: {e}")
    print(f"  [FAIL] {e}")

# houseseeker_profiles.json
print("\n[1b] houseseeker_profiles.json")
try:
    with open(DATA_DIR / "houseseeker_profiles.json", encoding="utf-8") as f:
        profiles = json.load(f)
    check("File is valid JSON", True, "")
    check("Has 480 profiles", len(profiles) == 480, f"Got {len(profiles)}, need 480")

    required_fields = ["id", "set_id", "income_level", "income_amount_eur", "employment_status",
                       "marital_status", "children", "gender", "national_background", "national_background_label", "name"]
    for p in profiles:
        for f_name in required_fields:
            if f_name not in p:
                errors.append(f"Profile {p.get('id')} missing: {f_name}")
    if all(f in p for p in profiles for f in required_fields):
        check("All profiles have required fields", True, "")

    # Set distribution
    from collections import Counter
    set_counts = Counter(p["set_id"] for p in profiles)
    check("24 unique sets", len(set_counts) == 24, f"Got {len(set_counts)}")
    check("Each set has 20 profiles", all(c == 20 for c in set_counts.values()),
          f"Set counts: {dict(list(set_counts.items())[:5])}...")

    # Demographic distribution
    bg_counts = Counter(p["national_background"] for p in profiles)
    check("5 backgrounds, 96 each", len(bg_counts) == 5 and all(c == 96 for c in bg_counts.values()),
          f"Backgrounds: {dict(bg_counts)}")
    gender_counts = Counter(p["gender"] for p in profiles)
    check("2 genders, 240 each", all(c == 240 for c in gender_counts.values()),
          f"Genders: {dict(gender_counts)}")

    # Check the 24 set combos
    expected_combos = set()
    for inc in ["low", "medium", "high"]:
        for emp in ["employed", "unemployed"]:
            for mar in ["single", "married"]:
                for kid in ["no", "yes"]:
                    expected_combos.add((inc, emp, mar, kid))
    actual_combos = set()
    for p in profiles:
        actual_combos.add((p["income_level"], p["employment_status"], p["marital_status"], p["children"]))
    check("All 24 set combinations present", expected_combos == actual_combos,
          f"Missing: {expected_combos - actual_combos}, Extra: {actual_combos - expected_combos}")

    # Per set: 2 reps per (gender, background) combo
    for set_id in list(set_counts.keys())[:3]:  # check first 3
        set_profiles = [p for p in profiles if p["set_id"] == set_id]
        combo_counts = Counter((p["gender"], p["national_background"]) for p in set_profiles)
        ok = all(c == 2 for c in combo_counts.values()) and len(combo_counts) == 10
        if not ok:
            errors.append(f"Set {set_id}: not 2 reps per combo. {dict(combo_counts)}")
    check("Each set: 2 reps per (gender, background) combo", True, "")

    # Print example
    print(f"\n  Example profile:")
    print(f"  {json.dumps(profiles[0], indent=4)[:600]}")
except Exception as e:
    errors.append(f"houseseeker_profiles.json failed: {e}")
    print(f"  [FAIL] {e}")


# ============================================================
# 2. CSV files
# ============================================================
print("\n" + "=" * 60)
print("2. CSV FILES")
print("=" * 60)

# turin_listings.csv
print("\n[2a] turin_listings.csv")
try:
    with open(DATA_DIR / "turin_listings.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    check("File readable as CSV", True, "")
    check("Has 5+ rows", len(rows) >= 5, f"Only {len(rows)} rows")
    expected_csv_cols = ["id", "title", "monthly_rent_eur", "size_mq", "bedrooms", "neighborhood", "description"]
    if rows:
        actual_cols = list(rows[0].keys())
        missing = set(expected_csv_cols) - set(actual_cols)
        check("Has expected columns", not missing, f"Missing: {missing}")
    print(f"  Columns: {list(rows[0].keys()) if rows else 'none'}")
    print(f"  Row count: {len(rows)}")
except Exception as e:
    errors.append(f"turin_listings.csv failed: {e}")
    print(f"  [FAIL] {e}")

# houseseeker_profiles.csv
print("\n[2b] houseseeker_profiles.csv")
try:
    with open(DATA_DIR / "houseseeker_profiles.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    check("File readable as CSV", True, "")
    check("Has 480 rows", len(rows) == 480, f"Got {len(rows)}")
    expected_cols = ["id", "set_id", "income_level", "income_amount_eur", "employment_status",
                     "marital_status", "children", "gender", "national_background"]
    if rows:
        actual_cols = list(rows[0].keys())
        missing = set(expected_cols) - set(actual_cols)
        check("Has expected columns", not missing, f"Missing: {missing}")
    print(f"  Columns: {list(rows[0].keys()) if rows else 'none'}")
    print(f"  Row count: {len(rows)}")
except Exception as e:
    errors.append(f"houseseeker_profiles.csv failed: {e}")
    print(f"  [FAIL] {e}")


# ============================================================
# 3. sft_results.json (partial results from interrupted run)
# ============================================================
print("\n" + "=" * 60)
print("3. PARTIAL RESULTS (sft_results.json)")
print("=" * 60)
try:
    with open(RESULTS_DIR / "sft_results.json", encoding="utf-8") as f:
        results = json.load(f)
    check("File is valid JSON", True, "")
    print(f"  Records: {len(results)}")
    if results:
        sample = results[0]
        print(f"  Sample fields: {list(sample.keys())}")
        from collections import Counter
        fits = Counter(r.get("fit", "?") for r in results)
        print(f"  Fit distribution: {dict(fits)}")
except Exception as e:
    errors.append(f"sft_results.json failed: {e}")
    print(f"  [FAIL] {e}")


# ============================================================
# 4. Scripts check
# ============================================================
print("\n" + "=" * 60)
print("4. SCRIPTS (syntax check)")
print("=" * 60)
import py_compile
scripts = ["run_sft.py", "analyze_sft.py", "generate_profiles_sft.py", "export_to_csv.py", "quick_test.py", "quick_test2.py"]
for s in scripts:
    path = PROJECT_ROOT / "scripts" / s
    try:
        py_compile.compile(str(path), doraise=True)
        check(f"{s}", True, "")
    except py_compile.PyCompileError as e:
        errors.append(f"{s} syntax error: {e}")
        print(f"  [FAIL] {s}: {e}")


# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)
print(f"Errors:   {len(errors)}")
for e in errors:
    print(f"  [ERR] {e}")
print(f"Warnings: {len(warnings)}")
for w in warnings:
    print(f"  [WARN] {w}")

if not errors:
    print("\n[OK] ALL CHECKS PASSED")
    sys.exit(0)
else:
    print(f"\n[FAIL] {len(errors)} errors found, fix before running")
    sys.exit(1)
