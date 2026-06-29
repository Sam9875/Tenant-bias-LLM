#!/usr/bin/env python3
import json
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "results" / "sft_results_full.json"
OUT = ROOT / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

BLUE = "#3b6fd6"

BG_ORDER = ["local_citizen", "eu_foreigner", "non_eu_foreigner",
            "second_gen", "refugee"]
BG_LABEL = {"local_citizen": "Local", "eu_foreigner": "EU",
            "non_eu_foreigner": "Non-EU", "second_gen": "2nd gen",
            "refugee": "Refugee"}
INC_ORDER = ["low", "medium", "high"]
INC_LABEL = {"low": "Low\n(€12k)", "medium": "Medium\n(€28k)",
             "high": "High\n(€60k)"}


def load():
    d = json.load(open(SRC))
    if isinstance(d, dict):
        d = d.get("results", d)
    # normalise the second_gen key
    for r in d:
        if r.get("profile_national_background") == "second_generation":
            r["profile_national_background"] = "second_gen"
    # keep ALL rows so denominators match the report tables (Yes / Total),
    # where unparsed outputs count toward Total but not toward Yes.
    return d


def rate(rows, key, k):
    yes = sum(1 for r in rows if r[key] == k and r["fit"] == "Yes")
    tot = sum(1 for r in rows if r[key] == k)
    return 100.0 * yes / tot if tot else 0.0


def fig_income(rows):
    vals = [rate(rows, "profile_income_level", k) for k in INC_ORDER]
    fig, ax = plt.subplots(figsize=(5.2, 4))
    bars = ax.bar([INC_LABEL[k] for k in INC_ORDER], vals, color=BLUE, width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}%",
                ha="center", fontsize=11)
    ax.set_ylabel("Approval rate (%)")
    ax.set_ylim(0, 100)
    ax.set_title("owl-alpha: approval by income band")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "owl_income.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_background(rows):
    vals = [rate(rows, "profile_national_background", k) for k in BG_ORDER]
    colors = [BLUE if k != "refugee" else "#d6783b" for k in BG_ORDER]
    fig, ax = plt.subplots(figsize=(5.6, 4))
    bars = ax.bar([BG_LABEL[k] for k in BG_ORDER], vals, color=colors, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.0, f"{v:.1f}%",
                ha="center", fontsize=10)
    ax.set_ylabel("Approval rate (%)")
    ax.set_ylim(0, 70)
    ax.set_title("owl-alpha: approval by national background")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "owl_background.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_heatmap(rows):
    genders = ["female", "male"]
    mat = np.zeros((len(BG_ORDER), 2))
    for i, bg in enumerate(BG_ORDER):
        for j, g in enumerate(genders):
            sub = [r for r in rows if r["profile_national_background"] == bg
                   and r["profile_gender"] == g]
            yes = sum(1 for r in sub if r["fit"] == "Yes")
            mat[i, j] = yes / len(sub) if sub else 0.0
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(2), labels=genders)
    ax.set_yticks(range(len(BG_ORDER)),
                  labels=[BG_LABEL[k] for k in BG_ORDER])
    ax.set_xlabel("Gender")
    ax.set_ylabel("National background")
    ax.set_title("owl-alpha: approval by background × gender (full sample)")
    for i in range(len(BG_ORDER)):
        for j in range(2):
            ax.text(j, i, f"{mat[i, j]*100:.1f}%", ha="center", va="center",
                    fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(OUT / "owl_heatmap_bg_x_gender.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_ablation(rows):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    counts = {k: sum(1 for r in rows if r["profile_income_level"] == k)
              for k in INC_ORDER}
    titles = {"low": f"Low income (n={counts['low']})",
              "medium": f"Medium income (n={counts['medium']})",
              "high": f"High income (n={counts['high']})"}
    for ax, inc in zip(axes, INC_ORDER):
        sub = [r for r in rows if r["profile_income_level"] == inc]
        vals = [rate(sub, "profile_national_background", k) for k in BG_ORDER]
        ax.bar([BG_LABEL[k] for k in BG_ORDER], vals, color=BLUE, width=0.7)
        ax.set_title(titles[inc])
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=30)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Approval rate (%)")
    fig.suptitle("owl-alpha income ablation: background effect within each income stratum",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT / "owl_ablation_by_income.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main():
    rows = load()
    print(f"loaded {len(rows)} owl-alpha rows")

    fig_heatmap(rows)     # owl_heatmap_bg_x_gender.png  (RQ3)
    fig_ablation(rows)    # owl_ablation_by_income.png
    fig_income(rows)      # owl_income.png               (Income Discrimination)
    fig_background(rows)  # owl_background.png            (RQ2)
    print("wrote 4 figures to", OUT)


if __name__ == "__main__":
    main()
