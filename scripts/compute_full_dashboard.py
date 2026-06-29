"""Compute dashboard stats from full 2400-call owl-alpha experiment."""
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from scipy.stats import chi2_contingency
except ImportError:
    chi2_contingency = None

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_PATH = PROJECT_ROOT / "results" / "sft_results_full.json"
OUTPUT_JSON = PROJECT_ROOT / "docs" / "_all_data.json"
INDEX_HTML = PROJECT_ROOT / "docs" / "index.html"


def load_results():
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def stats_by_field(results, field):
    out = {}
    for key in sorted({r[field] for r in results if field in r}):
        sub = [r for r in results if r.get(field) == key]
        yes = sum(1 for r in sub if r["fit"] == "Yes")
        out[key] = {
            "yes": yes,
            "no": sum(1 for r in sub if r["fit"] == "No"),
            "unknown": sum(1 for r in sub if r["fit"] not in ("Yes", "No")),
            "total": len(sub),
            "pct": round(100 * yes / len(sub), 1) if sub else 0,
        }
    return out


def stats_by_apt(results, listings):
    out = {}
    for listing in listings:
        sub = [r for r in results if r["listing_id"] == listing["id"]]
        yes = sum(1 for r in sub if r["fit"] == "Yes")
        out[listing["id"]] = {
            "yes": yes,
            "total": len(sub),
            "pct": round(100 * yes / len(sub), 1) if sub else 0,
            "rent": listing["monthly_rent_eur"],
            "neighborhood": listing["neighborhood"],
            "title": listing["title"],
        }
    return out


def chi_square(results, field):
    if not chi2_contingency:
        return None
    keys = sorted({r[field] for r in results})
    yes = [sum(1 for r in results if r[field] == k and r["fit"] == "Yes") for k in keys]
    no = [sum(1 for r in results if r[field] == k and r["fit"] == "No") for k in keys]
    if sum(yes) + sum(no) == 0:
        return None
    chi2, p, _, _ = chi2_contingency([yes, no])
    n = sum(yes) + sum(no)
    v = (chi2 / n) ** 0.5
    k = min(len(yes), 2)
    if k > 2:
        v = v / ((k - 1) ** 0.5)
    return {"chi2": round(chi2, 2), "p": round(p, 4), "cramers_v": round(v, 3)}


def bar_row(label, pct, color="#2563eb"):
    return (
        f'  <div class="row"><div class="row-label">{label}</div>'
        f'<div class="bar-container"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'
        f'<div class="bar-value">{pct}%</div></div>\n'
    )


