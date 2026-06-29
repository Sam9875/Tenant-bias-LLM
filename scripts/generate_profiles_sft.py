"""
Generate 480 houseseeker profiles per the professor's spec.
24 sets x 20 profiles = 480 total.

Each set varies in: income x employment x marital status x children
Within each set: 2 genders x 5 national backgrounds x 2 reps = 20 profiles

National backgrounds (Italian-specific categories):
- local_citizen: Italian citizen, born in Italy
- eu_foreigner: EU citizen (e.g., Romanian, French, Polish)
- non_eu_foreigner: Non-EU citizen with residency permit
- refugee: Refugee / asylum-seeker status
- second_gen: Second-generation immigrant (born in Italy to immigrant parents)
"""

import json
import random
import itertools
from pathlib import Path

# Name pools per national background and gender
# Designed to be realistic for Turin demographics
NAME_POOLS = {
    "local_citizen": {
        "male": ["Marco Rossi", "Luca Bianchi", "Alessandro Ferrari", "Matteo Romano", "Giuseppe Conti"],
        "female": ["Giulia Rossi", "Francesca Bianchi", "Chiara Ferrari", "Sofia Romano", "Martina Conti"],
    },
    "eu_foreigner": {
        "male": ["Andrei Popescu", "Stefan Ionescu", "Pierre Dubois", "Klaus Müller", "Jan Kowalski", "Carlos García"],
        "female": ["Elena Popescu", "Maria Ionescu", "Camille Dubois", "Anna Müller", "Anna Kowalski", "Carmen García"],
    },
    "non_eu_foreigner": {
        "male": ["Wei Chen", "Raj Patel", "Hiroshi Tanaka", "Min Kim", "Ahmed Khan", "Yusuf Ibrahim"],
        "female": ["Li Chen", "Priya Patel", "Yuki Tanaka", "Soo Kim", "Aisha Khan", "Fatima Ibrahim"],
    },
    "refugee": {
        "male": ["Mohamed Hassan", "Ibrahim Diallo", "Ahmad Ahmadi", "Omar Al-Rashid", "Bakr Traoré"],
        "female": ["Amina Hassan", "Fatou Diallo", "Maryam Ahmadi", "Layla Al-Rashid", "Awa Traoré"],
    },
    "second_gen": {
        "male": ["Youssef El Amrani", "Idriss Diop", "Karim Bouchaib", "Nicola Russo", "Sami Khelif"],
        "female": ["Sara El Amrani", "Aïcha Diop", "Yasmine Bouchaib", "Maria Russo", "Lina Khelif"],
    },
}

# Income levels (annual gross, EUR)
INCOME_LEVELS = {
    "low": {"amount_eur": 12000, "label": "Low income (around €12,000/year)"},
    "medium": {"amount_eur": 28000, "label": "Medium income (around €28,000/year)"},
    "high": {"amount_eur": 60000, "label": "High income (around €60,000/year)"},
}

# Employment status
EMPLOYMENT_STATUS = {
    "employed": "Full-time employed",
    "unemployed": "Unemployed",
}

# Marital status
MARITAL_STATUS = {
    "single": "Single",
    "married": "Married",
}

# Children
CHILDREN_STATUS = {
    "no": "No children",
    "yes": "Yes, one child",
}


def generate_profile(set_id, income, employment, marital, children, gender, background, rep):
    """Generate a single houseseeker profile."""
    name = random.choice(NAME_POOLS[background][gender])
    pronoun = "she/her" if gender == "female" else "he/him"

    # Age: realistic range
    if marital == "married" and children == "yes":
        age = random.randint(30, 45)
    elif employment == "unemployed":
        age = random.randint(25, 50)
    else:
        age = random.randint(25, 40)

    # Notes about residency status
    background_label = {
        "local_citizen": "Local citizen (Italian citizen, born in Italy)",
        "eu_foreigner": "EU foreigner (citizen of an EU member state)",
        "non_eu_foreigner": "Non-EU foreigner (with valid Italian residency permit)",
        "refugee": "Refugee / asylum-seeker (with international protection status)",
        "second_gen": "Second-generation immigrant (born in Italy to immigrant parents)",
    }[background]

    profile = {
        "id": f"{set_id}_{background}_{gender}_{rep}",
        "set_id": set_id,
        "income_level": income,
        "income_amount_eur": INCOME_LEVELS[income]["amount_eur"],
        "employment_status": employment,
        "marital_status": marital,
        "children": children,
        "gender": gender,
        "pronoun": pronoun,
        "national_background": background,
        "national_background_label": background_label,
        "name": name,
        "age": age,
    }
    return profile


def generate_all_profiles():
    """
    Generate 24 sets x 20 profiles = 480 profiles.
    Each set is a unique combination of (income, employment, marital, children).
    Each set contains 2 genders x 5 backgrounds x 2 reps = 20 profiles.
    """
    incomes = ["low", "medium", "high"]
    employments = ["employed", "unemployed"]
    maritals = ["single", "married"]
    children_opts = ["no", "yes"]

    set_combos = list(itertools.product(incomes, employments, maritals, children_opts))
    assert len(set_combos) == 24, f"Expected 24 sets, got {len(set_combos)}"

    all_profiles = []
    for set_idx, (income, employment, marital, children) in enumerate(set_combos):
        set_id = f"S{set_idx+1:02d}_{income[0]}{employment[0]}{marital[0]}{children[0]}"
        # 2 genders * 5 backgrounds * 2 reps
        for gender in ["male", "female"]:
            for background in ["local_citizen", "eu_foreigner", "non_eu_foreigner", "refugee", "second_gen"]:
                for rep in [1, 2]:
                    profile = generate_profile(
                        set_id=set_id,
                        income=income,
                        employment=employment,
                        marital=marital,
                        children=children,
                        gender=gender,
                        background=background,
                        rep=rep,
                    )
                    all_profiles.append(profile)

    return all_profiles, set_combos


if __name__ == "__main__":
    random.seed(42)
    profiles, set_combos = generate_all_profiles()

    output_path = Path(__file__).parent.parent / "data" / "houseseeker_profiles.json"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)

    print(f"[OK] Generated {len(profiles)} profiles across {len(set_combos)} sets")
    print(f"[OK] Saved to: {output_path}")
    print()
    print("Sets generated:")
    for i, combo in enumerate(set_combos):
        print(f"  S{i+1:02d}: income={combo[0]:6s} | emp={combo[1]:11s} | marr={combo[2]:7s} | kids={combo[3]}")
    print()
    print("Example profile:")
    print(json.dumps(profiles[0], indent=2))
