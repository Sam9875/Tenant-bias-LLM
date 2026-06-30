/**
 * Generate course presentation (.pptx) and report (.docx).
 * Run: node scripts/build_deliverables.js
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  HeadingLevel,
  AlignmentType,
  BorderStyle,
  WidthType,
  ShadingType,
  LevelFormat,
  PageBreak,
  ImageRun,
} = require("docx");

const OUT = path.join(__dirname, "..", "deliverables");
const FIGURES_DIR = path.join(__dirname, "..", "results", "figures_sft");
const REPO = "https://github.com/Sam9875/Tenant-bias-LLM";

const DASHBOARD_CHART_ORDER = [
  "dashboard_income",
  "dashboard_background",
  "dashboard_gender",
  "dashboard_apartment",
  "dashboard_intersection",
  "dashboard_ablation",
  "dashboard_mitigation",
  "dashboard_mit_by_apt",
];
const MODEL_SLUGS = ["owl", "qwen"];
const EXTRA_FIGURES = [
  "heatmap_bg_x_gender_full.png",
  "heatmap_bg_x_gender_medium.png",
  "ablation_background_by_income.png",
];

const CHART_TITLES = {
  dashboard_income: "Fit rate by income",
  dashboard_background: "Fit rate by national background",
  dashboard_gender: "Fit rate by gender",
  dashboard_apartment: "Fit rate by apartment",
  dashboard_intersection: "Gender × national background",
  dashboard_ablation: "Income ablation (background within income)",
  dashboard_mitigation: "RQ4 mitigation conditions",
  dashboard_mit_by_apt: "RQ4 Yes rate by apartment",
};

function modelLabel(slug) {
  return slug === "owl" ? "openrouter/owl-alpha" : "qwen3.5-9b";
}

function figureTitle(file) {
  if (file.startsWith("dashboard_")) {
    const base = file.replace(".png", "");
    const slug = MODEL_SLUGS.find((s) => base.endsWith(`_${s}`));
    const chart = slug ? base.slice(0, -(slug.length + 1)) : base;
    const chartName = CHART_TITLES[chart] || chart.replace("dashboard_", "");
    return slug ? `${chartName} — ${modelLabel(slug)}` : chartName;
  }
  if (file.includes("heatmap_bg_x_gender_full")) return "RQ3 heatmap — gender × background (full sample)";
  if (file.includes("heatmap_bg_x_gender_medium")) return "RQ3 heatmap — medium income only";
  if (file.includes("ablation_background_by_income")) return "Income ablation bar chart (qwen3.5-9b)";
  return file.replace(".png", "").replace(/_/g, " ");
}

const C = {
  primary: "065A82",
  secondary: "1C7293",
  accent: "02C39A",
  dark: "21295C",
  light: "F0F7FA",
  white: "FFFFFF",
  muted: "64748B",
  warn: "D97706",
  bad: "DC2626",
};

fs.mkdirSync(OUT, { recursive: true });

function slideTitle(slide, pres, title, subtitle) {
  slide.background = { color: C.dark };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 5.0,
    w: 10,
    h: 0.08,
    fill: { color: C.accent },
  });
  slide.addText(title, {
    x: 0.6,
    y: 1.6,
    w: 8.8,
    h: 1.2,
    fontSize: 32,
    bold: true,
    color: C.white,
    fontFace: "Segoe UI",
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 0.6,
      y: 2.9,
      w: 8.8,
      h: 0.8,
      fontSize: 16,
      color: "CADCFC",
      fontFace: "Segoe UI",
    });
  }
}

function slideContent(pres, title, bullets, note) {
  const slide = pres.addSlide();
  slide.background = { color: C.light };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 0.12,
    h: 5.625,
    fill: { color: C.primary },
  });
  slide.addText(title, {
    x: 0.55,
    y: 0.35,
    w: 9,
    h: 0.6,
    fontSize: 24,
    bold: true,
    color: C.dark,
    fontFace: "Segoe UI",
    margin: 0,
  });
  const items = bullets.map((t, i) => ({
    text: t,
    options: {
      bullet: true,
      breakLine: i < bullets.length - 1,
      fontSize: 14,
      color: C.dark,
      fontFace: "Segoe UI",
    },
  }));
  slide.addText(items, { x: 0.55, y: 1.1, w: 8.8, h: 3.8, valign: "top" });
  if (note) {
    slide.addText(note, {
      x: 0.55,
      y: 5.0,
      w: 8.8,
      h: 0.4,
      fontSize: 10,
      italic: true,
      color: C.muted,
      fontFace: "Segoe UI",
    });
  }
  return slide;
}

function slideTable(pres, title, headers, rows) {
  const slide = pres.addSlide();
  slide.background = { color: C.light };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 0.12,
    h: 5.625,
    fill: { color: C.primary },
  });
  slide.addText(title, {
    x: 0.55,
    y: 0.35,
    w: 9,
    h: 0.6,
    fontSize: 22,
    bold: true,
    color: C.dark,
    fontFace: "Segoe UI",
    margin: 0,
  });
  const data = [
    headers.map((h) => ({
      text: h,
      options: {
        bold: true,
        color: C.white,
        fill: { color: C.primary },
        fontSize: 11,
        fontFace: "Segoe UI",
      },
    })),
    ...rows.map((row) =>
      row.map((cell) => ({
        text: String(cell),
        options: {
          fontSize: 11,
          color: C.dark,
          fontFace: "Segoe UI",
        },
      }))
    ),
  ];
  slide.addTable(data, {
    x: 0.55,
    y: 1.05,
    w: 8.9,
    colW: Array(headers.length).fill(8.9 / headers.length),
    border: { pt: 0.5, color: "CBD5E1" },
    fontFace: "Segoe UI",
  });
  return slide;
}

function listFigures() {
  if (!fs.existsSync(FIGURES_DIR)) return [];
  const onDisk = new Set(fs.readdirSync(FIGURES_DIR).filter((f) => f.endsWith(".png")));
  const ordered = [];
  for (const slug of MODEL_SLUGS) {
    for (const chart of DASHBOARD_CHART_ORDER) {
      const file = `${chart}_${slug}.png`;
      if (onDisk.has(file)) ordered.push(file);
    }
  }
  for (const file of EXTRA_FIGURES) {
    if (onDisk.has(file) && !ordered.includes(file)) ordered.push(file);
  }
  for (const file of [...onDisk].sort()) {
    if (!ordered.includes(file)) ordered.push(file);
  }
  return ordered.map((file, i) => ({
    file,
    path: path.join(FIGURES_DIR, file),
    slideTitle: `Figure ${i + 1} — ${figureTitle(file)}`,
    caption: `Source: results/figures_sft/${file}`,
  }));
}

function slideImage(pres, title, imgPath, caption) {
  const slide = pres.addSlide();
  slide.background = { color: C.light };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 0.12,
    h: 5.625,
    fill: { color: C.primary },
  });
  slide.addText(title, {
    x: 0.55,
    y: 0.3,
    w: 9,
    h: 0.55,
    fontSize: 18,
    bold: true,
    color: C.dark,
    fontFace: "Segoe UI",
    margin: 0,
  });
  slide.addImage({
    path: imgPath,
    x: 0.55,
    y: 0.95,
    w: 8.9,
    h: 4.0,
    sizing: { type: "contain", w: 8.9, h: 4.0 },
  });
  if (caption) {
    slide.addText(caption, {
      x: 0.55,
      y: 5.05,
      w: 8.9,
      h: 0.45,
      fontSize: 9,
      italic: true,
      color: C.muted,
      fontFace: "Segoe UI",
    });
  }
  return slide;
}

function docFigure(fig, docWidth = 580) {
  const data = fs.readFileSync(fig.path);
  const dims = sizeOfPng(data);
  const height = dims ? Math.round(docWidth * (dims.height / dims.width)) : 400;
  return [
    docPara(fig.slideTitle.replace(/^Figure \d+ — /, ""), { bold: true, after: 120 }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 120 },
      children: [
        new ImageRun({
          type: "png",
          data,
          transformation: { width: docWidth, height },
          altText: {
            title: fig.file,
            description: fig.caption,
            name: fig.file,
          },
        }),
      ],
    }),
    docPara(fig.caption, { italic: true, size: 20, after: 240 }),
  ];
}

function sizeOfPng(buf) {
  if (buf.length < 24 || buf.readUInt32BE(0) !== 0x89504e47) return null;
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

async function buildPresentation() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "samesun";
  pres.title = "LLM Tenant Bias Audit — Turin";

  const s1 = pres.addSlide();
  slideTitle(
    s1,
    pres,
    "Investigating LLM Bias in\nTurin Tenant Screening",
    "Course project · 7,800 API evaluations · June 2026"
  );
  s1.addText("Models: openrouter/owl-alpha  ·  qwen3.5-9b", {
    x: 0.6,
    y: 4.0,
    w: 8.8,
    fontSize: 13,
    color: "A8C5E8",
    fontFace: "Segoe UI",
  });

  slideContent(pres, "Why this matters", [
    "LLMs are increasingly used to screen rental applicants.",
    "If models reject applicants based on gender or national origin — beyond income and employment — that raises fair-housing concerns.",
    "We audit two open models on synthetic Turin listings with controlled applicant profiles.",
    "Goal: measure demographic effects and test simple prompt mitigations.",
  ]);

  slideContent(pres, "Research questions", [
    "RQ1 — Gender: Does gender affect fit decisions?",
    "RQ2 — National background: Does origin/status affect decisions?",
    "RQ3 — Intersectional: Do gender effects differ by background?",
    "RQ4 — Mitigation: Do fairness or chain-of-thought prompts change outcomes?",
  ]);

  slideContent(pres, "Experimental design", [
    "5 real Turin rental listings (€500–€1,750/month).",
    "480 synthetic applicants: 24 sets (income × employment × family) × 20 profiles each.",
    "Main audit: 5 × 480 = 2,400 single-call evaluations per model.",
    "RQ4: 500 pairs × 3 prompt conditions (baseline, explicit fairness, CoT) per model.",
    "Total: 7,800 API calls · ~8 h (owl-alpha) · ~9 h (qwen3.5-9b).",
  ]);

  slideTable(
    pres,
    "Models & providers",
    ["Model", "Provider", "Main calls", "RQ4 calls"],
    [
      ["openrouter/owl-alpha", "OpenRouter", "2,400", "1,500"],
      ["qwen3.5-9b", "Regolo", "2,400", "1,500"],
    ]
  );

  slideTable(
    pres,
    "Headline results — income dominates (both models)",
    ["Income", "owl-alpha Yes%", "qwen3.5-9b Yes%"],
    [
      ["Low (€12k/yr)", "1.5%", "1.1%"],
      ["Medium (€28k/yr)", "40.5%", "33.0%"],
      ["High (€60k/yr)", "66.5%", "54.9%"],
    ]
  );

  slideTable(
    pres,
    "RQ2 — National background (significant)",
    ["Background", "owl-alpha", "qwen3.5-9b"],
    [
      ["Local citizen", "31.7%", "24.8%"],
      ["EU foreigner", "32.1%", "26.2%"],
      ["Non-EU (permit)", "32.9%", "28.8%"],
      ["Second generation", "32.5%", "27.3%"],
      ["Refugee", "51.7%", "41.2%"],
    ],
  );
  slideContent(
    pres,
    "RQ2 takeaway",
    [
      "Refugees receive substantially higher Yes rates than other groups (~15–20 pp gap).",
      "χ² significant for national background on both models (Cramer's V ≈ 0.13–0.16).",
      "Gap persists within income strata (income ablation).",
    ],
    "Motivations often cite refugee/protection status explicitly."
  );

  slideTable(
    pres,
    "RQ1 — Gender (model-dependent)",
    ["Metric", "owl-alpha", "qwen3.5-9b"],
    [
      ["Male Yes%", "34.1%", "28.8%"],
      ["Female Yes%", "38.2%", "30.6%"],
      ["p-value", "0.037 (significant)", "0.348 (not significant)"],
    ]
  );

  slideContent(pres, "RQ3 — Intersectional effects", [
    "Gender gaps are small within each national-background group.",
    "Cochran's Q test: no significant heterogeneity across backgrounds (p ≈ 0.95).",
    "Refugee elevation appears for both male and female applicants.",
    "Conclusion: background effect is not driven by gender × background interaction.",
  ]);

  const figures = listFigures();
  if (figures.length) {
    slideContent(pres, "Results figures", [
      `${figures.length} charts exported to results/figures_sft/ (same data as docs/index.html).`,
      "Per model: income, background, gender, apartment, intersection, ablation, RQ4 mitigation.",
      "See following slides for each figure.",
    ]);
    figures.forEach((fig) => slideImage(pres, fig.slideTitle, fig.path, fig.caption));
  }

  slideTable(
    pres,
    "RQ4 — Mitigation (500 pairs × 3 conditions)",
    ["Condition", "owl-alpha", "qwen3.5-9b"],
    [
      ["Baseline", "37.6% Yes", "32.0% Yes"],
      ["Explicit fairness", "37.4% Yes", "39.0% Yes"],
      ["Chain-of-thought", "25.0% Yes", "32.4% Yes"],
    ]
  );
  slideContent(
    pres,
    "RQ4 takeaway",
    [
      "Explicit fairness prompt barely shifts owl-alpha; raises Yes rate slightly on Qwen.",
      "Chain-of-thought makes owl-alpha much stricter (−12.6 pp); neutral on Qwen.",
      "Nationality gaps largely unchanged — simple prompts are insufficient mitigation.",
    ]
  );

  slideContent(pres, "Limitations", [
    "Synthetic profiles — not real tenant histories or documents.",
    "Turin-only listings; five apartments may not generalize.",
    "Single-turn JSON prompts; production systems may differ.",
    "Refugee effect may reflect model reasoning about legal status, not pure animus.",
  ]);

  const sEnd = pres.addSlide();
  slideTitle(sEnd, pres, "Conclusions", null);
  sEnd.addText(
    [
      {
        text: "Income is the strongest predictor of fit on both models.",
        options: { bullet: true, breakLine: true, fontSize: 15, color: "E8F4FC" },
      },
      {
        text: "Refugee applicants are accepted more often — a significant background effect.",
        options: { bullet: true, breakLine: true, fontSize: 15, color: "E8F4FC" },
      },
      {
        text: "Gender bias appears on owl-alpha only; Qwen shows no significant gender gap.",
        options: { bullet: true, breakLine: true, fontSize: 15, color: "E8F4FC" },
      },
      {
        text: "Tested mitigations do not remove nationality disparities.",
        options: { bullet: true, fontSize: 15, color: "E8F4FC" },
      },
    ],
    { x: 0.6, y: 2.0, w: 8.5, h: 2.5, fontFace: "Segoe UI" }
  );
  sEnd.addText(`Code & dashboard: ${REPO}`, {
    x: 0.6,
    y: 4.7,
    w: 8.8,
    fontSize: 12,
    color: C.accent,
    fontFace: "Segoe UI",
  });

  const out = path.join(OUT, "Tenant_Bias_Presentation.pptx");
  await pres.writeFile({ fileName: out });
  return out;
}

function docPara(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 160 },
    children: [new TextRun({ text, size: opts.size ?? 22, bold: opts.bold, italics: opts.italic })],
  });
}

function docHeading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({ heading: level, children: [new TextRun(text)] });
}

function docBullet(ref, text) {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    children: [new TextRun({ text, size: 22 })],
  });
}

function docTable(headers, rows) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const colW = Math.floor(9360 / headers.length);
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: headers.map(() => colW),
    rows: [
      new TableRow({
        children: headers.map(
          (h) =>
            new TableCell({
              borders,
              width: { size: colW, type: WidthType.DXA },
              shading: { fill: "D5E8F0", type: ShadingType.CLEAR },
              children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, size: 20 })] })],
            })
        ),
      }),
      ...rows.map(
        (row) =>
          new TableRow({
            children: row.map(
              (cell) =>
                new TableCell({
                  borders,
                  width: { size: colW, type: WidthType.DXA },
                  children: [new Paragraph({ children: [new TextRun({ text: String(cell), size: 20 })] })],
                })
            ),
          })
      ),
    ],
  });
}

async function buildReport() {
  const figures = listFigures();
  const figureBlocks = figures.flatMap((fig, i) => [
    ...(i === 0 ? [] : [new Paragraph({ children: [new PageBreak()] })]),
    ...docFigure({ ...fig, slideTitle: `Figure ${i + 1} — ${fig.slideTitle.replace(/^Figure \d+ — /, "")}` }),
  ]);

  const doc = new Document({
    styles: {
      default: { document: { run: { font: "Arial", size: 22 } } },
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { size: 32, bold: true, font: "Arial" },
          paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0 },
        },
        {
          id: "Heading2",
          name: "Heading 2",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { size: 28, bold: true, font: "Arial" },
          paragraph: { spacing: { before: 200, after: 160 }, outlineLevel: 1 },
        },
      ],
    },
    numbering: {
      config: [
        {
          reference: "bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "•",
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 720, hanging: 360 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 11906, height: 16838 },
            margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
          },
        },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 200 },
            children: [
              new TextRun({
                text: "Investigating Discrimination by LLMs\nin Turin Rental Apartment Assignment",
                bold: true,
                size: 36,
              }),
            ],
          }),
          docPara("Course project report · Politecnico di Torino · June 2026", { italic: true, after: 400 }),
          docPara(
            "Author: samesun · Repository: github.com/Sam9875/Tenant-bias-LLM",
            { after: 400 }
          ),

          docHeading("Abstract"),
          docPara(
            "Large language models are increasingly deployed in housing workflows. This study audits whether two models — openrouter/owl-alpha and qwen3.5-9b — discriminate against synthetic rental applicants in Turin based on gender or national background, while varying legitimate factors (income, employment, marital status, children). We run 7,800 single-call API evaluations: a 2,400-pair main factorial per model and 1,500 RQ4 mitigation calls per model (baseline, explicit fairness, chain-of-thought). Income is the dominant predictor of fit (Cramer's V ≈ 0.48–0.56). National background shows a significant effect: refugee applicants receive 15–20 percentage points more Yes decisions than other groups. Gender bias is significant on owl-alpha (p = 0.037) but not on qwen3.5-9b (p = 0.348). Intersectional analysis finds no heterogeneous gender effect across backgrounds. Simple prompt mitigations do not remove nationality disparities."
          ),

          docHeading("1. Introduction"),
          docPara(
            "Automated tenant screening can scale landlord decisions but also risks encoding demographic bias. Italian and EU fair-housing principles require that rental decisions be based on legitimate criteria — typically financial solvency, household fit, and rental history — rather than gender, ethnicity, or immigration status."
          ),
          docPara(
            "We simulate a landlord-assistant scenario: given a Turin listing and a structured applicant profile, the model must return a binary fit decision (Yes/No) and a short motivation. By holding income and family structure constant across profile sets while varying gender and national background, we isolate demographic effects."
          ),

          docHeading("2. Methodology"),
          docHeading("2.1 Dataset", HeadingLevel.HEADING_2),
          docBullet("bullets", "5 real Turin listings from immobiliare.it (rent €500–€1,750/month)."),
          docBullet("bullets", "480 applicant profiles: 24 sets × 20 profiles (2 genders × 5 backgrounds × 2 replicates)."),
          docBullet("bullets", "National backgrounds: local citizen, EU foreigner, non-EU with permit, refugee, second generation."),
          docBullet("bullets", "Income levels: low €12k, medium €28k, high €60k per year."),

          docHeading("2.2 Procedure", HeadingLevel.HEADING_2),
          docBullet("bullets", "Single-call evaluations (no batching) to avoid understating discrimination."),
          docBullet("bullets", "Model must reply with JSON: {\"fit\": \"Yes\"|\"No\", \"motivation\": \"...\"}."),
          docBullet("bullets", "Main audit: all 2,400 listing–profile pairs per model."),
          docBullet("bullets", "RQ4: 500 pairs (5 profile sets × 5 apartments × 20 profiles) × 3 prompt conditions."),

          docHeading("2.3 Models", HeadingLevel.HEADING_2),
          docTable(
            ["Model", "Provider", "Calls", "Approx. runtime"],
            [
              ["openrouter/owl-alpha", "OpenRouter", "3,900", "~8 hours"],
              ["qwen3.5-9b", "Regolo", "3,900", "~9 hours"],
            ]
          ),
          docPara("", { after: 200 }),
          docPara("Analysis: chi-square tests and Cramer's V on fit rates; Cochran's Q for RQ3 heterogeneity."),

          docHeading("3. Results"),
          docHeading("3.1 Income (strongest signal)", HeadingLevel.HEADING_2),
          docTable(
            ["Income", "owl-alpha Yes%", "qwen3.5-9b Yes%"],
            [
              ["Low €12k", "1.5%", "1.1%"],
              ["Medium €28k", "40.5%", "33.0%"],
              ["High €60k", "66.5%", "54.9%"],
            ]
          ),
          docPara("", { after: 200 }),
          docPara(
            "Both models overwhelmingly use income as a screening criterion. Low-income applicants are almost always rejected regardless of demographics."
          ),

          docHeading("3.2 RQ2 — National background", HeadingLevel.HEADING_2),
          docTable(
            ["Background", "owl-alpha", "qwen3.5-9b"],
            [
              ["Local", "31.7%", "24.8%"],
              ["EU", "32.1%", "26.2%"],
              ["Non-EU", "32.9%", "28.8%"],
              ["Second gen", "32.5%", "27.3%"],
              ["Refugee", "51.7%", "41.2%"],
            ]
          ),
          docPara("", { after: 200 }),
          docPara(
            "Refugee applicants are accepted significantly more often. Effect sizes are small-to-medium (V ≈ 0.13–0.16) but statistically significant. Qualitative review shows models often cite refugee/protection status in motivations."
          ),

          docHeading("3.3 RQ1 — Gender", HeadingLevel.HEADING_2),
          docPara(
            "owl-alpha: male 34.1% vs female 38.2% Yes (p = 0.037). qwen3.5-9b: male 28.8% vs female 30.6% (p = 0.348, not significant). Gender effects are model-dependent."
          ),

          docHeading("3.4 RQ3 — Intersectional", HeadingLevel.HEADING_2),
          docPara(
            "Gender gaps within each national-background group are small. Cochran's Q = 0.70, p = 0.95 — we do not find evidence that gender bias varies across backgrounds."
          ),

          docHeading("3.5 Figures", HeadingLevel.HEADING_2),
          docPara(
            figures.length
              ? `The following ${figures.length} figures match the dashboard charts and are saved in results/figures_sft/. Regenerate with: python scripts/export_dashboard_figures.py`
              : "No figures found. Run: python scripts/export_dashboard_figures.py",
            { after: 200 }
          ),
          ...figureBlocks,

          docHeading("3.6 RQ4 — Mitigation", HeadingLevel.HEADING_2),
          docTable(
            ["Prompt", "owl-alpha", "qwen3.5-9b"],
            [
              ["Baseline", "37.6%", "32.0%"],
              ["Explicit fairness", "37.4%", "39.0%"],
              ["Chain-of-thought", "25.0%", "32.4%"],
            ]
          ),
          docPara("", { after: 200 }),
          docPara(
            "Explicit fairness instructions have minimal impact on nationality gaps. Chain-of-thought prompting makes owl-alpha substantially stricter overall but does not equalize acceptance across backgrounds."
          ),

          docHeading("4. Discussion"),
          docPara(
            "The models behave primarily as financial screeners, which is expected. However, the elevated acceptance of refugee applicants — opposite to typical discrimination patterns against minorities — suggests the models treat protection status as a positive legal signal rather than applying a uniform rule. This is still a demographic disparity that landlords should not rely on."
          ),
          docPara(
            "owl-alpha shows a modest female advantage; Qwen does not. Practitioners should not assume bias patterns transfer across models."
          ),

          docHeading("5. Limitations"),
          docBullet("bullets", "Synthetic profiles without real documents, references, or rental history."),
          docBullet("bullets", "Five Turin apartments — limited price and neighborhood diversity."),
          docBullet("bullets", "Prompt wording sensitivity; mitigation results apply only to tested formulations."),
          docBullet("bullets", "API models may change over time; results are a snapshot from June 2026."),

          docHeading("6. Conclusion"),
          docPara(
            "We completed 7,800 LLM evaluations across two models. Income dominates fit decisions. National background — especially refugee status — significantly affects outcomes on both models. Gender bias is present on owl-alpha only. Simple fairness and chain-of-thought prompts are insufficient to remove demographic disparities. Full interactive results are available in docs/index.html in the project repository."
          ),

          docHeading("References"),
          docBullet("bullets", "HUD (2024). Guidance on AI and fair housing."),
          docBullet("bullets", "SafeRent settlement — algorithmic tenant screening litigation (US)."),
          docBullet("bullets", "Project repository: github.com/Sam9875/Tenant-bias-LLM"),
        ],
      },
    ],
  });

  const out = path.join(OUT, "Tenant_Bias_Report.docx");
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(out, buf);
  return out;
}

async function main() {
  const figures = listFigures();
  console.log(`[INFO] Figures found: ${figures.length}`);
  figures.forEach((f) => console.log(`       - ${f.file}`));
  const pptx = await buildPresentation();
  const docx = await buildReport();
  console.log(`[OK] Presentation: ${pptx}`);
  console.log(`[OK] Report:       ${docx}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});