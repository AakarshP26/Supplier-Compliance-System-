"""Tools available to the Compliance Copilot agent."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from scs.compliance.pipeline import run as run_comp
from scs.data import load_suppliers
from scs.models import Supplier, SupplierCategory, RiskProfile
from scs.risk.extractor import extract_signal
from scs.risk.news import NewsArticle
from scs.risk.pipeline import _annotate_corroboration
from scs.risk.pipeline import run as run_risk_pipeline
from scs.scoring.fusion import fuse
from scs.adversarial.attack import AttackConfig
from scs.adversarial.runner import run_attacked


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _all_supplier_scores() -> list[dict]:
    """Run full pipeline for every supplier and cache results.

    Expensive (~seconds) but called at most once per process lifetime.
    """
    results = []
    for s in load_suppliers():
        try:
            comp = run_comp(s)
            risk = run_risk_pipeline(s)
            sc = fuse(s.id, comp, risk, use_defense=True)
            results.append({
                "id": s.id,
                "name": s.name,
                "country": s.country,
                "category": s.category.value,
                "score": round(sc.score, 1),
                "grade": sc.grade,
                "belief_safe": round(sc.belief_safe, 3),
                "belief_risky": round(sc.belief_risky, 3),
                "uncertainty": round(sc.uncertainty, 3),
                "compliance_fails": comp.fail_count,
                "article_count": risk.article_count,
                "is_illustrative": s.is_illustrative,
            })
        except Exception as e:
            results.append({"id": s.id, "name": s.name, "error": str(e)})
    return results


def _fmt_supplier_row(r: dict, rank: int | None = None) -> str:
    prefix = f"{rank}. " if rank else "• "
    grade = r.get("grade", "?")
    score = r.get("score", "?")
    bs = r.get("belief_safe", 0)
    br = r.get("belief_risky", 0)
    bu = r.get("uncertainty", 0)
    fails = r.get("compliance_fails", 0)
    return (
        f"{prefix}**{r['name']}** ({r.get('country','?')}) — "
        f"Score: {score}/100, Grade: {grade} "
        f"[m_safe={bs:.2f}, m_risky={br:.2f}, uncertainty={bu:.2f}] "
        f"Compliance fails: {fails} [Source: DS-Fusion pipeline]"
    )


# ---------------------------------------------------------------------------
# Portfolio-aware tools
# ---------------------------------------------------------------------------

def list_risky_suppliers(threshold: float = 50.0, limit: int = 15) -> str:
    """Return suppliers with risk score below threshold, sorted worst-first."""
    scores = _all_supplier_scores()
    risky = [r for r in scores if "error" not in r and r["score"] < threshold]
    risky.sort(key=lambda r: r["score"])
    risky = risky[:limit]
    if not risky:
        return f"No suppliers found with score below {threshold}. Portfolio is clean at that threshold."
    lines = [f"**{len(risky)} suppliers below score {threshold}** (worst first):\n"]
    for i, r in enumerate(risky, 1):
        lines.append(_fmt_supplier_row(r, rank=i))
    return "\n".join(lines)


def portfolio_summary() -> str:
    """Return aggregate portfolio statistics with DS belief breakdown."""
    scores = _all_supplier_scores()
    ok = [r for r in scores if "error" not in r]
    if not ok:
        return "No supplier data available."
    n = len(ok)
    avg_score = round(sum(r["score"] for r in ok) / n, 1)
    avg_safe = round(sum(r["belief_safe"] for r in ok) / n, 3)
    avg_risky = round(sum(r["belief_risky"] for r in ok) / n, 3)
    avg_unc = round(sum(r["uncertainty"] for r in ok) / n, 3)
    n_critical = sum(1 for r in ok if r["score"] < 30)
    n_risky = sum(1 for r in ok if 30 <= r["score"] < 50)
    n_caution = sum(1 for r in ok if 50 <= r["score"] < 70)
    n_good = sum(1 for r in ok if r["score"] >= 70)
    n_fails = sum(1 for r in ok if r["compliance_fails"] > 0)
    top3 = sorted(ok, key=lambda r: r["score"], reverse=True)[:3]
    bottom3 = sorted(ok, key=lambda r: r["score"])[:3]
    summary = f"""**Portfolio Summary** ({n} suppliers) [Source: DS-Fusion pipeline]

