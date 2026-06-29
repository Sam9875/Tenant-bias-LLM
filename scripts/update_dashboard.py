"""
Rebuild dual-model dashboard: owl-alpha + qwen3.5-9b (both preserved).

Usage:
  python scripts/update_dashboard.py
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from scipy.stats import chi2_contingency
except ImportError:
    chi2_contingency = None

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_HTML = PROJECT_ROOT / "docs" / "index.html"
OUTPUT_JSON = PROJECT_ROOT / "docs" / "_all_data.json"
TARGET_N = 2400

BG_ORDER = ["local_citizen", "eu_foreigner", "non_eu_foreigner", "second_gen", "refugee"]
BG_CHART_ORDER = ["local_citizen", "eu_foreigner", "non_eu_foreigner", "refugee", "second_gen"]
BG_CHART_LABELS = ["Local", "EU", "Non-EU", "Refugee", "2nd gen"]
INCOME_ORDER = ["low", "medium", "high"]
APT_ORDER = ["A1", "A2", "A3", "A4", "A5"]

MODELS = {
    "owl": {
        "label": "openrouter/owl-alpha",
        "results": "sft_results_full.json",
        "mit_suffix": "owl",
    },
    "qwen": {
        "label": "qwen3.5-9b",
        "results": "sft_results_qwen35.json",
        "mit_suffix": "qwen35",
    },
}


def load_json(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pct_yes(rows, **filters):
    sub = rows
    for k, v in filters.items():
        sub = [r for r in sub if r.get(k) == v]
    if not sub:
        return 0.0
    yes = sum(1 for r in sub if r["fit"] == "Yes")
    return round(100 * yes / len(sub), 1)


def stats_by_field(results, field):
    out = {}
    for key in sorted({r[field] for r in results if field in r}):
        sub = [r for r in results if r.get(field) == key]
        yes = sum(1 for r in sub if r["fit"] == "Yes")
        out[key] = {
            "yes": yes,
            "no": sum(1 for r in sub if r["fit"] == "No"),
            "total": len(sub),
            "pct": round(100 * yes / len(sub), 1) if sub else 0,
        }
    return out


def chi_square(results, field):
    if not chi2_contingency:
        return {"chi2": None, "p": None, "cramers_v": None}
    keys = sorted({r[field] for r in results if field in r})
    yes = [sum(1 for r in results if r[field] == k and r["fit"] == "Yes") for k in keys]
    no = [sum(1 for r in results if r[field] == k and r["fit"] == "No") for k in keys]
    if sum(yes) + sum(no) == 0:
        return {"chi2": None, "p": None, "cramers_v": None}
    chi2, p, _, _ = chi2_contingency([yes, no])
    n = sum(yes) + sum(no)
    v = (chi2 / n) ** 0.5
    if len(yes) > 2:
        v = v / ((min(len(yes), 2) - 1) ** 0.5)
    return {"chi2": round(float(chi2), 2), "p": round(float(p), 4), "cramers_v": round(float(v), 3)}


def build_bundle(results_path, listings):
    raw = load_json(results_path)
    clean = [r for r in raw if r.get("fit") in ("Yes", "No")]
    fits = Counter(r["fit"] for r in raw)
    n = len(raw)
    by_income = stats_by_field(clean, "profile_income_level")
    by_gender = stats_by_field(clean, "profile_gender")
    by_bg = stats_by_field(clean, "profile_national_background")
    by_apt = {}
    apt_labels = []
    apt_pcts = []
    for listing in listings:
        sub = [r for r in clean if r["listing_id"] == listing["id"]]
        yes = sum(1 for r in sub if r["fit"] == "Yes")
        by_apt[listing["id"]] = {
            "pct": round(100 * yes / len(sub), 1) if sub else 0,
            "rent": listing["monthly_rent_eur"],
        }
    for aid in APT_ORDER:
        if aid in by_apt:
            apt_labels.append(f"{aid} €{by_apt[aid]['rent']}")
            apt_pcts.append(by_apt[aid]["pct"])
    inter_m = []
    inter_f = []
    for bg in BG_CHART_ORDER:
        inter_m.append(pct_yes(clean, profile_national_background=bg, profile_gender="male"))
        inter_f.append(pct_yes(clean, profile_national_background=bg, profile_gender="female"))
    ablation = {
        inc: [pct_yes(clean, profile_income_level=inc, profile_national_background=bg) for bg in BG_CHART_ORDER]
        for inc in INCOME_ORDER
    }
    refugee_pct = by_bg.get("refugee", {}).get("pct", 0)
    others = [by_bg[k]["pct"] for k in by_bg if k != "refugee"]
    others_avg = round(sum(others) / len(others), 1) if others else 0
    return {
        "n": n,
        "fits": dict(fits),
        "yes_pct": round(100 * fits.get("Yes", 0) / n, 1) if n else 0,
        "no_pct": round(100 * fits.get("No", 0) / n, 1) if n else 0,
        "income_pcts": [by_income[k]["pct"] for k in INCOME_ORDER if k in by_income],
        "bg_pcts": [by_bg[k]["pct"] for k in BG_CHART_ORDER if k in by_bg],
        "gender_pcts": [by_gender["male"]["pct"], by_gender["female"]["pct"]],
        "apt_labels": apt_labels,
        "apt_pcts": apt_pcts,
        "inter_m": inter_m,
        "inter_f": inter_f,
        "ablation": ablation,
        "chi": {
            "income": chi_square(clean, "profile_income_level"),
            "gender": chi_square(clean, "profile_gender"),
            "background": chi_square(clean, "profile_national_background"),
        },
        "refugee_pct": refugee_pct,
        "others_avg": others_avg,
        "by_gender": by_gender,
    }


def build_mitigation(suffix):
    results_dir = PROJECT_ROOT / "results"
    out = {}
    for cond in ("baseline", "fairness", "cot"):
        rows = load_json(results_dir / f"mit_{cond}_{suffix}.json")
        clean = [r for r in rows if r.get("fit") in ("Yes", "No")]
        yes = sum(1 for r in clean if r["fit"] == "Yes")
        n = len(clean)
        out[cond] = {
            "n": n,
            "yes": yes,
            "pct": round(100 * yes / n, 1) if n else 0,
            "by_apt": {aid: pct_yes(clean, listing_id=aid) for aid in APT_ORDER},
        }
    return out


def chart_grid_html(prefix, title, n, model_label):
    p = prefix
    return f"""
