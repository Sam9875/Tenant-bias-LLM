"""Export dashboard charts as PNG files to results/figures_sft/."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
DATA_JSON = PROJECT_ROOT / "docs" / "_all_data.json"
OUT_DIR = PROJECT_ROOT / "results" / "figures_sft"

BG_LABELS = ["Local", "EU", "Non-EU", "Refugee", "2nd gen"]
BG_COLORS = ["#2563eb", "#2563eb", "#2563eb", "#059669", "#2563eb"]
INCOME_LABELS = ["Low €12k", "Medium €28k", "High €60k"]
INCOME_COLORS = ["#dc2626", "#d97706", "#059669"]
ABLATION_COLORS = {"low": "#dc2626", "medium": "#d97706", "high": "#059669"}
MIT_COLORS = {"baseline": "#2563eb", "fairness": "#d97706", "cot": "#dc2626"}
MIT_LABELS = ["Baseline", "Explicit Fairness", "Chain-of-Thought"]
APT_LABELS = ["A1 €500", "A2 €1750", "A3 €890", "A4 €650", "A5 €700"]


def _bar_chart(labels, values, colors, title, ylabel="Yes rate (%)", ymax=None):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors[: len(labels)], edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylim(0, ymax or max(100, max(values) * 1.15 if values else 100))
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    plt.tight_layout()
    return fig


def _grouped_bar(labels, series, title, ymax=None):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(labels))
    n = len(series)
    width = 0.8 / n
    for i, (name, values, color) in enumerate(series):
        offset = (i - (n - 1) / 2) * width
        ax.bar(x + offset, values, width, label=name, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("Yes rate (%)")
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_ylim(0, ymax or 100)
    plt.tight_layout()
    return fig


def _save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {path.name}")


def export_model(model_key, m, mit):
    label = m["label"]
    slug = model_key

    _save(
        _bar_chart(
            INCOME_LABELS,
            m["income_pcts"],
            INCOME_COLORS,
            f"Fit rate by income — {label}",
        ),
        OUT_DIR / f"dashboard_income_{slug}.png",
    )
    _save(
        _bar_chart(
            BG_LABELS,
            m["bg_pcts"],
            BG_COLORS,
            f"Fit rate by national background — {label}",
        ),
        OUT_DIR / f"dashboard_background_{slug}.png",
    )
    _save(
        _bar_chart(
            ["Male", "Female"],
            m["gender_pcts"],
            ["#7c3aed", "#7c3aed"],
            f"Fit rate by gender — {label}",
            ymax=50,
        ),
        OUT_DIR / f"dashboard_gender_{slug}.png",
    )
    _save(
        _bar_chart(
            m["apt_labels"],
            m["apt_pcts"],
            ["#0891b2", "#dc2626", "#0891b2", "#0891b2", "#0891b2"],
            f"Fit rate by apartment — {label}",
            ymax=55,
        ),
        OUT_DIR / f"dashboard_apartment_{slug}.png",
    )
    _save(
        _grouped_bar(
            BG_LABELS,
            [
                ("Male", m["inter_m"], "#7c3aed"),
                ("Female", m["inter_f"], "#c084fc"),
            ],
            f"Gender × national background — {label}",
            ymax=60,
        ),
        OUT_DIR / f"dashboard_intersection_{slug}.png",
    )
    abl = m["ablation"]
    _save(
        _grouped_bar(
            BG_LABELS,
            [
                ("Low €12k", abl["low"], ABLATION_COLORS["low"]),
                ("Medium €28k", abl["medium"], ABLATION_COLORS["medium"]),
                ("High €60k", abl["high"], ABLATION_COLORS["high"]),
            ],
            f"Income ablation (background within income) — {label}",
        ),
        OUT_DIR / f"dashboard_ablation_{slug}.png",
    )

    base = mit["baseline"]["pct"]
    fair = mit["fairness"]["pct"]
    cot = mit["cot"]["pct"]
    _save(
        _bar_chart(
            MIT_LABELS,
            [base, fair, cot],
            [MIT_COLORS["baseline"], MIT_COLORS["fairness"], MIT_COLORS["cot"]],
            f"RQ4 mitigation conditions — {label}",
            ymax=55,
        ),
        OUT_DIR / f"dashboard_mitigation_{slug}.png",
    )

    apt_keys = ["A1", "A2", "A3", "A4", "A5"]
    _save(
        _grouped_bar(
            APT_LABELS,
            [
                ("Baseline", [mit["baseline"]["by_apt"][k] for k in apt_keys], MIT_COLORS["baseline"]),
                ("Fairness", [mit["fairness"]["by_apt"][k] for k in apt_keys], MIT_COLORS["fairness"]),
                ("CoT", [mit["cot"]["by_apt"][k] for k in apt_keys], MIT_COLORS["cot"]),
            ],
            f"RQ4 Yes rate by apartment — {label}",
            ymax=55,
        ),
        OUT_DIR / f"dashboard_mit_by_apt_{slug}.png",
    )


def main():
    if not DATA_JSON.exists():
        raise SystemExit(f"Missing {DATA_JSON}. Run dashboard data export first.")
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for key in ("owl", "qwen"):
        export_model(key, data["models"][key], data["mitigation"][key])

    n = len(list(OUT_DIR.glob("dashboard_*.png")))
    print(f"\n[OK] Exported {n} dashboard figures -> {OUT_DIR}")


if __name__ == "__main__":
    main()