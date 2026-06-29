"""
Export listings and profiles to CSV format for review.
Run this after generating profiles and listings to see them in spreadsheet form.
"""

import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def export_listings_csv():
    with open(PROJECT_ROOT / "data" / "turin_listings.json") as f:
        listings = json.load(f)

    csv_path = PROJECT_ROOT / "data" / "turin_listings.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "title", "address", "monthly_rent_eur", "size_mq", "bedrooms", "bathrooms",
            "neighborhood", "floor", "elevator", "furnished", "contract_type",
            "price_per_mq_eur", "security_deposit_eur", "heating", "description"
        ])
        for l in listings:
            writer.writerow([
                l["id"], l["title"], l["address"], l["monthly_rent_eur"],
                l["size_mq"], l["bedrooms"], l["bathrooms"], l["neighborhood"],
                l["floor"], l["elevator"], l["furnished"], l["contract_type"],
                l["price_per_mq_eur"], l.get("security_deposit_eur", ""),
                l.get("heating", ""), l["description"]
            ])
    print(f"[OK] Saved {len(listings)} listings to {csv_path}")


def export_profiles_csv():
    with open(PROJECT_ROOT / "data" / "houseseeker_profiles.json") as f:
        profiles = json.load(f)

    csv_path = PROJECT_ROOT / "data" / "houseseeker_profiles.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "set_id", "income_level", "income_amount_eur", "employment_status",
            "marital_status", "children", "gender", "national_background",
            "national_background_label", "name", "age"
        ])
        for p in profiles:
            writer.writerow([
                p["id"], p["set_id"], p["gender"], p["national_background"],
                p["national_background_label"], p["income_level"], p["income_amount_eur"],
                p["employment_status"], p["marital_status"], p["children"],
                p["name"], p["age"]
            ])
    print(f"[OK] Saved {len(profiles)} profiles to {csv_path}")


if __name__ == "__main__":
    export_listings_csv()
    export_profiles_csv()
    print()
    print("Files ready for review:")
    print(f"  - {PROJECT_ROOT / 'data' / 'turin_listings.csv'}")
    print(f"  - {PROJECT_ROOT / 'data' / 'houseseeker_profiles.csv'}")
