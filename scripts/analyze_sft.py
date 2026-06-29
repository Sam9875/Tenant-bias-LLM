"""
Analyze SFT experiment results.

1) Export to Excel
2) Logistic regression: P(fit=Yes) ~ income + employment + marital + children + gender + nationality + apartment_controls
3) Test if gender/nationality coefficients are significant after controlling for legitimate factors
4) Generate figures and tables
"""

import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import statsmodels.api as sm
from statsmodels.formula.api import logit

PROJECT_ROOT = Path(__file__).parent.parent
import os as _os
_results = PROJECT_ROOT / "results"
_active_model = (_os.getenv("MODEL_NAME") or "qwen/qwen3-next-80b-a3b-instruct:free").lower()
_model_outputs = [
    ("qwen", _results / "sft_results_qwen.json"),
    ("owl-alpha", _results / "sft_results_full.json"),
    ("nex", _results / "sft_results_nex.json"),
]
if _os.getenv("RESULTS_FILE"):
    RESULTS_PATH = _results / _os.getenv("RESULTS_FILE")
else:
    RESULTS_PATH = None
    for key, path in _model_outputs:
        if key in _active_model:
            RESULTS_PATH = path
            break
    if RESULTS_PATH is None:
        for _, path in _model_outputs:
            if path.exists():
                RESULTS_PATH = path
                break
    if RESULTS_PATH is None:
        RESULTS_PATH = _results / "sft_results.json"
OUTPUT_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = OUTPUT_DIR / "figures_sft"
FIGURES_DIR.mkdir(exist_ok=True, parents=True)


def load_data():
    with open(RESULTS_PATH) as f:
        results = json.load(f)
    df = pd.DataFrame(results)
    print(f"[OK] Loaded {len(df)} evaluations")
    print(f"  Fit distribution: {df['fit'].value_counts().to_dict()}")
    return df


def export_excel(df):
    """Export to Excel with multiple sheets."""
    excel_path = OUTPUT_DIR / "sft_results.xlsx"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # Sheet 1: Raw results
        df.to_excel(writer, sheet_name="Raw_Results", index=False)

        # Sheet 2: Pivot - fit rate by apartment x background
        pivot_bg = df.pivot_table(
            values="fit",
            index="listing_id",
            columns="profile_national_background",
            aggfunc=lambda x: (x == "Yes").mean(),
        )
        pivot_bg.to_excel(writer, sheet_name="Fit_Rate_by_Apt_Background")

        # Sheet 3: Pivot - fit rate by apartment x gender
        pivot_gender = df.pivot_table(
            values="fit",
            index="listing_id",
            columns="profile_gender",
            aggfunc=lambda x: (x == "Yes").mean(),
        )
        pivot_gender.to_excel(writer, sheet_name="Fit_Rate_by_Apt_Gender")

        # Sheet 4: Fit rate by background and income
        pivot_income = df.pivot_table(
            values="fit",
            index="profile_income_level",
            columns="profile_national_background",
            aggfunc=lambda x: (x == "Yes").mean(),
        )
        pivot_income.to_excel(writer, sheet_name="Fit_Rate_by_Income_Background")

        # Sheet 5: Pivot - fit rate by apartment x income
        pivot_apt_inc = df.pivot_table(
            values="fit",
            index="listing_id",
            columns="profile_income_level",
            aggfunc=lambda x: (x == "Yes").mean(),
        )
        pivot_apt_inc.to_excel(writer, sheet_name="Fit_Rate_by_Apt_Income")

        # Sheet 6: Summary statistics
        summary = df.groupby("profile_national_background").agg(
            n=("fit", "count"),
            fit_rate=("fit", lambda x: (x == "Yes").mean()),
        ).reset_index()
        summary.to_excel(writer, sheet_name="Summary_by_Background", index=False)

    print(f"[OK] Excel saved to: {excel_path}")
    return excel_path


