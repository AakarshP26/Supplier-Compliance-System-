# Supplier Compliance & Intelligent Recommendation System

> SDG 9 · Industry, Innovation and Infrastructure
> Experiential Learning, VI Sem · RV College of Engineering

A two-module system that verifies electronics-manufacturing supplier authenticity
and produces an explainable risk score from unstructured signals.

## Why this exists

Manual supplier vetting is slow, reactive, and ignores unstructured signals
(news, filings, sanction-list updates). This project demonstrates an
end-to-end pipeline that:

1. **Verifies** a supplier across multiple compliance sources (sanctions,
   debarment, BIS CRS registration).
2. **Senses** risk from news articles using an LLM that returns structured
   signals.
3. **Scores** every supplier on a 0–100 composite, with per-feature
   contributions so the recommendation is auditable.

## Architecture

```
                 ┌──────────────────────────────┐
                 │  Module 1 — Compliance       │
   suppliers ──▶ │  OFAC · WB Debarred · BIS    │ ─┐
                 └──────────────────────────────┘  │
                                                   ▼
                 ┌──────────────────────────────┐  Composite ──▶ Streamlit
                 │  Module 2 — Risk Sensing     │  scorer        dashboard
   suppliers ──▶ │  News + LLM extraction       │ ─┘
                 └──────────────────────────────┘
```

## Scope

This is a Phase-II MVP. It targets ~25 real Indian electronics suppliers
(a mix of PLI awardees and deliberately risky entities) and runs end-to-end
on a laptop.

Deliberately **out of scope** for this iteration: fine-tuning, persistent
homology, GA weight evolution, GNN, multi-tier graph extraction. These are
on the roadmap for Phase-III and beyond.

## Status

🚧 Under active development — see commit history.
