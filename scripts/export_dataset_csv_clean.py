"""
Re-export dataset CSVs with cleaner column names for Excel readability.

Old column names: id, set_id, income_level, income_amount_eur, ...
New column names: ID, Set, Income, Income EUR, ...

Same for turin_listings.csv.
"""
import json
import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Column rename maps (old -> new, more Excel-friendly)
LISTING_COL_MAP = {
    "id": "Apt ID",
    "title": "Title",
    "address": "Address",
    "monthly_rent_eur": "Rent (EUR/mo)",
    "size_mq": "Size (m2)",
    "bedrooms": "Bedrooms",
    "bathrooms": "Bathrooms",
    "neighborhood": "Neighborhood",
    "floor": "Floor",
    "elevator": "Elevator",
    "furnished": "Furnished",
    "contract_type": "Contract",
    "price_per_mq_eur": "Price/m2 (EUR)",
    "security_deposit_eur": "Deposit (EUR)",
    "heating": "Heating",
    "description": "Description",
}

PROFILE_COL_MAP = {
    "id": "Profile ID",
    "set_id": "Set",
    "income_level": "Income",
    "income_amount_eur": "Income (EUR/yr)",
    "employment_status": "Employment",
    "marital_status": "Marital",
    "children": "Children",
    "gender": "Gender",
    "national_background": "Nationality",
    "national_background_label": "Nationality (full)",
    "name": "Name",
    "age": "Age",
}


def export(json_file, csv_file, col_map):
    """Convert JSON to CSV with renamed columns."""
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print(f"[SKIP] {json_file.name} is empty")
        return

    old_keys = list(data[0].keys())
    new_headers = [col_map.get(k, k) for k in old_keys]

    # Write with UTF-8 BOM for Excel
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(new_headers)
        for row in data:
            out_row = []
            for k in old_keys:
                v = row.get(k, "")
                # Clean up boolean-like values
                if isinstance(v, bool):
                    v = "Yes" if v else "No"
                out_row.append(v)
            writer.writerow(out_row)

    print(f"[OK] {len(data)} rows -> {csv_file.name}")
    print(f"      Columns: {' | '.join(new_headers)}")


if __name__ == "__main__":
    export(DATA_DIR / "turin_listings.json",
           DATA_DIR / "turin_listings_clean.csv",
           LISTING_COL_MAP)
    print()
    export(DATA_DIR / "houseseeker_profiles.json",
           DATA_DIR / "houseseeker_profiles_clean.csv",
           PROFILE_COL_MAP)
    print()
    print("Clean CSVs saved to data/")
    print("Opens directly in Excel with friendly column names")