def fit_logistic_regression(df):
    """
    Logistic regression: P(fit=Yes) ~ demographic + housing_controls
    Key test: are gender/nationality coefficients significant AFTER controlling for legitimate factors?
    """
    print("\n" + "=" * 60)
    print("LOGISTIC REGRESSION")
    print("=" * 60)

    # Prepare data
    df = df.copy()
    df["fit_binary"] = (df["fit"] == "Yes").astype(int)

    # Dummy coding
    df["gender_male"] = (df["profile_gender"] == "male").astype(int)
    df["employed"] = (df["profile_employment"] == "employed").astype(int)
    df["married"] = (df["profile_marital"] == "married").astype(int)
    df["has_children"] = (df["profile_children"] == "yes").astype(int)

    # Income as ordinal
    income_map = {"low": 0, "medium": 1, "high": 2}
    df["income_ord"] = df["profile_income_level"].map(income_map)

    # National background dummies (reference: local_citizen)
    bg_dummies = pd.get_dummies(df["profile_national_background"], prefix="bg", drop_first=False)
    bg_dummies = bg_dummies.drop(columns=["bg_local_citizen"])  # reference

    # Build feature matrix
    X = pd.concat([
        df[["gender_male", "employed", "married", "has_children", "income_ord"]],
        df[["listing_rent_eur", "listing_size_mq", "listing_bedrooms"]],
        bg_dummies,
    ], axis=1).astype(float)
    X = sm.add_constant(X)
    y = df["fit_binary"]

    # Fit
    model = sm.Logit(y, X)
    result = model.fit(disp=0)
    print(result.summary())

    # Save to file
    with open(OUTPUT_DIR / "logistic_regression.txt", "w") as f:
        f.write(result.summary().as_text())

    # Extract key coefficients
    print("\n" + "=" * 60)
    print("KEY COEFFICIENTS (after controlling for income, employment, marital, children, apartment)")
    print("=" * 60)
    for var in ["gender_male", "bg_eu_foreigner", "bg_non_eu_foreigner", "bg_refugee", "bg_second_gen"]:
        if var in result.params:
            coef = result.params[var]
            pval = result.pvalues[var]
            sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else ""
            direction = "FAVORED" if coef > 0 else "PENALIZED"
            print(f"  {var:25s}: coef={coef:+.3f}  p={pval:.4f} {sig:3s}  {direction}")

    return result


def generate_figures(df):
    """Generate the figures your professor asked for."""
    print("\n" + "=" * 60)
    print("GENERATING FIGURES")
    print("=" * 60)

    # Figure 1: Fit rate by national background (overall)
    fig, ax = plt.subplots(figsize=(10, 6))
    bg_order = ["local_citizen", "eu_foreigner", "non_eu_foreigner", "second_gen", "refugee"]
    fit_by_bg = df.groupby("profile_national_background")["fit"].apply(lambda x: (x == "Yes").mean())
    fit_by_bg = fit_by_bg.reindex(bg_order)
    colors = ["#2ecc71", "#3498db", "#9b59b6", "#e67e22", "#e74c3c"]
    bars = ax.bar(fit_by_bg.index, fit_by_bg.values, color=colors)
    ax.set_ylabel("Fit Rate (Yes %)", fontsize=12)
    ax.set_xlabel("National Background", fontsize=12)
    ax.set_title("Overall Fit Rate by National Background (Controlling for Apartment)", fontsize=14)
    ax.set_ylim(0, 1)
    plt.xticks(rotation=20, ha="right")
    for bar, val in zip(bars, fit_by_bg.values):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.02, f"{val:.1%}",
                ha="center", fontsize=11, fontweight="bold")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fit_rate_by_background.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] fit_rate_by_background.png")

    # Figure 2: Fit rate by apartment and national background
    fig, ax = plt.subplots(figsize=(12, 6))
    pivot = df.pivot_table(values="fit", index="listing_id", columns="profile_national_background",
                            aggfunc=lambda x: (x == "Yes").mean())
    pivot = pivot[bg_order]
    pivot.plot(kind="bar", ax=ax, color=colors)
    ax.set_ylabel("Fit Rate (Yes %)", fontsize=12)
    ax.set_xlabel("Apartment", fontsize=12)
    ax.set_title("Fit Rate by Apartment and National Background", fontsize=14)
    ax.set_ylim(0, 1)
    ax.legend(title="National Background", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fit_rate_by_apt_and_background.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] fit_rate_by_apt_and_background.png")

    # Figure 3: Fit rate by income and background
    fig, ax = plt.subplots(figsize=(10, 6))
    pivot2 = df.pivot_table(values="fit", index="profile_income_level", columns="profile_national_background",
                             aggfunc=lambda x: (x == "Yes").mean())
    pivot2 = pivot2[bg_order]
    pivot2.plot(kind="bar", ax=ax, color=colors)
    ax.set_ylabel("Fit Rate (Yes %)", fontsize=12)
    ax.set_xlabel("Income Level", fontsize=12)
    ax.set_title("Fit Rate by Income and National Background", fontsize=14)
    ax.set_ylim(0, 1)
    ax.legend(title="National Background", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fit_rate_by_income_and_background.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] fit_rate_by_income_and_background.png")

    # Figure 4: Heatmap of fit rate by background x gender
    fig, ax = plt.subplots(figsize=(8, 6))
    pivot3 = df.pivot_table(values="fit", index="profile_national_background", columns="profile_gender",
                             aggfunc=lambda x: (x == "Yes").mean())
    pivot3 = pivot3.reindex(bg_order)
    sns.heatmap(pivot3, annot=True, fmt=".2f", cmap="RdYlGn", vmin=0, vmax=1, ax=ax)
    ax.set_title("Fit Rate by National Background × Gender", fontsize=14)
    ax.set_ylabel("National Background")
    ax.set_xlabel("Gender")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "fit_rate_background_x_gender.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] fit_rate_background_x_gender.png")

    # Figure 5: Coefficient plot from logistic regression
    # Done separately after regression is fit

    print(f"\n[OK] All figures saved to: {FIGURES_DIR}")


