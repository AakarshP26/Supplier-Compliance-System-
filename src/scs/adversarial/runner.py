"""Run the full pipeline under attack.

Provides `run_attacked` mirroring `risk.pipeline.run` but injecting
adversarial articles into the corpus before extraction.
"""
from __future__ import annotations

from scs.adversarial.attack import AttackConfig, craft_attack
from scs.models import RiskProfile, Supplier
from scs.risk import news as news_mod
from scs.risk.extractor import extract_signal
from scs.risk.pipeline import _annotate_corroboration


def run_attacked(supplier: Supplier, config: AttackConfig) -> tuple[RiskProfile, int]:
    """Run risk pipeline with synthetic articles injected.

    Returns the resulting RiskProfile and the number of injected articles
    (so callers can report attack effectiveness without re-deriving it).
    """
    real_articles = news_mod.articles_for(supplier.id)
    attack = craft_attack(supplier.name, supplier.id, config)
    combined = real_articles + attack.injected

    signals = [extract_signal(supplier.name, art) for art in combined]
    signals = _annotate_corroboration(signals)
    return (
        RiskProfile(
            supplier_id=supplier.id,
            signals=signals,
            article_count=len(combined),
        ),
        len(attack.injected),
    )
