# Trust-Calibrated Supplier Compliance under Evidence-Source Poisoning

> Companion code & benchmark for the paper:
> **"When Suppliers Game the Algorithm: Evidence-Source Poisoning Attacks on
> LLM-Based Supplier Risk Scoring, and a Trust-Calibrated Defense"**
>
> Aakarsh Prabhu, RV College of Engineering · Experiential Learning, VI Sem.

## Research question

LLM-based supplier risk scoring (Liu & Meidani 2024 and follow-ups) treats
the public information ecosystem — news, filings, reviews — as a trusted
input. But a supplier under evaluation is not a passive subject of analysis;
they have means and motive to **poison the evidence the LLM reads**.

This work asks:

> *How fragile are LLM-based supplier risk scorers under realistic
> evidence-source poisoning, and can a trust-calibrated multi-source
> fusion model recover the lost robustness without sacrificing accuracy?*

## Contributions

1. **Threat model.** A formal characterisation of evidence-source poisoning
   for compliance scorers, distinct from prompt injection, jailbreaks, and
   model poisoning.
2. **Attack benchmark.** A reproducible adversarial harness that perturbs
   the news corpus around 25 real Indian electronics suppliers (PLI awardees
   plus deliberately risky entities). We report flip rate, score delta, and
   Expected Calibration Error before and after attack.
3. **Defense.** A trust-calibrated multi-source fusion module using
   Dempster–Shafer evidence combination with source-credibility priors,
   corroboration weighting, and recency decay.
4. **Open code & data.** All seed suppliers, reference lists, prompts,
   adversarial articles, and evaluation scripts are in this repository.

## System overview

```
   ┌──────────────────────────┐    ┌────────────────────────────┐
   │  Module 1 — Compliance   │    │  Module 2 — Risk sensing   │
   │  OFAC · WB · BIS · MCA   │    │  News + LLM extraction     │
   │  per-source credibility  │    │  per-article credibility   │
   └────────────┬─────────────┘    └──────────────┬─────────────┘
                │                                 │
                ▼                                 ▼
        ┌────────────────────────────────────────────────┐
        │   Trust-calibrated fusion (Dempster–Shafer)     │
        │   ⊕ corroboration penalty · recency decay       │
        └────────────────────┬────────────────────────────┘
                             │
                             ▼
                ┌─────────────────────────┐
                │  Adversarial harness    │
                │  inject → re-score →    │
                │  measure Δ, flip, ECE   │
                └─────────────────────────┘
```

## Repository layout

```
src/scs/
  models.py            # Domain models with provenance
  data.py              # Seed supplier loader + fuzzy lookup
  compliance/          # OFAC, World Bank, BIS, MCA21 checkers
  risk/                # News fetch + LLM signal extraction
  scoring/             # Trust-calibrated DS fusion
  adversarial/         # Poisoning attacks + evaluation harness
  evaluation/          # Metrics: flip rate, ECE, score delta
  dashboard/           # Streamlit demo
data/
  seed_suppliers.json
  reference/           # Sanctions/debarment reference snapshots
  news/                # Cached news articles per supplier
  adversarial/         # Synthetic poisoned articles
```

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env  # leave USE_MOCK_LLM=1 for offline demo
python -m scs.evaluation.run_clean       # baseline scores
python -m scs.evaluation.run_attack      # under poisoning
python -m scs.evaluation.run_defended    # with DS fusion defense
streamlit run src/scs/dashboard/app.py   # interactive view
```

## Status

🚧 Active development — see commit history.

## License

Apache 2.0 — see `LICENSE`.