def main():
    df = load_data()

    # Filter to clean responses
    df_clean = df[df["fit"].isin(["Yes", "No"])].copy()
    print(f"[OK] After filtering to Yes/No: {len(df_clean)} (from {len(df)})")

    # 1) Excel export
    export_excel(df_clean)

    # 2) Logistic regression
    result = fit_logistic_regression(df_clean)

    # 3) Figures
    generate_figures(df_clean)

    # 4) Coefficient plot
    print("\n" + "=" * 60)
    print("GENERATING COEFFICIENT PLOT")
    print("=" * 60)

    coef_names = ["gender_male", "bg_eu_foreigner", "bg_non_eu_foreigner", "bg_refugee", "bg_second_gen",
                  "employed", "married", "has_children", "income_ord"]
    coef_labels = ["Male", "EU foreigner", "Non-EU foreigner", "Refugee", "2nd-gen",
                   "Employed", "Married", "Has children", "Income (ord)"]
    coefs = [result.params.get(n, 0) for n in coef_names]
    pvals = [result.pvalues.get(n, 1) for n in coef_names]
    conf_int = result.conf_int()
    ci_low = [conf_int.loc[n, 0] if n in conf_int.index else 0 for n in coef_names]
    ci_high = [conf_int.loc[n, 1] if n in conf_int.index else 0 for n in coef_names]
    errors = [(c - cl, ch - c) for c, cl, ch in zip(coefs, ci_low, ci_high)]
    err_low = [e[0] for e in errors]
    err_high = [e[1] for e in errors]

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = ["red" if "foreigner" in l.lower() or "refugee" in l.lower() or "male" in l.lower() or "gen" in l.lower()
              else "steelblue" for l in coef_labels]
    y_pos = np.arange(len(coef_labels))
    ax.barh(y_pos, coefs, xerr=[err_low, err_high], color=colors, alpha=0.7, capsize=5)
    ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(coef_labels)
    ax.set_xlabel("Log-Odds Coefficient (95% CI)", fontsize=12)
    ax.set_title("Logistic Regression: P(fit=Yes)\nRed = demographic, Blue = legitimate factor", fontsize=14)
    ax.invert_yaxis()
    for i, (c, p) in enumerate(zip(coefs, pvals)):
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        ax.text(c, i, f" {c:+.2f} {sig}", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "logistic_coefficients.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] logistic_coefficients.png")


if __name__ == "__main__":
    main()