<h2 id="charts-{prefix}">Results Charts — {model_label} (n={n})</h2>
<div class="grid-2">
  <div class="chart-box"><h4>Fit rate by income level</h4><canvas id="chartIncome{p}"></canvas></div>
  <div class="chart-box"><h4>Fit rate by national background</h4><canvas id="chartBackground{p}"></canvas></div>
</div>
<div class="grid-2">
  <div class="chart-box"><h4>Fit rate by gender</h4><canvas id="chartGender{p}"></canvas></div>
  <div class="chart-box"><h4>Fit rate by apartment (rent tier)</h4><canvas id="chartApartment{p}"></canvas></div>
</div>
<div class="chart-box"><h4>Gender × national background</h4><canvas id="chartIntersection{p}"></canvas></div>
<div class="chart-box"><h4>Income ablation (background within income stratum)</h4><canvas id="chartAblation{p}"></canvas></div>
"""


def headline_html(key, bundle, model_label):
    chi = bundle["chi"]
    inc = chi["income"]
    bg = chi["background"]
    gen = chi["gender"]
    partial = "" if bundle["n"] >= TARGET_N else " — partial run"
    bg_p = bg.get("p")
    gen_p = gen.get("p")
    bg_sig = "Significant national-background effect" if bg_p is not None and bg_p < 0.05 else "No significant national-background effect"
    gen_sig = "No significant gender bias" if gen_p is not None and gen_p >= 0.05 else "Significant gender gap"
    return (
        f'<div class="callout good"><strong>{model_label} (n={bundle["n"]}{partial}):</strong> '
        f'<strong>Strong income effect</strong> (χ²={inc["chi2"]}, V={inc["cramers_v"]}). '
        f'<strong>{bg_sig}</strong> (χ²={bg["chi2"]}, p={bg["p"]}, V={bg["cramers_v"]}) — '
        f'refugees {bundle["refugee_pct"]}% vs ~{bundle["others_avg"]}% others. '
        f'<strong>{gen_sig}</strong> (p={gen["p"]}). '
        f'Overall: {bundle["yes_pct"]}% Yes / {bundle["no_pct"]}% No.</div>'
    )


def rq3_detail_charts_html(bundles, chart_kind):
    """Dual-model chart canvases for RQ3/ablation sections (unique IDs)."""
    title = (
        "Background × gender (fit rate)"
        if chart_kind == "intersection"
        else "Background fit rate by income stratum (ablation)"
    )
    id_stem = "chartIntersectionRq3" if chart_kind == "intersection" else "chartAblationRq3"
    blocks = []
    for key in bundles:
        cap = key.capitalize()
        label = MODELS[key]["label"]
        blocks.append(
            f'<div class="chart-box" style="margin-top:16px;">'
            f'<h4>{title} — {label}</h4>'
            f'<canvas id="{id_stem}{cap}"></canvas></div>'
        )
    return "\n".join(blocks)


def _append_intersection_chart(lines, canvas_id, bundle):
    lines.append(f"  new Chart(document.getElementById('{canvas_id}'), {{")
    lines.append("    type: 'bar',")
    lines.append(f"    data: {{ labels: bgLabels, datasets: [")
    lines.append(f"      {{ label: 'Male', data: {json.dumps(bundle['inter_m'])}, backgroundColor: '#7c3aed' }},")
    lines.append(f"      {{ label: 'Female', data: {json.dumps(bundle['inter_f'])}, backgroundColor: '#c084fc' }}")
    lines.append("    ]},")
    lines.append(
        "    options: { responsive: true, plugins: { legend: { position: 'top' } }, "
        "scales: { y: { beginAtZero: true, max: 60, ticks: { callback: v => v + '%' } } } }"
    )
    lines.append("  });")


def _append_ablation_chart(lines, canvas_id, bundle):
    abl = bundle["ablation"]
    lines.append(f"  new Chart(document.getElementById('{canvas_id}'), {{")
    lines.append("    type: 'bar',")
    lines.append(f"    data: {{ labels: bgLabels, datasets: [")
    lines.append(f"      {{ label: 'Low €12k', data: {json.dumps(abl['low'])}, backgroundColor: '#dc2626' }},")
    lines.append(f"      {{ label: 'Medium €28k', data: {json.dumps(abl['medium'])}, backgroundColor: '#d97706' }},")
    lines.append(f"      {{ label: 'High €60k', data: {json.dumps(abl['high'])}, backgroundColor: '#059669' }}")
    lines.append("    ]},")
    lines.append(
        "    options: { responsive: true, plugins: { legend: { position: 'top' } }, "
        "scales: { y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } } } }"
    )
    lines.append("  });")


def mitigation_section_html(suffix_key, mit, model_label):
    b, f, c = mit["baseline"], mit["fairness"], mit["cot"]
    complete = all(mit[k]["n"] >= 500 for k in mit)
    status = "Complete (500/condition)" if complete else f"In progress ({b['n']}/{f['n']}/{c['n']} rows)"
    return f"""
