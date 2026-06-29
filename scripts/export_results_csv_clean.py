"""
Export results to a cleaner CSV format that opens well in Excel.

Improvements over the simple export:
- UTF-8 with BOM (Excel-friendly encoding)
- Quotes around all string fields (handles commas, quotes, special chars)
- Replaces curly quotes/special chars with plain equivalents
- Truncates long motivation text to 200 chars + "..." for readability
- Adds a clean header row with short, descriptive names
"""
import json
import csv
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "results"


def clean_text(text):
    """Replace special characters that cause Excel display issues."""
    if not text:
        return ""
    # Replace unicode quotes
    text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    # Replace dashes
    text = text.replace('—', '-').replace('–', '-')
    # Replace ellipsis
    text = text.replace('…', '...')
    # Replace euro
    text = text.replace('€', 'EUR')
    # Replace other special chars
    text = text.replace('°', ' deg')
    text = text.replace('²', '^2')
    return text


def export_clean(json_file, csv_file, truncate_motivation=True):
    # Try multiple encodings (some files have BOM or cp1252)
    data = None
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']:
        try:
            with open(json_file, encoding=enc) as f:
                data = json.load(f)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    if data is None:
        print(f"[FAIL] Could not read {json_file.name}")
        return
    if not data:
        print(f"[SKIP] No data in {json_file.name}")
        return

    # Define clean column mapping
    if "sft_results" in str(json_file) or "mit_" in str(json_file):
        # Main result format
        fieldnames = [
            ("listing_id", "Apt"),
            ("listing_title", "Apt Name"),
            ("listing_rent_eur", "Rent EUR"),
            ("listing_size_mq", "Size m2"),
            ("listing_neighborhood", "Neighborhood"),
            ("profile_id", "Profile ID"),
            ("profile_gender", "Gender"),
            ("profile_national_background", "Nationality"),
            ("profile_national_background_label", "Nationality Label"),
            ("profile_income_level", "Income"),
            ("profile_income_eur", "Income EUR"),
            ("profile_employment", "Employment"),
            ("profile_marital", "Marital"),
            ("profile_children", "Kids"),
            ("fit", "Fit"),
            ("motivation", "Motivation"),
        ]
    else:
        # Generic: just use all keys
        fieldnames = [(k, k) for k in data[0].keys()]

    # Write CSV with UTF-8 BOM for Excel
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        # Header row
        writer.writerow([h for _, h in fieldnames])
        # Data rows
        for row in data:
            out_row = []
            for key, _ in fieldnames:
                v = row.get(key, "")
                if isinstance(v, str):
                    v = clean_text(v)
                    # Truncate long motivation
                    if key == "motivation" and truncate_motivation and len(v) > 200:
                        v = v[:197] + "..."
                out_row.append(v)
            writer.writerow(out_row)

    print(f"[OK] {len(data)} rows -> {csv_file.name} (clean format)")


if __name__ == "__main__":
    # Export all result files
    pairs = [
        ("sft_results.json", "sft_results_clean.csv"),
        ("batch_results.json", "batch_results_clean.csv"),
        ("clarify_test.json", "clarify_test_clean.csv"),
        ("mit_baseline.json", "mit_baseline_clean.csv"),
        ("mit_fairness.json", "mit_fairness_clean.csv"),
        ("mit_cot.json", "mit_cot_clean.csv"),
    ]
    for src, dst in pairs:
        if (RESULTS_DIR / src).exists():
            export_clean(RESULTS_DIR / src, RESULTS_DIR / dst)
        else:
            print(f"[SKIP] {src} not found")

    print("\n[INFO] Clean CSVs use UTF-8 with BOM (opens in Excel without encoding issues)")
    print("[INFO] Long motivations truncated to 200 chars for readability")
    print("[INFO] Special characters (curly quotes, dashes, euro) replaced with plain text")