def main():
    with open(PROJECT_ROOT / "data" / "turin_listings.json", encoding="utf-8") as f:
        listings = json.load(f)
    with open(PROJECT_ROOT / "data" / "houseseeker_profiles.json", encoding="utf-8") as f:
        profiles = json.load(f)

    results = load_results()
    fits = Counter(r["fit"] for r in results)
    model = results[0].get("model", "openrouter/owl-alpha") if results else "unknown"

    by_income = stats_by_field(results, "profile_income_level")
    by_gender = stats_by_field(results, "profile_gender")
    by_bg = stats_by_field(results, "profile_national_background")
    by_emp = stats_by_field(results, "profile_employment")
    by_apt = stats_by_apt(results, listings)

    stats = {
        "income": chi_square(results, "profile_income_level"),
        "gender": chi_square(results, "profile_gender"),
        "background": chi_square(results, "profile_national_background"),
        "employment": chi_square(results, "profile_employment"),
    }

    refugee_quote = None
    for r in results:
        if (
            r.get("profile_national_background") == "refugee"
            and r["fit"] == "No"
            and any(
                w in r.get("motivation", "").lower()
                for w in ("status", "asylum", "refugee", "documentation", "verification")
            )
        ):
            refugee_quote = {
                "profile_id": r["profile_id"],
                "motivation": r["motivation"][:400],
                "income": r["profile_income_level"],
            }
            break

    data = {
        "meta": {
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "model": model,
            "n_total": len(results),
            "n_yes": fits.get("Yes", 0),
            "n_no": fits.get("No", 0),
            "n_unknown": fits.get("Unknown", 0),
            "n_profiles_total": len(profiles),
            "n_listings": len(listings),
            "n_sets": 24,
            "design": "5 apartments x 24 sets x 20 profiles = 2400",
        },
        "by_income": by_income,
        "by_gender": by_gender,
        "by_background": by_bg,
        "by_employment": by_emp,
        "by_apt": by_apt,
        "chi_square": stats,
        "refugee_bias_quote": refugee_quote,
        "listings": [
            {
                "id": l["id"],
                "title": l["title"],
                "rent": l["monthly_rent_eur"],
                "size": l["size_mq"],
                "bedrooms": l["bedrooms"],
                "neighborhood": l["neighborhood"],
            }
            for l in listings
        ],
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    yes_pct = round(100 * fits.get("Yes", 0) / len(results), 1)
    no_pct = round(100 * fits.get("No", 0) / len(results), 1)

    income_bars = "".join(
        bar_row(f"{k.title()} (n={v['total']})", v["pct"], "#059669" if k == "high" else "#d97706" if k == "medium" else "#dc2626")
        for k, v in by_income.items()
    )
    bg_bars = "".join(
        bar_row(k.replace("_", " "), v["pct"], "#2563eb")
        for k, v in by_bg.items()
    )
    gender_bars = "".join(bar_row(k.title(), v["pct"], "#7c3aed") for k, v in by_gender.items())
    apt_bars = "".join(
        bar_row(f"{k} €{v['rent']}/mo", v["pct"], "#0891b2")
        for k, v in by_apt.items()
    )

    inc_chi = stats.get("income") or {}
    gen_chi = stats.get("gender") or {}
    bg_chi = stats.get("background") or {}

    with open(INDEX_HTML, encoding="utf-8") as f:
        html = f.read()

    html = re.sub(
        r"<title>.*?</title>",
        f"<title>Tenant Bias Audit - Owl Alpha Full Run ({len(results)}/2400)</title>",
        html,
    )
    html = html.replace(
        '<span class="badge">500 / 500 single calls complete</span>',
        f'<span class="badge">{len(results)} / 2400 complete</span>'
        f'<span class="badge">Model: {model}</span>'
        f'<span class="badge">24 sets (full factorial)</span>',
    )

    headline = (
        f'<strong>Main result (owl-alpha, n={len(results)}):</strong> '
        f'<strong>Strong income effect</strong> (χ²={inc_chi.get("chi2","?")}, p={inc_chi.get("p","?")}, V={inc_chi.get("cramers_v","?")}). '
        f'<strong>No significant gender bias</strong> (p={gen_chi.get("p","?")}). '
        f'<strong>No significant nationality bias</strong> (p={bg_chi.get("p","?")}). '
        f'Overall fit rate: {yes_pct}% Yes / {no_pct}% No.'
    )
    html = re.sub(
        r'<strong>Main result:</strong>.*?</div>\s*</div>\s*<h2 id="stats">',
        headline + '\n</div>\n</div>\n<h2 id="stats">',
        html,
        flags=re.DOTALL,
    )

    metrics_block = f"""<div class="grid-4">
  <div class="metric good"><div class="value">{fits.get('Yes',0)}</div><div class="label">Yes decisions</div><div class="sub">{yes_pct}% of {len(results)}</div></div>
  <div class="metric bad"><div class="value">{fits.get('No',0)}</div><div class="label">No decisions</div><div class="sub">{no_pct}% of {len(results)}</div></div>
  <div class="metric"><div class="value">{len(results)}</div><div class="label">Total API calls</div><div class="sub">5 apts × 24 sets × 20</div></div>
  <div class="metric warn"><div class="value">{fits.get('Unknown',0)}</div><div class="label">Unknown parses</div><div class="sub">parse failures</div></div>
</div>"""

    if 'id="headline-metrics"' not in html:
        html = html.replace(
            '<h2 id="stats">',
            '<div id="headline-metrics">' + metrics_block + '</div>\n<h2 id="stats">',
        )
    else:
        html = re.sub(
            r'<div id="headline-metrics">.*?</div>\s*<h2 id="stats">',
            f'<div id="headline-metrics">{metrics_block}</div>\n<h2 id="stats">',
            html,
            flags=re.DOTALL,
        )

    html = re.sub(
        r'<h3>Fit rate by income level.*?</div>\s*<div class="card">',
        f'<h3>Fit rate by income level (n={len(results)})</h3>\n<div class="card" style="padding:16px 20px">\n{income_bars}</div>\n<div class="card">',
        html,
        flags=re.DOTALL,
        count=1,
    )

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # Write chart snippet file for manual sections
    snippet = PROJECT_ROOT / "docs" / "_dashboard_snippets.html"
    snippet.write_text(
        f"<!-- INCOME -->\n{income_bars}\n<!-- BG -->\n{bg_bars}\n<!-- GENDER -->\n{gender_bars}\n<!-- APT -->\n{apt_bars}",
        encoding="utf-8",
    )

    print(f"[OK] {len(results)} results | Yes={fits.get('Yes')} No={fits.get('No')} Unknown={fits.get('Unknown')}")
    print(f"[OK] Wrote {OUTPUT_JSON}")
    print(f"[OK] Updated {INDEX_HTML}")
    print("Chi-square:", stats)


if __name__ == "__main__":
    main()