<h3>RQ4 — {model_label} ({status})</h3>
<div class="grid-3">
  <div class="metric"><div class="value">{b['pct']}%</div><div class="label">Baseline</div><div class="sub">{b['yes']}/{b['n']} Yes</div></div>
  <div class="metric warn"><div class="value">{f['pct']}%</div><div class="label">Explicit Fairness</div><div class="sub">{f['yes']}/{f['n']} Yes</div></div>
  <div class="metric bad"><div class="value">{c['pct']}%</div><div class="label">Chain-of-Thought</div><div class="sub">{c['yes']}/{c['n']} Yes</div></div>
</div>
<div class="chart-box" style="margin-top:16px;">
  <h4>Mitigation conditions — {model_label}</h4>
  <canvas id="chartMitigation{suffix_key}"></canvas>
</div>
<div class="chart-box" style="margin-top:16px;">
  <h4>Yes rate by apartment — {model_label}</h4>
  <canvas id="chartMitByApt{suffix_key}"></canvas>
</div>
"""


def charts_js(bundles, mitigations):
    lines = [
        "(function () {",
        "  const chartDefaults = {",
        "    responsive: true, maintainAspectRatio: true,",
        "    plugins: { legend: { display: false } },",
        "    scales: { y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } } }",
        "  };",
        "  const bar = (id, labels, data, colors) => new Chart(document.getElementById(id), {",
        "    type: 'bar',",
        "    data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 4 }] },",
        "    options: { ...chartDefaults, plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ctx.parsed.y + '% fit rate' } } } }",
        "  });",
        f"  const bgLabels = {json.dumps(BG_CHART_LABELS)};",
    ]
    colors_inc = ["#dc2626", "#d97706", "#059669"]
    colors_bg = ["#2563eb", "#2563eb", "#2563eb", "#059669", "#2563eb"]
    colors_gen = ["#7c3aed", "#7c3aed"]
    colors_apt = ["#0891b2", "#dc2626", "#0891b2", "#0891b2", "#0891b2"]

    for key, b in bundles.items():
        cap = key.capitalize()
        lines.append(f"  bar('chartIncome{cap}', ['Low €12k', 'Medium €28k', 'High €60k'], {json.dumps(b['income_pcts'])}, {json.dumps(colors_inc)});")
        lines.append(f"  bar('chartBackground{cap}', {json.dumps(BG_CHART_LABELS)}, {json.dumps(b['bg_pcts'])}, {json.dumps(colors_bg)});")
        lines.append(f"  bar('chartGender{cap}', ['Male', 'Female'], {json.dumps(b['gender_pcts'])}, {json.dumps(colors_gen)});")
        lines.append(f"  bar('chartApartment{cap}', {json.dumps(b['apt_labels'])}, {json.dumps(b['apt_pcts'])}, {json.dumps(colors_apt)});")
        _append_intersection_chart(lines, f"chartIntersection{cap}", b)
        _append_ablation_chart(lines, f"chartAblation{cap}", b)
        _append_intersection_chart(lines, f"chartIntersectionRq3{cap}", b)
        _append_ablation_chart(lines, f"chartAblationRq3{cap}", b)

    for key, mit in mitigations.items():
        cap = key.capitalize()
        b, f, c = mit["baseline"], mit["fairness"], mit["cot"]
        lines.append(f"  bar('chartMitigation{cap}', ['Baseline', 'Explicit Fairness', 'Chain-of-Thought'], {[b['pct'], f['pct'], c['pct']]}, ['#2563eb', '#d97706', '#dc2626']);")
        apt_labels = [f"{aid} €{MODELS[key] and ''}" for aid in APT_ORDER]
        # rebuild apt labels with rents from bundle
        apt_labels = bundles[key]["apt_labels"]
        b_apt = [b["by_apt"].get(aid, 0) for aid in APT_ORDER]
        f_apt = [f["by_apt"].get(aid, 0) for aid in APT_ORDER]
        c_apt = [c["by_apt"].get(aid, 0) for aid in APT_ORDER]
        lines.append(f"  new Chart(document.getElementById('chartMitByApt{cap}'), {{")
        lines.append("    type: 'bar',")
        lines.append(f"    data: {{ labels: {json.dumps(apt_labels)}, datasets: [")
        lines.append(f"      {{ label: 'Baseline', data: {json.dumps(b_apt)}, backgroundColor: '#2563eb' }},")
        lines.append(f"      {{ label: 'Fairness', data: {json.dumps(f_apt)}, backgroundColor: '#d97706' }},")
        lines.append(f"      {{ label: 'CoT', data: {json.dumps(c_apt)}, backgroundColor: '#dc2626' }}")
        lines.append("    ]},")
        lines.append("    options: { responsive: true, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true, max: 55, ticks: { callback: v => v + '%' } } } }")
        lines.append("  });")

    lines.append("})();")
    return "\n".join(lines)


def main():
    listings = load_json(PROJECT_ROOT / "data" / "turin_listings.json")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    bundles = {}
    mitigations = {}
    for key, cfg in MODELS.items():
        path = PROJECT_ROOT / "results" / cfg["results"]
        if path.exists():
            bundles[key] = build_bundle(path, listings)
            bundles[key]["model"] = cfg["label"]
        mitigations[key] = build_mitigation(cfg["mit_suffix"])

    all_data = {
        "last_updated": today,
        "models": {
            k: {"label": MODELS[k]["label"], **{kk: vv for kk, vv in bundles[k].items() if kk != "ablation"}, "ablation": bundles[k]["ablation"]}
            for k in bundles
        },
        "mitigation": mitigations,
    }
    OUTPUT_JSON.write_text(json.dumps(all_data, indent=2, ensure_ascii=False), encoding="utf-8")

    html = INDEX_HTML.read_text(encoding="utf-8")

    owl_n = bundles.get("owl", {}).get("n", 0)
    qwen_n = bundles.get("qwen", {}).get("n", 0)
    html = html.replace(
        "<title>Tenant Bias Audit",
        f"<title>Tenant Bias Audit — owl-alpha ({owl_n}) + qwen3.5-9b ({qwen_n})",
        1,
    )
    # Fix title properly
    import re
    html = re.sub(r"<title>.*?</title>", f"<title>Tenant Bias Audit — owl-alpha + qwen3.5-9b</title>", html, count=1)

    badges = f"""<span class="badge">UPDATED {today}</span>
    <span class="badge">owl-alpha: {owl_n}/{TARGET_N}</span>
    <span class="badge">qwen3.5-9b: {qwen_n}/{TARGET_N}</span>
    <span class="badge">Dual-model dashboard</span>"""
    html = re.sub(
        r'<span class="badge">UPDATED .*?</span>\s*<span class="badge">(?:Main audit:|owl-alpha:).*?</span>\s*<span class="badge">(?:RQ4 mitigation:|qwen3\.5-9b:).*?</span>\s*(?:<span class="badge">5 apartments.*?</span>\s*)?<span class="badge">.*?</span>',
        badges,
        html,
        count=1,
        flags=re.DOTALL,
    )

    dual_block = '<h2 id="headline">Headline Findings — Model Comparison</h2>\n'
    if "owl" in bundles:
        dual_block += headline_html("owl", bundles["owl"], MODELS["owl"]["label"])
        dual_block += chart_grid_html("Owl", MODELS["owl"]["label"], bundles["owl"]["n"], MODELS["owl"]["label"])
    if "qwen" in bundles:
        dual_block += headline_html("qwen", bundles["qwen"], MODELS["qwen"]["label"])
        dual_block += chart_grid_html("Qwen", MODELS["qwen"]["label"], bundles["qwen"]["n"], MODELS["qwen"]["label"])

    html = re.sub(
        r'<h2 id="headline">Headline Findings.*?</h2>.*?<h2 id="stats">Statistical Tests',
        dual_block + '\n<h2 id="stats">Statistical Tests',
        html,
        count=1,
        flags=re.DOTALL,
    )

    if bundles:
        html = re.sub(
            r'<div class="chart-box" style="margin-top:16px;">\s*'
            r'<h4>Heatmap: background × gender \(fit rate\)</h4>\s*'
            r'<canvas id="chartIntersection"></canvas>\s*</div>',
            rq3_detail_charts_html(bundles, "intersection"),
            html,
            count=1,
            flags=re.DOTALL,
        )
        html = re.sub(
            r'<div class="chart-box" style="margin-top:16px;">\s*'
            r'<h4>Background fit rate by income stratum \(ablation\)</h4>\s*'
            r'<canvas id="chartAblation"></canvas>\s*</div>',
            rq3_detail_charts_html(bundles, "ablation"),
            html,
            count=1,
            flags=re.DOTALL,
        )

    rq4_dual = '<h2 id="rq4">RQ4: Mitigation Strategies (per model)</h2>\n<div class="card">\n'
    rq4_dual += mitigation_section_html("Owl", mitigations["owl"], MODELS["owl"]["label"])
    rq4_dual += mitigation_section_html("Qwen", mitigations["qwen"], MODELS["qwen"]["label"])
    rq4_dual += "</div>"

    html = re.sub(
        r'<h2 id="rq4">RQ4: Mitigation Strategies.*?(?=<h2 id="rq3">)',
        rq4_dual + "\n",
        html,
        count=1,
        flags=re.DOTALL,
    )

    script = charts_js(bundles, mitigations)
    script_start = html.find("<script>")
    script_end = html.rfind("</script>")
    if script_start >= 0 and script_end > script_start:
        html = html[:script_start] + f"<script>\n{script}\n</script>" + html[script_end + len("</script>") :]

    html = re.sub(
        r"Generated .*?<br>",
        f"Generated {today} | owl-alpha {owl_n}/{TARGET_N} + qwen3.5-9b {qwen_n}/{TARGET_N} | Both models preserved on this dashboard<br>",
        html,
        count=1,
    )

    INDEX_HTML.write_text(html, encoding="utf-8")
    print(f"[OK] Wrote {OUTPUT_JSON}")
    print(f"[OK] Updated {INDEX_HTML} (dual-model: owl + qwen)")
    for k, b in bundles.items():
        print(f"  {MODELS[k]['label']}: n={b['n']} Yes={b['fits'].get('Yes')} No={b['fits'].get('No')}")


if __name__ == "__main__":
    main()