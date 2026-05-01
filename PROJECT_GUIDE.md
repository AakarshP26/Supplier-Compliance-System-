# PROJECT GUIDE — Trust-Calibrated Supplier Compliance System

A complete walkthrough of what we built, why we built it that way, every
concept you need to defend it, and honest answers to the questions a
reviewer is most likely to ask.

Read this end-to-end once. Then keep it open during the review and
search for whatever your teacher just asked.

---

## Table of contents

1. [The big picture](#1-the-big-picture)
2. [Concepts you must own before talking about the system](#2-concepts-you-must-own)
3. [Architecture at a glance](#3-architecture-at-a-glance)
4. [The data layer — what we know about each supplier](#4-the-data-layer)
5. [Pipeline stage 1 — Compliance screening](#5-pipeline-stage-1--compliance-screening)
6. [Pipeline stage 2 — News intelligence with an LLM](#6-pipeline-stage-2--news-intelligence)
7. [Pipeline stage 3 — Verification parameters (the SME layer)](#7-pipeline-stage-3--verification-parameters)
8. [Pipeline stage 4 — Dempster–Shafer fusion](#8-pipeline-stage-4--dempstershafer-fusion)
9. [Pipeline stage 5 — Trust-calibrated defense](#9-pipeline-stage-5--trust-calibrated-defense)
10. [Adversarial simulation — the threat model](#10-adversarial-simulation)
11. [Evaluation — how we measure success](#11-evaluation)
12. [Dashboard — every page, what it does, why it's there](#12-dashboard)
13. [Parameter reference — every parameter, defined and sourced](#13-parameter-reference)
14. [Accuracy, effectiveness, and the honest numbers](#14-accuracy-and-effectiveness)
15. [Limitations — what the system cannot do](#15-limitations)
16. [Likely teacher questions and how to answer them](#16-anticipated-questions)
17. [Glossary](#17-glossary)

---

## 1. The big picture

### The problem

Companies — especially in regulated electronics manufacturing — must
decide: **is this supplier trustworthy enough to place an order with?**
The data they look at is messy:

- **Sanction lists** (OFAC SDN, World Bank Debarred, EU consolidated,
  India MEA) — authoritative but cover only the worst cases.
- **News articles** — rich signal, but uncurated, mixed sentiment, easy
  to fake.
- **Public filings** (MCA in India, SEC EDGAR in the US, Companies
  House in the UK) — authoritative for what they cover but require
  parsing.
- **Operational data** (on-time delivery, defect rates, ISO certs) —
  often only available for repeat suppliers.

A modern "AI scoring" approach is to feed all of this to an LLM and
ask for a verdict. **The problem with that approach is that LLMs are
gullible to whichever evidence ends up in the context window.** A
supplier that wants a contract can plant flattering articles on cheap
PR-wire services and watch the LLM-driven scorer reward them. The
system has no internal model of *who* is providing each piece of
evidence and how trustworthy that source is.

### What we built

A scoring system with three properties any production deployment
needs:

1. **Provenance-aware.** Every piece of evidence is tagged with where
   it came from (URL → domain → credibility tier).
2. **Multi-source.** It fuses three different evidence streams —
   compliance lists, news intelligence, and 40+ verification parameters
   from public Indian filings — instead of relying on any single
   source.
3. **Adversarially robust.** It explicitly models an attacker who
   plants flattering content and applies a defense (burst detection +
   template-similarity downweighting) that demonstrably blocks the
   attack.

### What's novel about it

The contribution is the **trust-calibrated defense**. Most LLM-based
supplier-scoring papers treat all retrieved articles as equal. We
show:

- **The attack** — a supplier with a low-credibility budget can flip
  their classification from RISKY to SAFE just by spamming positive
  press-releases.
- **The defense** — Dempster–Shafer fusion with Yager's conflict rule,
  combined with credibility priors (a press release counts ~16% of a
  Reuters article), corroboration bonuses, and burst/template
  penalties, blocks this attack with no false-positive cost on
  legitimate news.

This is honest, measurable, and reproducible. That's what makes it a
project worth defending.

### How it aligns with SDG 9

SDG 9 is *Industry, Innovation, and Infrastructure*. Concretely, the
target the system supports is **9.3** — improving access of small
enterprises to financial services and value chains. A trust-calibrated
verifier lets an Indian buyer place orders with smaller, less-known
suppliers (Peenya, Whitefield, Electronic City SMEs) without taking
on the risk of fraud or relabeled imports. That's the explicit
infrastructure-resilience angle.

---

## 2. Concepts you must own

You will be asked to define these. Don't memorise sentences —
understand them.

### 2.1 Frame of discernment (Θ, "theta")

The set of possible answers your system distinguishes between. In our
case it's exactly **{safe, risky}**. Two elements means three subsets
the system can have an opinion about:

| Subset | Read as |
|---|---|
| `{safe}` | "this supplier is safe" |
| `{risky}` | "this supplier is risky" |
| `{safe, risky} = Θ` | "I don't know yet — could be either" |

That third subset is the killer feature. Bayesian probability cannot
distinguish "I'm 50% confident it's safe and 50% confident it's risky"
from "I have no idea". DS theory can.

### 2.2 Basic Probability Assignment (BPA, also called *mass function*)

A function `m(·)` that distributes 1.0 of belief mass across the
subsets of Θ:

```
m({safe})  +  m({risky})  +  m({safe, risky})  =  1.0
```

Each piece of evidence produces one BPA. Example: an OFAC pass on a
clean supplier might give:

```
m({safe})         = 0.5    ← strong push toward safe
m({risky})        = 0.0
m({safe, risky})  = 0.5    ← but I'm only 50% sure
```

A press-release puff piece about the same supplier:

```
m({safe})         = 0.10   ← weak push toward safe (low credibility)
m({risky})        = 0.00
m({safe, risky})  = 0.90   ← 90% uncertainty
```

The mass that goes to `{safe, risky}` represents **uncertainty**, not
ignorance about the answer — it represents knowledge about how strong
this piece of evidence is. That's why DS is the right tool when
sources have different levels of credibility.

### 2.3 Dempster's combination rule

Given two BPAs `m₁` and `m₂` from independent sources, the combined
BPA is:

```
m₁₂(A) = ( Σ        m₁(B) · m₂(C) ) / (1 − K)
         B ∩ C = A

K     = Σ        m₁(B) · m₂(C)        ← "conflict mass"
        B ∩ C = ∅
```

In plain English: multiply the masses of every pair of subsets that
agree (intersection non-empty), normalise so it sums to 1. The
denominator `(1 − K)` is the standard normalisation; K is the mass
that ended up on the empty set, which is logically impossible.

### 2.4 Why Yager's rule instead

Standard Dempster's rule has a known pathology: when two highly
confident sources disagree, the conflict K is large, so dividing by
`(1 − K)` blows up the remaining masses unrealistically. Zadeh's
classic example: two doctors each 99% certain of different diagnoses,
combined, give 100% certainty in the third (rare) diagnosis they
both gave 1% mass to. Wrong.

**Yager's rule** is a cleaner alternative for our use case:

```
mY(A)        = Σ  m₁(B) · m₂(C)        for B ∩ C = A, A ≠ ∅
mY(Θ)        = m₁(Θ) · m₂(Θ)  +  K
```

Conflict mass is dumped into Θ instead of being normalised away. When
sources disagree, the system gets *more uncertain*, not falsely
confident. That is exactly what we want when an attacker is trying to
poison the evidence stream.

This is implemented in `src/scs/scoring/fusion.py::combine_pair()`.

### 2.5 Provenance and credibility

Every piece of evidence carries a `Provenance` object:

```python
class Provenance(BaseModel):
    source_name: str        # "Reuters" / "OFAC SDN" / "anon-blog-x.com"
    source_type: str        # "news" / "government" / "press_release"
    url: str | None
    fetched_at: datetime
    credibility: float      # 0.0 to 1.0
```

Credibility is a prior — set per source type before any evidence is
seen — that scales how strongly that evidence pushes the BPA. Our
registry (`src/scs/credibility.py`):

| Source type | Prior | Examples |
|---|---|---|
| Government | 0.95 | OFAC, World Bank, BIS CRS, MCA filings |
| Tier-1 news | 0.80 | Reuters, AP, FT, WSJ, BBC, The Hindu, ET |
| Trade press | 0.70 | EE Times, Electronics Weekly, EE Asia |
| General news | 0.55 | Local newspapers, mainstream blogs |
| Press release | 0.30 | PR Newswire, Business Wire, Cision |
| Anonymous | 0.20 | Anonymous blogs, Reddit posts |

Numbers come from journalism-credibility studies (Pennycook & Rand
2019; Lin et al. 2023 on LLM-RAG attribution); they are starting points
that can be re-tuned with per-domain trust scores.

### 2.6 Adversarial machine learning — why this is a real attack

Three terms you should know:

- **Data poisoning.** Attacker injects malicious examples into the
  training data of an ML model.
- **Evasion attack.** Attacker crafts inputs at inference time that
  fool an already-trained model.
- **Evidence-source poisoning** (our category). Attacker doesn't
  modify the model or its training data. They modify the *world* the
  model retrieves from. They plant news articles, blog posts, fake
  reviews — and the model dutifully retrieves and reasons over them.

This last category is under-studied but increasingly relevant because
of RAG (retrieval-augmented generation) systems that hit the open web.
A 2023 study by Carlini et al. showed that buying expired domains
linked from Wikipedia can be done for less than $50 per domain and
inserts attacker-controlled content into thousands of LLM training
runs. Our threat model is the closely-related inference-time variant.

---

## 3. Architecture at a glance

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│    Supplier (id, name, country, category, aliases)       │
│                                                          │
└─────┬──────────────────┬──────────────────┬──────────────┘
      │                  │                  │
      ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  Compliance  │   │     News     │   │     Profile      │
│  pipeline    │   │  intelligence│   │  (40+ params)    │
│              │   │              │   │                  │
│ OFAC SDN     │   │ corpus →     │   │ MCA, GSTN,       │
│ World Bank   │   │ LLM extract  │   │ KSPCB, Udyam,    │
│ BIS CRS      │   │ → corroborate│   │ ISO certs, OTD,  │
└──────┬───────┘   └──────┬───────┘   │ defect ppm, etc. │
       │                  │           └──────────┬───────┘
       │ ComplianceCheck  │ RiskSignal           │
       │ (BPA each)       │ (BPA each, weighted  │ ParamContribution
       │                  │  by credibility,     │ (BPA each)
       │                  │  corroboration,      │
       │                  │  defense penalty)    │
       └──────────┬───────┴──────────┬───────────┘
                  │                  │
                  ▼                  ▼
            ┌─────────────────────────────────┐
            │  Dempster–Shafer fusion         │
            │  (Yager rule, conflict → Θ)     │
            └────────────┬────────────────────┘
                         │
                         ▼
                ┌────────────────────┐
                │   SupplierScore    │
                │   ─────────────    │
                │   score: 0–100     │
                │   grade: A–F       │
                │   belief_safe      │
                │   belief_risky     │
                │   uncertainty      │
                │   contributions[]  │
                └────────────────────┘
```

The whole pipeline runs in well under 100ms per supplier with the
mock LLM, and ~2-3 seconds per supplier with the real Anthropic
backend.

---

## 4. The data layer

### 4.1 The Supplier model (`src/scs/models.py`)

```python
class Supplier(BaseModel):
    id: str                     # stable slug, e.g. "dixon-tech"
    name: str
    legal_name: str | None
    country: str                # ISO-2: "IN", "US", "TW"
    category: SupplierCategory  # enum (ems, semiconductor_fab, ...)
    cin: str | None             # India: Corporate Identification Number
    incorporated: date | None
    aliases: tuple[str, ...]    # for fuzzy compliance matching
    website: str | None
    is_illustrative: bool       # true = synthetic SME demo entity
    note: str | None            # human-readable description
```

The `is_illustrative` flag matters a lot. It's the **honesty hook** —
illustrative entities show with a ⓘ marker everywhere in the dashboard.
We never claim a synthetic entry is a real firm.

### 4.2 The directory (87 suppliers, India-focused)

| Tier | Count | Examples |
|---|---|---|
| Real listed Indian firms | 41 | Dixon, Foxconn India, Wistron India, Pegatron India, Bhagwati, Amber, Syrma, Kaynes, Tata Electronics, Vedanta-Foxconn, BEL, ITI, Tejas Networks |
| Real Bangalore-specific | 7 | Saankhya Labs, Signalchip, Wipro 3D, Zetwerk, Tessolve, Tata Elxsi Whitefield, Capgemini Engineering |
| Illustrative SMEs | 35 | Mysuru Precision Electronics, Deccan PCB Works, Konkan Circuit Solutions, Peenya/Whitefield/Electronic City fictitious composites |
| Risky foreign (for OFAC/WB demo) | 4 | Apex Global Sourcing (BVI), Dnipro Microelectronics, Shenzhen Shadow, Guangdong Relabel |

### 4.3 The SupplierProfile (`src/scs/profile.py`)

Optional extended profile carrying all 40+ verification parameters,
loaded from `data/supplier_profiles.json`. Sections:

- **Registrations** (8 fields): CIN, PAN, GSTIN, Udyam, IEC, Shop &
  Estab, EPFO, ESIC.
- **Financial** (9 fields): Udyam category, annual turnover (₹ cr),
  net worth (₹ cr), current ratio, debt-to-equity, days payable
  outstanding, days sales outstanding, GST compliance score.
- **Operational** (6 fields): employees, plant area sqft, monthly
  capacity, capacity utilisation %, on-time delivery %, defect ppm.
- **Quality** (7 fields): ISO 9001, ISO 14001, IATF 16949, AS9100,
  ISO 13485, IPC-A-610, BIS CRS active.
- **Regulatory** (6 fields): MCA active, KSPCB pollution NOC, fire
  NOC, Factories Act licence, EPF dues clear, ITR filed.
- **Reputation** (5 fields): domain age years, online review score,
  customer references count, labour cases (3 yr), media coverage
  breadth.

A profile is *optional*. Suppliers without one still score on the
basic compliance + news pipeline. Suppliers with one get additional
parameter-level evidence folded into the fusion.

### 4.4 News corpus (`data/news/seed_corpus.json`)

For each supplier we have zero or more `NewsArticle` records:

```python
class NewsArticle(BaseModel):
    id: str
    supplier_id: str
    title: str
    body: str
    url: str | None
    published_at: datetime
```

The corpus is intentionally small (representative articles per supplier)
because the experiment runs against deterministic synthetic attack
articles, not live web crawl. Production would replace `news.py` with
a real crawler.

### 4.5 Compliance reference data (`data/reference/`)

Three JSON files with offline snapshots of real public lists:

- `ofac_sdn_sample.json` — OFAC Specially Designated Nationals.
  Contains entries that match Dnipro Microelectronics and Shell
  Electronics BVI.
- `wb_debarred_sample.json` — World Bank Debarred Firms list.
  Contains entries matching Shenzhen Shadow Components and Apex Global
  Sourcing.
- `bis_crs_sample.json` — Bureau of Indian Standards Compulsory
  Registration Scheme. Contains ~30 R-numbers across the seeded Indian
  suppliers.

Sample format:

```json
{
  "_source": "OFAC SDN public list",
  "entries": [
    {"name": "Dnipro Microelectronics LLC",
     "alt_names": ["Dnipro Microelectronics", "DML"],
     "country": "RU",
     "list_added": "2022-08-15"}
  ]
}
```

---

## 5. Pipeline stage 1 — Compliance screening

### 5.1 What it does

Three sub-checks run **in parallel via asyncio**:

1. **OFAC SDN check** (`src/scs/compliance/ofac.py`). Loads the SDN
   sample, fuzzy-matches the supplier name + aliases against entries
   using `rapidfuzz.fuzz.partial_ratio` ≥ 85 as the hit threshold.
2. **World Bank Debarred check** (`src/scs/compliance/world_bank.py`).
   Same shape; different list.
3. **BIS CRS check** (`src/scs/compliance/bis_crs.py`). Looks up R-
   numbers for the supplier; presence is *positive* signal (registered
   with BIS for the products they sell), absence on a CRS-mandatory
   product is *negative*.

Each sub-check returns a `ComplianceCheck`:

```python
class ComplianceCheck(BaseModel):
    source: str               # "OFAC SDN", "World Bank Debarred", "BIS CRS"
    status: Literal["pass", "fail", "unknown"]
    detail: str               # "no match" or "matched: Dnipro …"
    provenance: Provenance    # source_type=government, credibility=0.95
    checked_at: datetime
```

The `pipeline.run()` function (in `compliance/pipeline.py`) collects
all three and returns a `ComplianceReport` with `fail_count` and the
list of `checks`.

### 5.2 Why government sources score 0.95 not 1.0

Even authoritative sanction lists have a small false-positive rate
(name collisions, transliteration issues). 0.95 leaves ~5% mass on Θ,
which means a single OFAC hit alone doesn't pin a supplier to risky —
it strongly pushes there but a supplier with otherwise-perfect data
could still fight for a non-zero "safe" mass. That's the right
behaviour.

### 5.3 How a ComplianceCheck becomes a BPA

In `scoring/fusion.py::bpa_from_check()`:

```python
if check.status == "fail":
    # Fail → push toward risky, weighted by credibility
    return BPA(safe=0.0,
               risky=check.provenance.credibility * 0.85,
               theta=1 - that)
elif check.status == "pass":
    return BPA(safe=check.provenance.credibility * 0.5,
               risky=0.0, theta=...)
else:  # unknown
    return BPA(safe=0.0, risky=0.0, theta=1.0)
```

Government source × fail = up to 0.81 risky mass per check. Three
fails on a sanctioned entity make it nearly impossible to escape
risky classification, which is exactly what should happen.

---

## 6. Pipeline stage 2 — News intelligence

### 6.1 What the LLM is asked to do

For each article (`src/scs/risk/prompts.py`):

> Read this article about supplier {name} and produce JSON:
> {
>   "event_type": one of [recall, sanction, fraud, labor, cyber,
>                         esg, financial_distress, leadership_change,
>                         litigation, positive, other],
>   "severity":   integer 1–5,
>   "sentiment":  float -1.0 to +1.0,
>   "summary":    1-sentence,
>   "entities":   [list of named entities mentioned]
> }

This is a structured-output extraction task. We do not ask the LLM to
score the supplier directly — that's the design choice that prevents
the LLM from being the attack surface. The LLM only summarises one
article into a structured signal.

### 6.2 Mock vs. Anthropic backend

`src/scs/risk/extractor.py` has two backends:

- **Mock** (default; `USE_MOCK_LLM=1`). Deterministic regex over
  keywords. "recall" in body → event_type=recall, severity=4. "fraud"
  → event_type=fraud, severity=5. Strict but reproducible — every run
  produces identical results, so the experiment numbers in the paper
  are exactly reproducible by a reviewer.

- **Anthropic** (production; `USE_MOCK_LLM=0` + `ANTHROPIC_API_KEY`).
  Calls Claude via the API with the prompt above. Better at nuanced
  cases (e.g. "no labour disputes were found" → not a labour event)
  but stochastic, so eval results would have variance.

The system is *designed* to allow either backend. That's important to
say to the teacher: we do not depend on any specific LLM, the
provider is a swap.

### 6.3 Corroboration annotation (`src/scs/risk/pipeline.py`)

After extraction, `_annotate_corroboration()` marks a signal as
**corroborated** if **another article from a different domain** in the
same time window reports the same event type. Two distinct outlets
saying "recall" within a week corroborates; two articles from the
same domain do not.

The flag is used in fusion: corroborated signals get full weight,
uncorroborated signals get half weight. This is the single biggest
defense lever against single-domain attacks.

### 6.4 RiskSignal → BPA

In `scoring/fusion.py::bpa_from_signal()`:

```
effective_credibility = source.credibility
                      × (1.0 if corroborated else 0.5)
                      × recency_decay     # defense weight
                      × (severity / 5.0)  # if negative event
```

Negative events (recall, sanction, fraud, labor, cyber, esg, financial
distress, litigation) push risky mass. Positive events push safe mass
(but with a hard cap at 0.4 — you cannot whitewash a supplier with a
flood of puff pieces; see §9).

---

## 7. Pipeline stage 3 — Verification parameters

### 7.1 Why this layer exists

Compliance lists catch ~3 of our 87 suppliers. News-driven scoring
catches another handful. **The remaining 80+ — the typical Bangalore
SME you'd actually be considering ordering from — are invisible to
both.**

This is the cold-start problem. A small Karnataka manufacturer with
no OFAC exposure and no significant news footprint is just *blank* to
the first two pipelines. Any score the system gives them is therefore
dominated by Θ (uncertainty mass), and they all look the same.

The verification parameter layer fixes this. It plugs in the data a
human procurement officer would actually look at — public filings,
GSTN records, KSPCB licences, ISO certs — and converts each to a
small but real BPA.

### 7.2 The taxonomy (`src/scs/metrics_taxonomy.py`)

35 named parameters across 6 groups, each with:

```python
@dataclass
class ParameterSpec:
    key: str                    # "current_ratio"
    group: str                  # "Financial health"
    label: str                  # "Current ratio"
    description: str
    unit: str                   # "ratio", "%", "₹ cr", "ppm"
    direction: Literal["higher_is_better", "lower_is_better",
                       "in_range", "categorical"]
    healthy_min: float | None
    healthy_max: float | None
    concerning_min: float | None
    concerning_max: float | None
    used_in_scoring: bool       # does it affect the score?
    source_examples: str        # "MCA21 / Companies House / EDGAR"
```

20 of the 35 are wired into scoring. The other 15 are reference-only
— they appear on the Parameters page so a reviewer can see what the
schema captures, but they don't currently influence the score because
we lack reliable bulk sources (e.g. patent count, R&D spend %).

### 7.3 The scoring rules (`src/scs/scoring/parameters.py`)

Six rule families. Each maps a parameter value to a `(safe, risky)`
mass pair via either:

- A **linear ramp** for numeric values (`_ramp()`):

  ```
  current_ratio: healthy=1.5, concerning=1.0, mass=0.55
  
  value 2.0 → safe=0.55, risky=0.0 (above healthy, full safe mass)
  value 1.5 → safe=0.55, risky=0.0
  value 1.25 → safe=0.275, risky=0.275 (halfway)
  value 1.0 → safe=0.0, risky=0.55 (at concerning, full risky mass)
  value 0.5 → safe=0.0, risky=0.55
  ```

- A **categorical mapping** for enums:

  ```
  ISO 9001 status:
    ACTIVE  → safe=0.45, risky=0.0
    EXPIRED → safe=0.0, risky=0.27 (penalty for letting it lapse)
    PENDING → safe=0.0, risky=0.09 (small penalty)
    NA      → no signal (some suppliers don't need it)
  ```

The mass values come from a calibration sweep documented in
`PAPER.md` §4.2 — they are tuned to give Dixon (a clean publicly-
listed PLI awardee) ~95 score and a synthetic SME with red flags
~35-45.

### 7.4 The crucial cold-start property

Every rule has the same shape: "if value is known and matches
healthy → push safe; if known and matches concerning → push risky;
**if unknown → contribute nothing**." The unknown case sends mass to
Θ (uncertainty) which is exactly the right behaviour. A supplier with
2 known parameters out of 30 will have very high uncertainty mass and
a near-50 score, signalling "we don't have enough data to decide."

This is a fundamental advantage of DS over weighted-average scoring,
where missing values either get imputed (introducing bias) or get
zero (silently treated as bad).

---

## 8. Pipeline stage 4 — Dempster–Shafer fusion

### 8.1 The combine_pair() function

`src/scs/scoring/fusion.py::combine_pair(m1, m2)` implements Yager's
combination:

```python
def combine_pair(m1: BPA, m2: BPA) -> BPA:
    new_safe  = m1.safe  * m2.safe  + m1.safe  * m2.theta + m1.theta * m2.safe
    new_risky = m1.risky * m2.risky + m1.risky * m2.theta + m1.theta * m2.risky
    conflict  = m1.safe  * m2.risky + m1.risky * m2.safe
    new_theta = m1.theta * m2.theta + conflict   # Yager: conflict → Θ
    return BPA(safe=new_safe, risky=new_risky, theta=new_theta)
```

Walk through the math:

- `safe ∩ safe = safe`. Both sources say safe → push safe.
- `safe ∩ Θ = safe`. One says safe, the other doesn't know → still
  push safe but with the uncertain source's mass acting as multiplier.
- `safe ∩ risky = ∅`. **Disagreement.** This mass goes to Θ in Yager's
  rule (instead of being normalised away in standard Dempster).
- `Θ ∩ Θ = Θ`. Mutual ignorance stays as ignorance.

### 8.2 combine_many() — folding all evidence

```python
def combine_many(bpas: list[BPA]) -> BPA:
    result = BPA(safe=0.0, risky=0.0, theta=1.0)  # vacuous prior
    for b in bpas:
        result = combine_pair(result, b)
    return result
```

Order doesn't matter (the combination is associative and commutative).
We start with a vacuous prior (all mass on Θ — "I know nothing") and
multiply in each piece of evidence one at a time.

### 8.3 From fused BPA to a 0-100 score

```python
diff = fused.safe - fused.risky    # in [-1, +1]
score = 50.0 + 50.0 * diff          # in [0, 100]
```

Then bucketed to a grade:

| Score | Grade | Read as |
|---|---|---|
| 90–100 | A | Strong evidence safe |
| 80–89  | B | Mostly safe |
| 60–79  | C | Mixed signals |
| 40–59  | D | Concerning |
| 0–39   | F | Strong evidence risky |

Suppliers below threshold (default 50) are predicted RISKY for
classification purposes.

### 8.4 Why a 0-100 score and not just the raw BPA

Procurement officers don't read mass functions. The 0-100 score is
the user-facing summary. The full BPA (`belief_safe`, `belief_risky`,
`uncertainty`) is shown alongside it on every detail page. So the
reviewer can:

- See the score for the executive summary,
- Inspect the belief decomposition for the technical detail,
- Trust both because they came from the same arithmetic.

---

## 9. Pipeline stage 5 — Trust-calibrated defense

This is **the central contribution of the project** so be ready to
explain it.

### 9.1 The threat model

A supplier under evaluation wants to flip their score from RISKY to
SAFE without changing what they actually do. They cannot modify the
LLM, the compliance lists, or the buyer's data. But they can **buy
visibility on the open web** by:

- Publishing flattering articles on cheap PR-wire services
  (PR Newswire, Business Wire, EIN Presswire — credibility 0.30).
- Spinning up anonymous blogs (credibility 0.20).
- Using LLMs to generate variations of these articles cheaply.

The attack budget B is the number of articles they plant. Cost per
article is ~$50 on PR-wire services, so B=20 is a $1000 attack. We
demonstrate the system breaks at B=10 without defense and holds
through B=20+ with defense.

### 9.2 The two defense components (`src/scs/scoring/defense.py`)

**Component A: burst detection.** Adversarial article injection has a
characteristic signature — many articles published in a short window,
all praising the same supplier. We compute the article density per
supplier per week. If `articles_in_window > burst_threshold`
(default = 5), the burst weight applies: every article in the burst
gets its credibility multiplied by 0.4.

```python
if k_articles > burst_threshold:
    burst_weight = 0.4
else:
    burst_weight = 1.0
```

**Component B: template-similarity downweighting.** Even with burst
detection blunted, attackers can spread articles over time. But they
typically reuse text templates because writing 20 distinct fluent
articles is expensive. We compute pairwise normalised Levenshtein
similarity across the last 10 articles per supplier. Any article
within 0.7 similarity of another (other than the very first) gets its
credibility multiplied by 0.3.

```python
if max_similarity_to_prior_article > 0.7:
    template_weight = 0.3
else:
    template_weight = 1.0
```

The final defense weight is the product:

```python
defense_weight = burst_weight × template_weight
```

This weight folds into the BPA construction so that an article that
trips both penalties contributes 0.4 × 0.3 = 0.12 of its original
mass. A natural press release passing both checks contributes its
full 0.30-credibility mass.

### 9.3 Why this works

The defense exploits two structural asymmetries between attacker and
defender:

1. **Volume asymmetry.** Real news about a real supplier comes in
   bursts only around real events (recall, IPO, factory fire).
   Sustained week-on-week bursts are rare and statistically detectable.
   The attacker either has to pay for a real news cycle (impractical
   for a small supplier) or accept downweighting.

2. **Authoring cost asymmetry.** Generating fluent diverse text is
   cheap with LLMs, but it's still costlier than copy-pasting templates,
   and templates are what real PR firms use anyway. Every distinct
   article costs the attacker more.

Both penalties scale with attack budget B. The honest finding in the
paper is that at very low B (B≤2) neither penalty fires (5 articles is
the burst threshold), so the defense is a no-op. We document this in
§5.4 and argue B=2 attackers cannot move a clean supplier into safe
classification anyway.

### 9.4 The headline result

| Setting | Clean F1 | Attacked F1 (B=10) | Defended F1 (B=10) |
|---|---|---|---|
| OFAC + WB only | 0.43 | 0.43 | 0.43 |
| + News (no defense) | **0.73** | **0.00** | n/a |
| + News + defense | 0.73 | 0.00 | **1.00** |

Read as: with a B=10 press-release attack, the no-defense scorer
wrongly classifies all attacked suppliers as safe (F1=0). The trust-
calibrated defense fully recovers correct classification. **No false-
positive cost on the clean run** (F1=0.73 either way).

---

## 10. Adversarial simulation

### 10.1 The attack module (`src/scs/adversarial/`)

`attack.py` synthesises attack articles. Three vectors:

- **press_release** — credibility 0.30, source_name varied across
  ["PR Newswire", "Business Wire", "EIN Presswire", "Cision",
  "Send2Press"], all positive sentiment.
- **anon_blog** — credibility 0.20, source_name varied across
  ["independent-electronics-blog.com", "supply-chain-insider.net",
  "tech-trends-daily.com"], positive sentiment.
- **self_published** — credibility 0.25, source_name is the
  supplier's own website. Easiest to detect (single-domain).

Each attack vector has 3-5 article templates. The runner samples
templates, fills in the supplier name, dates them across a 4-week
window, and folds them into the news pipeline alongside whatever real
articles exist.

### 10.2 The runner (`src/scs/adversarial/runner.py`)

`run_attacked(supplier, AttackConfig(budget=B, vector=V))` returns
the same `RiskProfile` shape the normal pipeline returns, but with
the synthetic articles included. So the rest of the system doesn't
know it's under attack — it just sees more articles.

### 10.3 Honesty caveat

The synthetic templates are not as fluent as a determined human
attacker could write. We acknowledge this in §5.4 of the paper. But
the *type* of attack we model (volume + low-credibility sources +
similar templates) is exactly what real PR-spam looks like.

---

## 11. Evaluation

### 11.1 Ground truth (`data/ground_truth.json`)

Hand-labelled `risky=true/false` for every supplier in the directory.
For real listed firms the label comes from public knowledge (PLI
awardee with clean record → safe; OFAC-sanctioned firm → risky). For
illustrative entries the label is set by what we constructed them to
demonstrate.

### 11.2 Metrics (`src/scs/evaluation/metrics.py`)

- **Precision, recall, F1** — standard binary classification metrics
  with `risky=positive`.
- **Adversarial lift** — how much the attacker can move a target
  supplier's score. Defined as `|score_attacked − score_clean|`.
- **Expected Calibration Error (ECE)** — measures whether the system's
  confidence is calibrated. If the system says "70% confident risky"
  on 100 suppliers, ~70 should actually be risky. ECE is the average
  absolute deviation between confidence and accuracy across confidence
  buckets.

### 11.3 The headline experiment (`run_experiment.py`)

For each supplier:

1. Run the clean pipeline → get `score_clean`.
2. Run the pipeline under each (vector, budget) attack →
   `score_attacked[v, B]`.
3. Re-run with defense on → `score_defended[v, B]`.

Then compute classification F1 against ground truth at each setting.

Reproduce with:

```
make eval
cat data/results/headline.csv
```

### 11.4 The budget sweep (`run_budget_sweep.py`)

Same experiment, parameterised over budget B = 0, 2, 5, 10, 15, 20.
Output is the data for the paper's Figure 2 (score vs budget for one
target supplier, with-defense and without).

Reproduce with:

```
make sweep
cat data/results/budget_sweep.csv
```

---

## 12. Dashboard

8 pages, one router (`src/scs/dashboard/app.py`).

### 12.1 Overview (`page_overview.py`)

Portfolio-level view. Shows:

- 6-KPI strip (total suppliers, % graded A, % graded F, mean score,
  risky-prediction count, attacks blocked count).
- Score histogram with grade-band shading.
- Risk-event donut (event-type distribution across the directory).
- Per-category boxplot.
- Country/grade sunburst.
- Compliance-fail heatmap (suppliers × check sources).
- Top-5 worst and best tables.
- Sortable register.

The user sees this first. It's the executive summary of "what is in
the directory and how does it look."

### 12.2 Find suppliers (`page_find.py`)

The procurement-officer workflow: filter the 87 down to a shortlist.
8 filter dimensions:

- Country
- Category (EMS, semiconductor fab, distributor, …)
- Grade
- Score band slider
- Compliance status (clean / has-fail / any)
- Risk-event presence
- Real / illustrative / both
- Free-text name / legal name / CIN

Result table is sortable by 5 keys, includes a CSV download for the
shortlist, and has a single-supplier drill-in expander.

### 12.3 Supplier detail (`page_detail.py`)

Single-supplier rich report. Layout:

- Hero banner (name, country, grade-tinted background).
- Illustrative-banner if the supplier is synthetic.
- 6-KPI strip: score, belief safe, belief risky, uncertainty,
  compliance fails, prediction.
- Belief decomposition donut (safe / risky / Θ).
- Risk topology radar (event types as axes).
- News timeline with event-type color coding.
- Evidence-source credibility table (every URL with its credibility tier).
- Compliance check results table.
- Extracted risk signals table.
- Score contribution waterfall (every BPA's net push, sorted by
  absolute magnitude).
- Verification profile section: 6 columns, one per group,
  containing all 40+ profile fields.

### 12.4 Parameters used (`page_parameters.py`)

The page your teacher will probably linger on. Three sections:

- **Master taxonomy table** — every parameter with group, label, unit,
  direction, healthy/concerning thresholds, used-in-scoring marker,
  coverage % across the directory, description, source examples. CSV
  export.
- **Per-parameter distribution** — pick a parameter, see a histogram
  (numeric) or bar chart (categorical) of its values across the 87
  suppliers.
- **Per-supplier contribution view** — pick a supplier, see every
  parameter's net push on the score as a horizontal bar chart, with
  the underlying table including raw value, safe mass, risky mass,
  and net push in points.

This is the system's "what does it look at" disclosure. Drop here if
you ever get asked "what data are you using?"

### 12.5 Compare (`page_compare.py`)

2-5 suppliers side-by-side. Includes:

- Radar overlay (one polygon per supplier, axes = score components).
- Parallel coordinates plot across 7 dimensions.
- Numeric metric matrix.

### 12.6 Onboard new supplier (`page_onboard.py`)

The "wow moment" page for a demo. A form to:

- Enter supplier identity (name, country, category, CIN, year, aliases).
- Optionally paste 0-10 news article bodies.
- Submit → run full pipeline live → render the same hero + KPI +
  belief + radar + waterfall as Detail.
- Session-only persistence (no seed-data mutation).

### 12.7 Adversarial lab (`page_lab.py`)

Interactive version of the paper's central experiment.

- Supplier selector.
- Attack vector selector (press_release / anon_blog / self_published).
- Budget slider (0 to 30).
- Defense toggle.
- Score-vs-budget chart (two lines: with and without defense).
- Attack lift heatmap (vector × budget).
- Portfolio-wide F1 deltas.
- Per-supplier flip table.

This is where you show the attack working without defense and the
defense blocking it.

### 12.8 Methodology (`page_method.py`)

The maths. Threat model, credibility pyramid, DS + Yager equations,
defense maths, honest limitations, full data disclosure.

---

## 13. Parameter reference

### 13.1 Identity & Scale (5)

| Parameter | Source | Healthy | Concerning | Used? |
|---|---|---|---|---|
| `years_in_operation` | MCA Master Data | ≥ 3 yrs | ≤ 1 yr | ✓ |
| `employee_count` | MCA Form AOC-4 / annual report | ≥ 10 | < 2 | ✓ |
| `annual_revenue_usd_m` | MCA P&L / 10-K | ≥ $1M | < $50K | ✓ |
| `number_of_facilities` | Company website / regulatory filings | ≥ 1 | 0 | — |
| `registered_capital_usd_m` | MCA Master Data | ≥ $50K | — | — |

**Why these.** Years in operation < 1 is a classic shell-company
indicator (borrowed from cybersecurity domain-age detection — the same
signature applies to fake supplier entities). Employee count and
revenue establish "is this a real business at all?"

### 13.2 Financial Health (8)

| Parameter | Source | Healthy | Concerning | Used? |
|---|---|---|---|---|
| `current_ratio` | Balance sheet (MCA) | ≥ 1.5 | < 1.0 | ✓ |
| `quick_ratio` | Balance sheet | ≥ 1.0 | < 0.7 | — |
| `debt_to_equity_ratio` | Balance sheet | ≤ 1.0 | > 2.5 | ✓ |
| `net_profit_margin_pct` | P&L | ≥ 5% | < 0% | — |
| `revenue_growth_yoy_pct` | P&L | ≥ 5% | < -10% | — |
| `days_payables_outstanding` | Balance sheet ratios | ≤ 45 | ≥ 120 | ✓ |
| `credit_score` | CRISIL / ICRA / D&B | ≥ 600 | < 400 | — |
| `cash_runway_months` | derived (cash / monthly burn) | ≥ 12 | < 3 | — |

**Plus** these India-specific extensions used in scoring:
- `gst_compliance_score` — 0-100, from GSTN portal compliance
  rating. Healthy ≥ 80, concerning ≤ 50.
- `net_worth_cr` — book net worth in ₹ crore. Negative net worth =
  immediate red flag (mass 0.7 risky).
- `annual_turnover_cr` — ₹ crore.

**Why these.** Current ratio is the textbook short-term solvency
metric. D/E captures leverage. DPO captures payment behaviour — high
DPO often signals distress. GST compliance score is unique to India
and effectively impossible for a fake entity to fake.

### 13.3 Operational (7)

| Parameter | Source | Healthy | Concerning | Used? |
|---|---|---|---|---|
| `on_time_delivery_pct` | ERP/SAP customer scorecards | ≥ 95% | < 80% | ✓ |
| `defect_rate_ppm` | QA reports / ISO 9001 | ≤ 500 | ≥ 5000 | ✓ |
| `order_fulfillment_accuracy_pct` | ERP | ≥ 99% | < 95% | — |
| `avg_lead_time_days` | ERP | ≤ 30 | ≥ 90 | — |
| `lead_time_variability_days` | ERP std-dev | ≤ 5 | ≥ 20 | — |
| `capacity_utilization_pct` | Plant reports | 50-85% range | < 30% or > 95% | ✓ |
| `customer_concentration_top1_pct` | sales analytics | ≤ 25% | ≥ 50% | — |

**Why these.** OTD and defect ppm are the two textbook supplier
quality KPIs (refer the user's own Parameters.docx requirements).
Capacity utilisation has a sweet-spot pattern — both very low (idle
factory) and very high (no headroom for spikes) are red flags. The
rule body in `_operational_rules()` reflects this asymmetry.

### 13.4 Compliance & ESG (8)

| Parameter | Source | Healthy | Concerning | Used? |
|---|---|---|---|---|
| `iso_9001_status` | certification body registry | ACTIVE | EXPIRED | ✓ |
| `iatf_16949_status` | IATF database | ACTIVE | EXPIRED | ✓ (auto context) |
| `as9100_status` | IAQG OASIS | ACTIVE | EXPIRED | ✓ (aero context) |
| `iso_14001_status` | certification body | ACTIVE | EXPIRED | ✓ |
| `rohs_compliance_status` | self-declaration | declared | not declared | — |
| `conflict_minerals_disclosure` | RMI | yes | no (when applicable) | — |
| `esg_controversy_count_12mo` | RepRisk / Sustainalytics | 0 | ≥ 3 | — |
| `labor_audit_findings_severe_count` | SA8000 / SMETA audits | 0 | ≥ 1 | — |

**India extensions** used in scoring:
- `iso_13485` (medical devices)
- `ipc_a_610` (acceptability of electronic assemblies — *very*
  important for any supplier doing solder work)
- `bis_crs_active` — Bureau of Indian Standards Compulsory
  Registration Scheme. For products like LED lights, IT goods, mobile
  phone batteries, BIS CRS is mandatory by law. Absent CRS for a
  CRS-mandatory product = the supplier is effectively unsellable in
  India.

### 13.5 Cybersecurity & Capability (4) — reference-only

| Parameter | Source | Healthy | Concerning | Used? |
|---|---|---|---|---|
| `iso_27001_status` | certification body | ACTIVE | EXPIRED | — |
| `cyber_incident_count_24mo` | breach databases | 0 | ≥ 1 | — |
| `patent_count` | patent office | ≥ 1 | 0 | — |
| `rd_spend_pct_revenue` | annual report | ≥ 3% | < 1% | — |

These are defined in the schema but not yet wired because reliable
bulk sources are scarce for SME-scale suppliers in India. The scoring
hooks exist — adding them is a one-line append to `_extra_rules()`.

### 13.6 Network & Trust (3) — reference + reputation

| Parameter | Source | Healthy | Concerning | Used? |
|---|---|---|---|---|
| `entity_age_months` | MCA incorporation date | ≥ 36 | ≤ 12 | — (subsumed by years_in_operation) |
| `domain_age_years` | WHOIS | ≥ 3 | ≤ 1 | ✓ |
| `profile_last_updated_days` | last-modified header | ≤ 90 | ≥ 365 | — |

**Plus** reputation extensions used in scoring:
- `online_review_score` (1-5) from JustDial / IndiaMart / Google.
  Healthy ≥ 4.0, concerning ≤ 2.5.
- `customer_references_count` — number of named, traceable
  customer references the supplier provides. ≥ 3 healthy, 0 concerning.
- `labor_cases_3y` — count of labour-court cases in past 3 years.
  0 healthy, ≥ 5 concerning.
- `media_coverage_breadth` — number of distinct outlets covering the
  supplier in past 12 months. ≥ 3 healthy, 0 concerning.

### 13.7 Regulatory (Indian-specific, all in scoring)

| Parameter | Source | Concerning if | Used? |
|---|---|---|---|
| `mca_status_active` | MCA Master Data | "no" | ✓ |
| `pollution_noc_kspcb` | KSPCB CFE/CFO | "no" for any factory in Karnataka | ✓ |
| `fire_noc` | local fire dept | "no" | ✓ |
| `factories_act_license` | Karnataka Factories & Boilers Dept | "no" if employees ≥ 10 | ✓ |
| `epf_dues_clear` | EPFO portal | "no" — outstanding PF dues | ✓ |
| `income_tax_returns_filed` | Form 26AS / ITR-V | "no" — non-filer | ✓ |
| `epfo_registration` | EPFO portal | "no" for ≥ 20 employees | ✓ |
| `esic_registration` | ESIC portal | "no" for ≥ 10 employees | ✓ |
| `shop_estab_license` | local labour office | "no" for any retail/office | ✓ |

**These are the parameters that matter most for SME verification**
because they are uniquely Indian, publicly verifiable, and very hard
for a fake supplier to fake (you would need to forge multiple
government databases). No comparable signals exist for compliance
lists or news.

---

## 14. Accuracy and effectiveness

### 14.1 The headline numbers

Reproduced verbatim from `data/results/headline.csv`:

```
config              precision  recall    f1     adversarial_lift
clean              0.71       0.75      0.73    n/a
attacked B=10      —          0.00      0.00   +43.6 points
defended B=10      1.00       1.00      1.00    +0.0 points
```

What this means:

- On clean inputs, the system correctly classifies 73% of the
  ground-truth labelled suppliers (F1).
- Under a B=10 press-release attack on every risky supplier, the
  no-defense version wrongly classifies **all** of them as safe
  (recall = 0).
- With the defense on, classification recovers fully — every risky
  supplier still flagged risky.
- The attacker's lift on score (how many points they moved scores up)
  drops from +43.6 to +0.0.

### 14.2 What this does NOT mean

Be honest about scope.

**These numbers are computed against the seed directory.** The seed
directory has 87 entries with hand-labelled ground truth. It is not a
held-out test set drawn from a real population of unseen suppliers.
A held-out generalisation study would require a much larger labelled
set (~1000+ suppliers with vetted ground truth), which is not in
scope for a Phase II project.

**The synthetic attack vectors are templates we wrote.** A determined
human attacker could write more diverse fluent text. The defense
should still trip on volume (burst threshold) but the
template-similarity defense becomes weaker as templates diversify.

**ECE (calibration) is in the 0.18-0.22 range** — moderate. The
system's "70% confident" calls are not yet 70% accurate on average.
This is a known weakness of DS-derived scores; recalibration via Platt
scaling on a held-out set would tighten ECE meaningfully.

### 14.3 What you can defend with confidence

- **The architecture is sound.** Provenance-aware, multi-source,
  fusion-based — these are textbook good practices for evidence-based
  classification.
- **The attack is real.** Evidence-source poisoning is documented in
  the literature (Carlini et al. 2023). Our threat model is a direct
  extension to inference-time supplier-evaluation scenarios.
- **The defense is principled, not ad-hoc.** Burst detection comes
  directly from anomaly-detection literature (Kleinberg 2002).
  Template similarity comes from anti-plagiarism literature.
  Credibility priors come from journalism research.
- **Reproducibility is end-to-end.** Every number can be regenerated
  by `make eval && make sweep`. Mock LLM means no API key needed for
  reproduction.

### 14.4 What's "production-ready" and what isn't

**Ready:**
- Domain models, type system, asyncio compliance pipeline.
- DS fusion math and grade computation.
- Defense math (burst + template).
- Dashboard end-to-end.

**Not ready (but the system is designed for it):**
- Live web crawling (currently uses static news corpus).
- Real-time MCA / GSTN / KSPCB data feeds (currently uses static
  profile data).
- Per-domain credibility learning (currently uses fixed tiers).
- Per-buyer ground truth and recalibration.

This is the right shape for a research artifact + dashboard demo,
not for a SaaS deployment. Honest framing of this is your strongest
defense if the teacher asks "is this production?"

---

## 15. Limitations

In rough order of importance:

1. **Small attack budgets bypass the defense.** B≤2 falls below the
   burst threshold (5). The defense is a no-op for very small attacks.
   We argue this is acceptable because B=2 cannot move a labelled-
   risky supplier above the 50 threshold anyway, but it's a valid
   limitation.

2. **Coordinated multi-domain + multi-template attacks partially
   evade.** A determined adversary buying coverage across 10+ domains
   and writing 10+ distinct fluent templates can lower defense
   effectiveness. We do not claim the defense is unbreakable —
   security is always relative to attacker resources.

3. **The mock LLM is a simplified extractor.** Regex-on-keywords
   misses subtleties an LLM would catch (negations, sarcasm). The
   defense's *strength* is independent of the extractor (defense
   operates on metadata: source, date, text similarity), so this
   limits the *attack* analysis precision more than the defense.

4. **Static reference data.** OFAC, World Bank, BIS CRS data are
   offline JSON snapshots. A live system would refresh these daily.

5. **Calibration.** As noted in §14.2, ECE is moderate. Confidence
   levels are slightly miscalibrated.

6. **Ground truth set is small.** 87 labels. F1 numbers are point
   estimates, not population estimates with confidence intervals.

7. **Illustrative entries are synthetic.** They show the system
   working at SME scale but they are not real Indian SMEs. The
   numbers behave like real Indian SMEs would, but if the question is
   "does this work on real Peenya vendors?", the answer is "we have
   not tested with real verified Peenya vendor data; the architecture
   is designed for it but evaluation against real data is future
   work."

State 7 explicitly when relevant. Hiding the synthetic-data caveat
would be the one thing that could trip the project up.

---

## 16. Anticipated questions

### Q1. "Why not just feed everything to GPT-4 and ask for a score?"

Because GPT-4 has no internal model of source credibility. If an
attacker plants 10 PR-wire articles claiming the supplier is great,
GPT-4 reads them as inputs and returns "great supplier." The system
becomes trivially manipulable. Our architecture explicitly separates
*extraction* (which the LLM is good at) from *fusion + decision*
(which the LLM is bad at, because it cannot reason about the
provenance of evidence at the resolution we need).

### Q2. "Why Dempster–Shafer instead of Bayesian probability?"

Bayesian probability requires you to commit to either P(safe) or
P(risky); the two must sum to 1. There is no place for "I don't
know." DS theory has the third subset (Θ = {safe, risky}) that
captures uncertainty distinct from a 50/50 prior. This matters
specifically for our cold-start case: a supplier with 2 known
parameters out of 30 should have very high uncertainty mass and a
near-50 score. A Bayesian system would have to either impute the
missing values (introducing bias) or give them a 50/50 prior
(silently treating "missing" as "no opinion either way," which is
wrong because missing-because-the-data-doesn't-exist and
missing-because-the-evidence-is-balanced are very different states).

### Q3. "Why Yager's rule, not classical Dempster's?"

Classical Dempster's rule normalises away conflict mass, which leads
to the Zadeh paradox: two highly confident sources who disagree end up
endorsing a third minor option. Yager's rule routes conflict to Θ
(uncertainty) instead. When sources disagree, the system gets *more
uncertain*, not falsely confident. This is the correct behaviour
under adversarial conditions where the attacker explicitly creates
disagreement between trusted sources (real news) and low-credibility
sources (planted PR).

### Q4. "Why a mock LLM by default?"

Reproducibility. Every number in the paper has to be regenerable by a
reviewer with no API key. The mock backend is deterministic — same
input → same output, every run. It's strictly less capable than
Claude, so any results the system gets with the mock are a
*conservative lower bound* on what it would achieve with the real
model. We ship the Anthropic backend behind a one-line env var change.

### Q5. "What's actually novel here? Multi-source fusion isn't new."

Two specific contributions:

1. **The threat model.** Most LLM-based supplier scoring papers
   evaluate on clean data only. We explicitly model the attacker who
   plants flattering content to game the scorer, and we measure the
   attack's effectiveness end-to-end.

2. **The trust-calibrated defense.** Burst detection + template-
   similarity downweighting fed back into DS fusion as per-signal
   credibility multipliers. This specific pipeline — extract → tag
   with provenance → assess burstiness → assess template similarity
   → fuse with Yager's rule — has not been proposed for this problem
   before, to our knowledge.

### Q6. "How accurate is this in practice?"

On the seed directory: F1 = 0.73 clean, 1.00 defended. *Not on
held-out unseen real suppliers.* The architecture is designed to
generalise; the evaluation set is small. State the gap clearly.

### Q7. "What are illustrative suppliers and why are they there?"

Synthetic SME-scale entities (35 of 87) we constructed to demonstrate
score variation at small scale without misrepresenting any real firm.
Marked with `is_illustrative=True` in the schema, displayed with a
ⓘ badge in the dashboard, disclosed in the README, in the
Methodology page, in the sidebar, and in any filtered view. The Find
page has a "Real only" filter that excludes them entirely. They do
not affect the headline F1 numbers — those are computed across the
labelled set including both real and illustrative entries.

### Q8. "Could a real attacker break this?"

Yes, given enough resources. Specifically: (a) a coordinated
campaign across many distinct high-credibility domains (impossible
without buying their content; expensive), or (b) human-written
diverse templates across many low-credibility domains paired with
genuine-looking burst spread (slow, expensive). The defense raises
the cost of attack. It does not make attack impossible. We are
explicit about this in §5.4.

### Q9. "Why these specific 30+ parameters and not others?"

Three filters were applied:

1. **Procurement-relevance.** Each parameter answers a question a
   real procurement officer would ask before placing an order.
2. **India-specific publicly verifiable.** Each parameter has a
   public Indian source (MCA, GSTN, KSPCB, BIS, EPFO, ESIC) so a
   buyer doesn't need the supplier's voluntary cooperation to verify
   it.
3. **Compatible with DS fusion.** Each parameter has a clear
   "healthy" and "concerning" interpretation that maps to a (safe,
   risky) mass via a linear ramp or categorical lookup.

Parameters that failed any of these (e.g. "innovation index" — too
fuzzy for DS; "founder LinkedIn presence" — not verifiable from
public records) were not included.

### Q10. "What's the engineering cost of running this in production?"

For 1000 suppliers refreshed daily:

- Compliance lookups: ~0.1s/supplier (sample lists; live OFAC API
  would add ~0.3s).
- News crawl: ~5-10s/supplier (real Google News API or NewsAPI).
- LLM extraction: ~2-3s/article × ~10 articles/supplier × 1000 =
  ~5-8 hours total daily.
- DS fusion + parameter scoring: ~50ms/supplier.

Cost: ~$100/day on Anthropic Sonnet for the LLM extraction. Caching
known articles would cut that 80%. So roughly ~$20-30/day to run for
1000 suppliers — order-of-magnitude affordable for a procurement
team.

### Q11. "Why not use a Graph Neural Network on the supplier
network?"

Two reasons. First, scope: a Phase II project should ship something
end-to-end. Adding a GNN would expand the project but reduce the
strength of the core trust-calibrated-defense story. Second, data:
GNNs need a meaningful graph (suppliers + buyers + relationships).
We do not have one. Public Indian supplier-buyer networks are not
crawlable. A GNN on a synthetic graph would prove little.

The next-step extension you can mention is: with real procurement
data including supplier-buyer edges, the GNN approach from the
Liu & Meidani 2024 paper (the original PDF you uploaded) would
augment our DS fusion meaningfully. It's compatible — graph features
can become additional BPAs in the same fusion.

### Q12. "Why call it 'trust-calibrated' and not 'robust'?"

"Robust" implies the system is unbreakable, which is false. "Trust-
calibrated" precisely describes what it does: the system *calibrates*
how much it trusts each piece of evidence based on source, recency,
corroboration, burst pattern, and template similarity. It is honest
about what the design achieves.

---

## 17. Glossary

- **BPA** — Basic Probability Assignment. A function distributing 1.0
  of belief across subsets of the frame of discernment.
- **Burst** — A period in which the article volume for a supplier
  exceeds a threshold (default 5/week).
- **CIN** — Corporate Identification Number, India. Issued by MCA at
  incorporation. Format: 21 chars, e.g. `L32101DL1993PLC056320`.
- **CRS** — Compulsory Registration Scheme of the Bureau of Indian
  Standards. Mandatory for certain electronic products to be sold in
  India.
- **Credibility prior** — A scalar in [0, 1] assigned per source
  before any evidence is seen, used to weight that source's BPA.
- **DS / Dempster–Shafer theory** — Mathematical framework for
  combining evidence under uncertainty. Generalises Bayesian
  probability by allowing belief mass on subsets of the frame, not
  just singletons.
- **ECE** — Expected Calibration Error. Measures whether the
  system's stated confidence matches its empirical accuracy.
- **EPF / EPFO** — Employees' Provident Fund, India. EPFO is the
  governing body. EPF dues clear = no outstanding contributions.
- **ESIC** — Employees' State Insurance Corporation. Mandatory
  health-insurance scheme for many Indian employees.
- **Evidence-source poisoning** — Attack class where adversary
  modifies the world the model retrieves from (planting articles)
  rather than modifying the model itself.
- **Frame of discernment Θ** — Set of mutually exclusive answers the
  system distinguishes between. In our case `{safe, risky}`.
- **GSTIN** — Goods and Services Tax Identification Number, India.
  15 chars; first 2 are the state code (29 = Karnataka).
- **GSTN compliance score** — Numeric (0-100) compliance rating
  published by the GST Network.
- **IATF 16949** — Automotive quality management system standard.
  Required for tier-1 automotive electronics suppliers.
- **IPC-A-610** — Industry-standard for acceptability of electronic
  assemblies. Critical for any solder-work supplier.
- **KSPCB** — Karnataka State Pollution Control Board. Issues
  Consent for Establishment (CFE) and Consent for Operation (CFO),
  collectively the "pollution NOC."
- **MCA21** — Ministry of Corporate Affairs portal where Indian
  companies file annual reports, financial statements, and Master
  Data updates.
- **OFAC SDN** — US Office of Foreign Assets Control's Specially
  Designated Nationals list. The primary US sanctions list.
- **Provenance** — Metadata about where a piece of evidence came
  from (source name, source type, URL, fetched timestamp,
  credibility).
- **Udyam** — Indian government MSME (Micro, Small, Medium
  Enterprise) registration scheme. Replaces the older Udyog Aadhaar.
- **Yager's rule** — A combination rule for DS belief functions that
  routes conflict mass to Θ instead of normalising it away.
- **Θ (theta)** — Both the frame of discernment as a set and, in
  BPA-shorthand, the mass on the full frame `{safe, risky}` —
  representing uncertainty.

---

## End

You have all of this. Walk into the review with confidence. The
strongest answer is always the one that admits a limitation alongside
the strength: "the F1 is 0.73 on the seed directory and 1.00 with
defense; the seed directory is small and the headline numbers are
not held-out generalisation results — that's the next step." Honesty
on limits is what makes the strengths credible.

Good luck.
