"""
RQ3 (intersectional) + income ablation analysis for owl-alpha full run.

Income ablation strategies:
  1) Stratify by income level (low / medium / high)
  2) Medium-income-only slice (richest signal, ~40% Yes)
  3) Within-set pooling: income, employment, marital, children held constant per set_id

Outputs:
  - results/rq3_ablation_results.json
  - results/figures_sft/ablation_*.png
  - Refresh dashboard: python scripts/update_dashboard.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import chi2_contingency, chi2

PROJECT_ROOT = Path(__file__).parent.parent
import argparse
import os

def _default_results_path():
    env = os.getenv("RESULTS_FILE")
    if env:
        return PROJECT_ROOT / "results" / env
    return PROJECT_ROOT / "results" / "sft_results_qwen35.json"
OUTPUT_JSON = PROJECT_ROOT / "results" / "rq3_ablation_results.json"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures_sft"
BG_ORDER = ["local_citizen", "eu_foreigner", "non_eu_foreigner", "second_gen", "refugee"]
BG_LABELS = {
    "local_citizen": "Local",
    "eu_foreigner": "EU",
    "non_eu_foreigner": "Non-EU",
    "second_gen": "2nd gen",
    "refugee": "Refugee",
}
INCOME_ORDER = ["low", "medium", "high"]


def load_df(results_path):
    with open(results_path, encoding="utf-8") as f:
        rows = json.load(f)
    df = pd.DataFrame(rows)
    df = df[df["fit"].isin(["Yes", "No"])].copy()
    df["yes"] = (df["fit"] == "Yes").astype(int)
    return df


def chi_square_2xk(yes_counts, no_counts):
    """2 x k contingency: row0=yes, row1=no."""
    table = [list(yes_counts), list(no_counts)]
    if sum(yes_counts) + sum(no_counts) == 0:
        return None
    chi2_val, p, _, _ = chi2_contingency(table)
    n = sum(yes_counts) + sum(no_counts)
    k = len(yes_counts)
    v = (chi2_val / n) ** 0.5
    if k > 2:
        v = v / ((min(k, 2) - 1) ** 0.5) if k > 1 else 0
    cramers_v = round(float(v), 3)
    return {
        "chi2": round(float(chi2_val), 2),
        "p": round(float(p), 4),
        "cramers_v": cramers_v,
        "n": int(n),
    }


def fit_rate_table(df, group_col):
    out = {}
    for key in sorted(df[group_col].dropna().unique()):
        sub = df[df[group_col] == key]
        yes = int(sub["yes"].sum())
        total = len(sub)
        out[key] = {
            "yes": yes,
            "no": total - yes,
            "total": total,
            "pct": round(100 * yes / total, 1) if total else 0,
        }
    return out


def gender_by_background_table(df):
    """Rows=background, cols=male/female fit %."""
    rows = []
    for bg in BG_ORDER:
        sub = df[df["profile_national_background"] == bg]
        male = sub[sub["profile_gender"] == "male"]
        female = sub[sub["profile_gender"] == "female"]
        m_yes = int(male["yes"].sum()) if len(male) else 0
        f_yes = int(female["yes"].sum()) if len(female) else 0
        m_pct = round(100 * m_yes / len(male), 1) if len(male) else 0
        f_pct = round(100 * f_yes / len(female), 1) if len(female) else 0
        rows.append({
            "background": bg,
            "label": BG_LABELS[bg],
            "male_yes": m_yes,
            "male_total": len(male),
            "male_pct": m_pct,
            "female_yes": f_yes,
            "female_total": len(female),
            "female_pct": f_pct,
            "gap_pp": round(f_pct - m_pct, 1),
        })
    return rows


def cochran_q_gender_homogeneity(df):
    """
    RQ3 test from REPORT.md: is the gender odds ratio homogeneous across
    the 5 national-background groups?
    Each group -> 2x2 [male_yes, male_no, female_yes, female_no].
    """
    tables = []
    group_stats = []
    for bg in BG_ORDER:
        sub = df[df["profile_national_background"] == bg]
        a = int(sub[(sub["profile_gender"] == "male") & (sub["yes"] == 1)].shape[0])
        b = int(sub[(sub["profile_gender"] == "male") & (sub["yes"] == 0)].shape[0])
        c = int(sub[(sub["profile_gender"] == "female") & (sub["yes"] == 1)].shape[0])
        d = int(sub[(sub["profile_gender"] == "female") & (sub["yes"] == 0)].shape[0])
        group_stats.append({"background": bg, "male_yes": a, "male_no": b, "female_yes": c, "female_no": d})
        if min(a, b, c, d) > 0:
            tables.append((a, b, c, d))

    if len(tables) < 2:
        return {"Q": None, "p": None, "df": None, "n_tables": len(tables), "groups": group_stats}

    log_ors, weights = [], []
    for a, b, c, d in tables:
        log_or = np.log((a * d) / (b * c))
        se2 = 1 / a + 1 / b + 1 / c + 1 / d
        log_ors.append(log_or)
        weights.append(1 / se2)

    weighted = sum(lo * w for lo, w in zip(log_ors, weights)) / sum(weights)
    Q = sum(w * (lo - weighted) ** 2 for lo, w in zip(log_ors, weights))
    df_q = len(tables) - 1
    p = float(1 - chi2.cdf(Q, df_q))
    return {
        "Q": round(float(Q), 2),
        "p": round(p, 4),
        "df": int(df_q),
        "n_tables": len(tables),
        "groups": group_stats,
        "interpretation": "homogeneous gender effect" if p >= 0.05 else "heterogeneous gender effect across backgrounds",
    }


def logistic_interaction_test(df):
    """Likelihood-ratio test: does gender x background improve fit beyond additive?"""
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    d = df.copy()
    d["gender_male"] = (d["profile_gender"] == "male").astype(int)
    d["income_ord"] = d["profile_income_level"].map({"low": 0, "medium": 1, "high": 2})
    d["employed"] = (d["profile_employment"] == "employed").astype(int)
    d["married"] = (d["profile_marital"] == "married").astype(int)
    d["has_children"] = (d["profile_children"] == "yes").astype(int)

    apt_terms = ["listing_rent_eur", "listing_size_mq"]
    if "listing_bedrooms" in d.columns:
        apt_terms.append("listing_bedrooms")
    apt_rhs = " + ".join(apt_terms)
    formula_add = (
        "yes ~ gender_male + C(profile_national_background, Treatment('local_citizen')) "
        "+ income_ord + employed + married + has_children "
        f"+ {apt_rhs}"
    )
    formula_int = formula_add + " + gender_male:C(profile_national_background, Treatment('local_citizen'))"

    m0 = smf.logit(formula_add, data=d).fit(disp=0)
    m1 = smf.logit(formula_int, data=d).fit(disp=0)
    lr_stat = 2 * (m1.llf - m0.llf)
    lr_df = len(m1.params) - len(m0.params)
    lr_p = float(1 - chi2.cdf(lr_stat, lr_df))

    return {
        "lr_chi2": round(float(lr_stat), 2),
        "lr_df": int(lr_df),
        "lr_p": round(lr_p, 4),
        "significant_interaction": lr_p < 0.05,
    }


def logistic_no_income(df):
    """Demographic effects controlling for set (income ablated via set fixed effects)."""
    import statsmodels.formula.api as smf

    d = df.copy()
    if "profile_set_id" not in d.columns:
        d["profile_set_id"] = d["profile_id"].str.extract(r"^(S\d+_[a-z]{4})")[0]

    formula = (
        "yes ~ gender_male + C(profile_national_background, Treatment('local_citizen')) "
        "+ C(profile_set_id) + C(listing_id)"
    )
    try:
        m = smf.logit(formula, data=d).fit(disp=0, maxiter=200)
        coefs = {}
        for var in ["gender_male"]:
            if var in m.params:
                coefs[var] = {"coef": round(float(m.params[var]), 3), "p": round(float(m.pvalues[var]), 4)}
        for bg in BG_ORDER[1:]:
            key = f"C(profile_national_background, Treatment('local_citizen'))[T.{bg}]"
            if key in m.params:
                coefs[bg] = {"coef": round(float(m.params[key]), 3), "p": round(float(m.pvalues[key]), 4)}
        return {"converged": True, "coefficients": coefs, "aic": round(float(m.aic), 1)}
    except Exception as e:
        return {"converged": False, "error": str(e)}


def stratified_ablation(df):
    """Chi-square for gender and background within each income stratum."""
    out = {}
    for inc in INCOME_ORDER:
        sub = df[df["profile_income_level"] == inc]
        g = fit_rate_table(sub, "profile_gender")
        b = fit_rate_table(sub, "profile_national_background")
        male_yes = g.get("male", {}).get("yes", 0)
        male_no = g.get("male", {}).get("no", 0)
        fem_yes = g.get("female", {}).get("yes", 0)
        fem_no = g.get("female", {}).get("no", 0)
        gender_chi = chi_square_2xk([male_yes, fem_yes], [male_no, fem_no])

        yes_bg = [b.get(bg, {}).get("yes", 0) for bg in BG_ORDER if bg in b]
        no_bg = [b.get(bg, {}).get("no", 0) for bg in BG_ORDER if bg in b]
        bg_chi = chi_square_2xk(yes_bg, no_bg) if yes_bg else None

        out[inc] = {
            "n": len(sub),
            "gender": g,
            "background": b,
            "gender_chi": gender_chi,
            "background_chi": bg_chi,
            "gender_gap_pp": round(
                g.get("female", {}).get("pct", 0) - g.get("male", {}).get("pct", 0), 1
            ),
        }
    return out


def heatmap_figure(df, path, title):
    pivot = df.pivot_table(
        values="yes",
        index="profile_national_background",
        columns="profile_gender",
        aggfunc="mean",
    ).reindex(BG_ORDER)
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.heatmap(pivot, annot=True, fmt=".1%", cmap="RdYlGn", vmin=0, vmax=1, ax=ax)
    ax.set_title(title, fontsize=13)
    ax.set_ylabel("National background")
    ax.set_xlabel("Gender")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def ablation_bar_figure(stratified, path):
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)
    colors = {"low": "#dc2626", "medium": "#d97706", "high": "#059669"}
    for ax, inc in zip(axes, INCOME_ORDER):
        b = stratified[inc]["background"]
        labels = [BG_LABELS[k] for k in BG_ORDER if k in b]
        vals = [b[k]["pct"] for k in BG_ORDER if k in b]
        ax.bar(labels, vals, color="#2563eb", alpha=0.85)
        ax.set_title(f"{inc.title()} income (n={stratified[inc]['n']})")
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylabel("Yes %")
    fig.suptitle("Income ablation: background effect within each income stratum", fontsize=13)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def html_table_gender_bg(rows):
    lines = [
        '<table class="stat-table">',
        "<tr><th>Background</th><th>Male</th><th>Female</th><th>Gap (F−M)</th></tr>",
    ]
    for r in rows:
        lines.append(
            f"<tr><td>{r['label']}</td>"
            f"<td>{r['male_yes']}/{r['male_total']} = {r['male_pct']}%</td>"
            f"<td>{r['female_yes']}/{r['female_total']} = {r['female_pct']}%</td>"
            f"<td>{r['gap_pp']:+.1f}pp</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def html_ablation_table(stratified):
    lines = [
        '<table class="stat-table">',
        "<tr><th>Income stratum</th><th>n</th><th>Gender χ² (p)</th><th>Background χ² (p)</th><th>Gender gap</th></tr>",
    ]
    for inc in INCOME_ORDER:
        s = stratified[inc]
        gc = s["gender_chi"] or {}
        bc = s["background_chi"] or {}
        g_sig = "sig" if gc.get("p", 1) < 0.05 else "ns"
        b_sig = "sig" if bc.get("p", 1) < 0.05 else "ns"
        lines.append(
            f"<tr><td><strong>{inc.title()}</strong></td><td>{s['n']}</td>"
            f"<td class=\"stat-sig {g_sig}\">{gc.get('chi2','—')}, p={gc.get('p','—')}</td>"
            f"<td class=\"stat-sig {b_sig}\">{bc.get('chi2','—')}, p={bc.get('p','—')}</td>"
            f"<td>{s['gender_gap_pp']:+.1f}pp</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=None, help="Results JSON filename in results/")
    args = parser.parse_args()
    results_path = PROJECT_ROOT / "results" / args.results if args.results else _default_results_path()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = load_df(results_path)
    model = df["model"].iloc[0] if "model" in df.columns and len(df) else "unknown"

    gender_bg = gender_by_background_table(df)
    cochran = cochran_q_gender_homogeneity(df)
    interaction = logistic_interaction_test(df)
    stratified = stratified_ablation(df)
    no_income_fe = logistic_no_income(df)

    heatmap_figure(df, FIGURES_DIR / "heatmap_bg_x_gender_full.png", "RQ3: Fit rate by background × gender (full sample)")
    med = df[df["profile_income_level"] == "medium"]
    heatmap_figure(med, FIGURES_DIR / "heatmap_bg_x_gender_medium.png", "Ablation: background × gender (medium income only)")
    ablation_bar_figure(stratified, FIGURES_DIR / "ablation_background_by_income.png")

    results = {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "model": model,
            "n": len(df),
            "source": str(results_path.name),
        },
        "rq3": {
            "gender_by_background": gender_bg,
            "cochran_q": cochran,
            "logistic_interaction_lr": interaction,
        },
        "income_ablation": {
            "stratified": stratified,
            "medium_only": {
                "n": len(med),
                "background": fit_rate_table(med, "profile_national_background"),
                "gender": fit_rate_table(med, "profile_gender"),
                "gender_by_background": gender_by_background_table(med),
                "cochran_q": cochran_q_gender_homogeneity(med),
            },
            "set_fixed_effects_logit": no_income_fe,
            "note": (
                "Stratification holds income constant per stratum. "
                "Set fixed-effects logit holds income+employment+marital+children constant via profile_set_id."
            ),
        },
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[OK] n={len(df)} model={model}")
    print(f"[OK] Cochran Q: {cochran}")
    print(f"[OK] Interaction LR: {interaction}")
    print(f"[OK] Stratified ablation:")
    for inc in INCOME_ORDER:
        s = stratified[inc]
        print(f"  {inc}: gender p={s['gender_chi']['p'] if s['gender_chi'] else '—'}, bg p={s['background_chi']['p'] if s['background_chi'] else '—'}")
    print(f"[OK] Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()