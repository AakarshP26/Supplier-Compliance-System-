"""Risk sensing pipeline.

For one supplier:
  1. Pull every article in the corpus for that supplier id.
  2. Extract a structured RiskSignal from each (LLM or mock).
  3. Compute corroboration: a signal is corroborated if at least one other
     signal of the same event_type came from a *different* source domain.
  4. Return a RiskProfile.

Corroboration is the seed of the trust-calibrated defense. A single
high-severity signal from one low-credibility source is suspicious;
the same signal echoed by an independent tier-1 outlet is much harder
to fake. The fusion layer reads the `is_corroborated` flag.
"""
from __future__ import annotations

from urllib.parse import urlparse

from scs.models import RiskProfile, RiskSignal, Supplier
from scs.risk import news
from scs.risk.extractor import extract_signal


def _domain_of(signal: RiskSignal) -> str:
    url = signal.provenance.source_url
    if not url:
        return signal.provenance.source_name.lower()
    host = urlparse(url).netloc
    return host.removeprefix("www.").lower()


def _registrable_domain(host: str) -> str:
    """Collapse subdomains for corroboration: markets.ft.com -> ft.com."""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def _annotate_corroboration(signals: list[RiskSignal]) -> list[RiskSignal]:
    """Mark each signal corroborated iff another signal of the same type
    from a different *registrable* domain exists."""
    by_type: dict[str, set[str]] = {}
    for s in signals:
        domain = _registrable_domain(_domain_of(s))
        by_type.setdefault(s.event_type.value, set()).add(domain)

    out: list[RiskSignal] = []
    for s in signals:
        domain = _registrable_domain(_domain_of(s))
        independent_domains = by_type[s.event_type.value] - {domain}
        out.append(s.model_copy(update={"is_corroborated": bool(independent_domains)}))
    return out


def run(supplier: Supplier) -> RiskProfile:
    articles = news.articles_for(supplier.id)
    signals = [extract_signal(supplier.name, art) for art in articles]
    signals = _annotate_corroboration(signals)
    return RiskProfile(
        supplier_id=supplier.id,
        signals=signals,
        article_count=len(articles),
    )


def run_all(suppliers: list[Supplier]) -> dict[str, RiskProfile]:
    return {s.id: run(s) for s in suppliers}