Score Distribution:
• Critical (<30):  {n_critical} suppliers
• Risky (30–50):   {n_risky} suppliers
• Caution (50–70): {n_caution} suppliers
• Good (70+):      {n_good} suppliers

Averages:
• Mean score: {avg_score}/100
• Mean belief_safe: {avg_safe} | belief_risky: {avg_risky} | uncertainty: {avg_unc}
• Compliance failures: {n_fails}/{n} suppliers have ≥1 fail

Top 3 safest:
{chr(10).join(_fmt_supplier_row(r, i+1) for i, r in enumerate(top3))}

Bottom 3 riskiest:
{chr(10).join(_fmt_supplier_row(r, i+1) for i, r in enumerate(bottom3))}"""
    return summary


def rank_suppliers(by: str = "score", ascending: bool = True, limit: int = 10) -> str:
    """Rank suppliers by score, compliance_fails, or article_count."""
    scores = _all_supplier_scores()
    ok = [r for r in scores if "error" not in r and by in r]
    ok.sort(key=lambda r: r[by], reverse=not ascending)
    ok = ok[:limit]
    field_label = {"score": "Score", "compliance_fails": "Compliance Fails", "article_count": "News Articles"}.get(by, by)
    direction = "lowest" if ascending else "highest"
    lines = [f"**Top {len(ok)} suppliers by {field_label} ({direction} first)** [Source: DS-Fusion pipeline]\n"]
    for i, r in enumerate(ok, 1):
        lines.append(_fmt_supplier_row(r, rank=i))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core supplier tools
# ---------------------------------------------------------------------------

def get_supplier_by_name(name: str) -> Supplier | None:
    """Find a supplier in the directory by name (fuzzy)."""
    name_low = name.lower()
    for s in load_suppliers():
        if name_low in s.name.lower() or any(name_low in a.lower() for a in s.aliases):
            return s
    return None


def analyze_supplier(supplier: Supplier, news_articles: list[dict[str, Any]] | None = None, use_defense: bool = True) -> dict[str, Any]:
    """Run full compliance + risk analysis for a supplier."""
    comp = run_comp(supplier)

    if news_articles:
        articles = []
        for i, a in enumerate(news_articles):
            articles.append(NewsArticle(
                id=f"agent-pasted-{i}",
                supplier_id=supplier.id,
                title=a.get("title", "News Update"),
                body=a["body"],
                url=a.get("url"),
                published_at=datetime.now(timezone.utc),
            ))
        signals = [extract_signal(supplier.name, art) for art in articles]
        signals = _annotate_corroboration(signals)
        risk = RiskProfile(supplier_id=supplier.id, signals=signals, article_count=len(articles))
    else:
        risk = run_risk_pipeline(supplier)

    score = fuse(supplier.id, comp, risk, use_defense=use_defense)
    return {"supplier": supplier, "compliance": comp, "risk": risk, "score": score}


def analyze_supplier_summary(supplier_name: str, news_body: str | None = None) -> str:
    """Full analysis returning a human-readable summary with DS belief breakdown and citations."""
    sup = get_supplier_by_name(supplier_name)
    if not sup:
        return f"Supplier '{supplier_name}' not found in the directory."

    news = [{"body": news_body}] if news_body else None
    res = analyze_supplier(sup, news_articles=news)
    sc = res["score"]
    comp = res["compliance"]
    risk = res["risk"]

    fail_details = "\n".join(
        f"  • [{c.source}] {c.status.upper()}: {c.detail or 'no detail'} [Source: {c.source}]"
        for c in comp.checks if c.status == "fail"
    ) or "  None"

    top_signals = sorted(risk.signals, key=lambda s: s.severity, reverse=True)[:3]
    signal_lines = "\n".join(
        f"  • {s.event_type.value.title()} (severity={s.severity}/5, sentiment={s.sentiment:+.2f}, "
        f"corroborated={'yes' if s.is_corroborated else 'no'}) [Source: {s.provenance.source_name}]"
        for s in top_signals
    ) or "  No risk signals found."

    top_contribs = sc.contributions[:5]
    contrib_lines = "\n".join(
        f"  • {c.feature}: {c.contribution:+.1f}pts (weight={c.weight:.2f})"
        for c in top_contribs
    )

    return f"""**Analysis: {sup.name}** ({sup.country}, {sup.category.value}) [Source: DS-Fusion pipeline]

