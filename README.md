# Trust-Calibrated Supplier Compliance under Evidence-Source Poisoning

> Companion code & benchmark for the paper:
> **"When Suppliers Game the Algorithm: Evidence-Source Poisoning Attacks on
> LLM-Based Supplier Risk Scoring, and a Trust-Calibrated Defense"**
>
> Aakarsh Prabhu · RV College of Engineering · Experiential Learning, VI Sem.

[![Tests](https://img.shields.io/badge/tests-25%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)]()

## TL;DR

LLM-based supplier risk scoring (Liu & Meidani 2024 and follow-ups) treats
the public information ecosystem as a trusted input. We show this is a
serious vulnerability: a debarred supplier can lift its score from grade
**F (15.2)** to grade **A (83.3)** with twenty synthetic press releases.
A trust-calibrated Dempster–Shafer fusion with burst and template-similarity
downweighting restores correct classification (**F1 1.00**) on the same
attack while keeping clean-data performance unchanged.

## Headline result

```
make eval
```

| Condition | Accuracy | F1 | Flip rate | Mean score lift |
|---|---:|---:|---:|---:|
| Clean             | 0.88 | 0.73 |  —    |   —   |
| **Attacked**      | 0.84 | **0.00** | 0.28 | +16.5 |
| **Defended**      | **1.00** | **1.00** | 0.12 | +8.0 |

(B = 10 synthetic press releases, 25 seed suppliers, mock LLM backend.)

## Architecture

```
   ┌──────────────────────────┐    ┌────────────────────────────┐
   │  Module 1 — Compliance   │    │  Module 2 — Risk sensing   │
   │  OFAC · WB · BIS         │    │  News + LLM extraction     │
   │  per-source credibility  │    │  per-article credibility   │
   └────────────┬─────────────┘    └──────────────┬─────────────┘
                │                                 │
                ▼                                 ▼
        ┌────────────────────────────────────────────────┐
        │   Trust-calibrated fusion (Dempster–Shafer)    │
        │   ⊕ corroboration · burst · template penalties │
        └────────────────────┬───────────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────┐
            │  Adversarial harness            │
            │  inject → re-score → measure    │
            │  flip / lift / ECE              │
            └─────────────────────────────────┘
```

## Quick start

```bash
git clone https://github.com/AakarshP26/Supplier-Compliance-System-.git
cd Supplier-Compliance-System-
git checkout agentic-workflow

make install      # installs pinned requirements
make test         # 25 tests pass
make eval         # reproduces the headline result table
make sweep        # writes data/results/budget_sweep.csv (Figure 2 input)
make dashboard    # launches the Streamlit demo at localhost:8501
```

The mock LLM backend is on by default (`USE_MOCK_LLM=1`), so everything
above runs offline. To use the real Anthropic API:

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY and USE_MOCK_LLM=0
```

## Agentic UI (Next.js + FastAPI)

The `agentic-workflow` branch ships a full-stack interface — a Perplexity-style
chat frontend backed by a FastAPI server and a multi-turn tool-calling agent.

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, Tailwind CSS v4, Magic UI, Recharts |
| Backend API | FastAPI + Uvicorn |
| Agent | DeepSeek via OpenRouter (or Anthropic Claude) |
| Database | PostgreSQL 16 (85 suppliers, CN suppliers excluded) |

### Setup

**1. PostgreSQL**

```bash
brew install postgresql@16
/opt/homebrew/opt/postgresql@16/bin/pg_ctl start -D /opt/homebrew/var/postgresql@16
/opt/homebrew/opt/postgresql@16/bin/createdb scs_db
```

**2. Backend**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
pip install fastapi uvicorn sqlalchemy psycopg2-binary

# Set API keys
cp backend/.env.example backend/.env
# Edit backend/.env — set OPENROUTER_API_KEY, USE_MOCK_LLM=0

# Seed the database (removes CN suppliers, loads 85 suppliers)
cd backend && python scripts/seed_db.py

# Start the API server
cd backend && uvicorn main:app --reload --port 8000
```

**3. Frontend**

```bash
cd frontend && npm install && npm run dev
# Open http://localhost:3000
```

### Agent capabilities

The copilot agent runs a multi-turn tool-calling loop (up to 6 rounds) with
these tools:

| Tool | What it does |
|------|-------------|
| `portfolio_summary()` | Aggregate risk stats with DS belief breakdown |
| `list_risky_suppliers(threshold, limit)` | Suppliers below a score threshold, worst-first |
| `rank_suppliers(by, ascending, limit)` | Sort by score, compliance fails, or article count |
| `analyze_supplier_summary(name, news?)` | Full DS-fusion analysis with belief masses + citations |
| `onboard_supplier(name, country, category, ...)` | Assess a new supplier not yet in the directory |
| `find_cheapest_attack(supplier_id, ...)` | Red-team adversarial vulnerability test |

Responses stream token-by-token via SSE. Every data point carries an inline
`[Source: DS-Fusion pipeline]` citation. DS belief masses (`m_safe`,
`m_risky`, `uncertainty`) are surfaced in every analysis.

### Database

PostgreSQL `scs_db` schema:

| Table | Rows | Contents |
|-------|------|----------|
| `suppliers` | 85 | Supplier records (CN-based suppliers excluded) |
| `news_articles` | 30 | Seed news corpus |
| `reference_lists` | 39 | OFAC SDN, BIS CRS, World Bank debarred entries |

`scs/data.py` reads from PostgreSQL with automatic fallback to the JSON flat
files if the database is unreachable.

To re-seed after data changes:

```bash
cd backend && python scripts/seed_db.py
```

## Dashboard pages

The Streamlit app exposes eight pages:

| Page | What it shows |
|---|---|
| **Overview** | Portfolio KPIs across all 87 suppliers · score histogram with grade-band shading · risk-event donut · per-category boxplot · country/grade sunburst · compliance heatmap · top-5 worst/best · sortable register |
| **Find suppliers** | Multi-criteria filter (8 dimensions) · score-band slider · risk-event match · real-vs-illustrative toggle · text search · CSV shortlist export |
| **Supplier detail** | Hero banner tinted by grade · belief decomposition donut · risk topology radar · news timeline · evidence-source credibility · compliance & signals tables · contribution waterfall · **40+ verification parameters** organised by section (Registrations, Financial, Operations, Quality, Regulatory, Reputation) |
| **Parameters used** | Full taxonomy of 35 scoring inputs · group filter · per-parameter coverage and value distribution · per-supplier contribution bar chart with green/red net-push coloring · CSV export of taxonomy |
| **Compare** | 2–5 suppliers side-by-side · radar overlay · parallel coordinates across 7 dimensions · metric matrix |
| **Onboard new supplier** | Form to add a new supplier · paste news bodies · runs the full pipeline live · session-only persistence |
| **Adversarial lab** | Score-vs-budget curve · attack lift heatmap · portfolio-wide F1 deltas · per-supplier flip table |
| **Methodology** | Threat model · credibility pyramid · DS + Yager equations · defense maths · honest limitations · data disclosure |

## What the analyser looks at

The scoring layer fuses three streams of evidence using Dempster–Shafer:

**Compliance.** OFAC SDN, World Bank Debarred Firms, and BIS CRS
registration check, each weighted by source credibility.

**News intelligence.** LLM-extracted risk signals from a per-supplier
news corpus, with fields for event type (recall, sanction, fraud,
labor, cyber, ESG, financial distress, leadership change, litigation,
positive), severity, sentiment, source credibility, and corroboration
across distinct outlets.

**40+ verification parameters** ([taxonomy](src/scs/metrics_taxonomy.py),
[scoring rules](src/scs/scoring/parameters.py)) — the SME-scale
verification layer:

| Group | Parameters |
|---|---|
| **Identity & scale** | Years in operation, employee count, annual revenue, plant area, monthly capacity |
| **Financial health** | Current ratio, debt-to-equity, days payable outstanding, GST compliance score, net worth, annual turnover, Udyam category |
| **Operational** | On-time delivery %, defect rate (ppm), capacity utilisation %, lead time variability |
| **Quality certifications** | ISO 9001, ISO 14001, IATF 16949, AS9100, ISO 13485, IPC-A-610, BIS CRS active |
| **Regulatory** | MCA active, KSPCB pollution NOC, fire NOC, Factories Act licence, EPF dues clear, ITR filed, EPFO/ESIC registered, Shop & Estab. licence |
| **Reputation** | Domain age, online review score, customer references, labour disputes (3 yr), media coverage breadth |

Each known value generates a basic-probability assignment that folds
into the fusion. Unknown values contribute mass to Θ (uncertainty),
which is exactly the behaviour you want for cold-start verification of
small suppliers with limited public footprint.

## Supplier directory composition

The seeded directory holds **85 suppliers** focused on
**India / Bangalore** (2 CN-based suppliers removed from the live database):

- **41 real listed Indian firms** — PLI awardees (Dixon, Lava, Optiemus,
  Foxconn India, Wistron India, Pegatron India, Bhagwati, Amber, Syrma
  SGS, Kaynes, Cyient DLM, Avalon, Epack, VVDN, Centum, Bharat FIH,
  MosChip, Tata Electronics, Vedanta-Foxconn JV); PSUs (BEL, ITI, Tejas,
  HFCL, Sterlite); listed EMS / semi design / automotive (Tata Elxsi,
  Bosch India, Honeywell India, Continental India, Salcomp, Jabil
  India, Flex India).
- **7 real Bangalore-specific firms** — Saankhya Labs, Signalchip,
  Wipro 3D, Zetwerk, Tessolve, Tata Elxsi Whitefield, Capgemini
  Engineering.
- **35 illustrative SME-scale entities** marked with `is_illustrative=True`
  and a descriptive `note`. Composites of typical small Bangalore
  electronics suppliers (Peenya, Whitefield, Electronic City,
  Bommanahalli, Yelahanka, Rajajinagar industrial zones) — included to
  demonstrate score variation at SME scale without misrepresenting any
  real firm. They appear with a ⓘ marker throughout the dashboard and
  can be filtered out on the **Find suppliers** page.
- **2 deliberately-risky foreign entities** (Apex Global Sourcing BVI,
  Dnipro Microelectronics) — kept to demo OFAC / World Bank compliance-list
  catches. Shenzhen Shadow and Guangdong Relabel (CN) have been removed from
  the live database.

## Repository layout

```
src/scs/
  models.py          Provenance-aware domain models
  credibility.py     Source credibility registry (gov / tier-1 / press-release / anon)
  data.py            Seed supplier loader + fuzzy lookup
  service.py         High-level assess() entrypoint

  compliance/        Module 1 - structured compliance checks
    ofac.py          OFAC SDN sanctions screening
    world_bank.py    World Bank debarred firms
    bis_crs.py       BIS Compulsory Registration Scheme (India)
    pipeline.py      Parallel orchestrator -> ComplianceReport

  risk/              Module 2 - LLM risk sensing
    news.py          News corpus model + loader
    prompts.py       Externalised prompts (verbatim in paper appendix)
    extractor.py     LLM extractor with Anthropic + mock backends
    pipeline.py      Cross-source corroboration -> RiskProfile

  scoring/           Trust-calibrated fusion
    fusion.py        Dempster-Shafer with Yager conflict-to-uncertainty
    defense.py       Burst + template-similarity downweighting

  adversarial/       Threat model + attack harness
    attack.py        Evidence-source poisoning (press_release, anon_blog,
                     self_published vectors)
    runner.py        Run pipeline under attack

  evaluation/        Reproducible experiments
    metrics.py       F1, flip rate, score lift, ECE
    ground_truth.py  Risky/safe labels for the seed set
    run_experiment.py    Headline result table
    run_budget_sweep.py  CSV for the paper's main figure

  dashboard/
    app.py           Streamlit demo (single supplier / compare / adversarial)

data/
  seed_suppliers.json
  ground_truth.json
  reference/
    ofac_sdn_sample.json
    wb_debarred_sample.json
    bis_crs_sample.json
  news/
    seed_corpus.json
  results/             generated by make eval / make sweep
```

## Citing this work

```bibtex
@misc{prabhu2026trustcal,
  author = {Prabhu, Aakarsh},
  title  = {When Suppliers Game the Algorithm: Evidence-Source Poisoning Attacks
            on LLM-Based Supplier Risk Scoring, and a Trust-Calibrated Defense},
  year   = {2026},
  url    = {https://github.com/AakarshP26/Supplier-Compliance-System-}
}
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
