"""
Export all results to CSV (opens in Excel) for easy review.
"""
import json
import csv
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "results"


def export_to_csv(json_file, csv_file):
    # Try multiple encodings
    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']:
        try:
            with open(json_file, encoding=enc) as f:
                data = json.load(f)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    else:
        print(f"[FAIL] Could not read {json_file}")
        return
    if not data:
        print(f"No data in {json_file}")
        return
    fields = list(data[0].keys())
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print(f"[OK] {len(data)} rows -> {csv_file}")


if __name__ == "__main__":
    export_to_csv(RESULTS_DIR / "sft_results.json",
                  RESULTS_DIR / "sft_results.csv")
    export_to_csv(RESULTS_DIR / "batch_results.json",
                  RESULTS_DIR / "batch_results.csv")
    export_to_csv(RESULTS_DIR / "clarify_test.json",
                  RESULTS_DIR / "clarify_test.csv")
    print("\nAll CSV files ready in LLM_SFT/results/")
    print("Open in Excel by double-clicking the .csv files")