Score: **{sc.score:.1f}/100** — Grade: **{sc.grade}**
DS Belief Masses: m_safe={sc.belief_safe:.3f} | m_risky={sc.belief_risky:.3f} | uncertainty={sc.uncertainty:.3f}

Compliance Checks ({comp.pass_count} pass, {comp.fail_count} fail):
{fail_details}

Top Risk Signals ({risk.article_count} articles):
{signal_lines}

Top Score Drivers:
{contrib_lines}"""


# ---------------------------------------------------------------------------
# Onboarding tool
# ---------------------------------------------------------------------------

def onboard_supplier(
    name: str,
    country: str,
    category: str,
    cin: str | None = None,
    website: str | None = None,
    news_text: str | None = None,
) -> str:
    """Create a transient supplier record and run full compliance + risk pipeline on it."""
    try:
        cat = SupplierCategory(category.lower().replace(" ", "_"))
    except ValueError:
        cat = SupplierCategory.OEM

    sup = Supplier(
        id=f"onboard-{name.lower().replace(' ', '-')}",
        name=name,
        legal_name=name,
        country=country.upper(),
        category=cat,
        cin=cin,
        website=website,
        is_illustrative=True,
        note="Transient onboarding record — not persisted to directory.",
    )

    news = [{"title": "Submitted news", "body": news_text}] if news_text else None
    res = analyze_supplier(sup, news_articles=news)
    sc = res["score"]
    comp = res["compliance"]

    verdict = "RECOMMEND APPROVE" if sc.score >= 60 else ("REVIEW REQUIRED" if sc.score >= 40 else "RECOMMEND REJECT")
    fail_lines = "\n".join(
        f"  • [{c.source}] {c.status.upper()}: {c.detail or ''}"
        for c in comp.checks if c.status == "fail"
    ) or "  None"

    return f"""**Onboarding Assessment: {name}** [Source: DS-Fusion pipeline]

Country: {country.upper()} | Category: {cat.value} | CIN: {cin or 'not provided'}
Score: **{sc.score:.1f}/100** — Grade: **{sc.grade}** — Verdict: **{verdict}**
DS Belief: m_safe={sc.belief_safe:.3f} | m_risky={sc.belief_risky:.3f} | uncertainty={sc.uncertainty:.3f}

Compliance Failures:
{fail_lines}

Note: This is a transient assessment. Persist to directory after human review."""


# ---------------------------------------------------------------------------
# Adversarial tool
# ---------------------------------------------------------------------------

def find_cheapest_attack(supplier_id: str, vector: str = "press_release", target_score: float = 60.0) -> str:
    """Find minimum budget to push a supplier score above target via adversarial injection."""
    suppliers = {s.id: s for s in load_suppliers()}
    s = suppliers.get(supplier_id)
    if not s:
        # Try fuzzy name match
        sup = get_supplier_by_name(supplier_id)
        if sup:
            s = sup
        else:
            return f"Supplier '{supplier_id}' not found. [Source: adversarial runner]"

    comp = run_comp(s)
    baseline = fuse(s.id, comp, run_risk_pipeline(s), use_defense=True)

    for B in range(1, 21):
        risk_attacked, _ = run_attacked(s, AttackConfig(budget=B, vector=vector))
        sc = fuse(s.id, comp, risk_attacked, use_defense=False).score
        if sc >= target_score:
            return (
                f"**Attack found** on {s.name} [Source: adversarial runner]\n"
                f"Baseline score: {baseline.score:.1f} → Attacked score: {sc:.1f}\n"
                f"Budget needed: **{B} unit(s)** via vector '{vector}'\n"
                f"Defense (use_defense=True) would neutralise this attack."
            )

    return (
        f"**Attack failed** — {s.name} could not be pushed above {target_score} "
        f"with up to 20 budget units via '{vector}'. [Source: adversarial runner]"
    )
