"""Stronger trust calibration: detect coordinated poisoning patterns.

The vanilla pipeline already discounts low-credibility uncorroborated
signals. But a coordinated attacker plants many articles across multiple
low-credibility domains in a short window — they ARE corroborated under
the simple cross-domain rule, just not credibly.

This module adds two cheap, model-free pattern detectors that the paper
proposes as the trust-calibrated defense:

  1. Temporal burst penalty
     If many positive signals about a supplier all land within a narrow
     window, downweight each by a burst factor < 1.

  2. Template / surface-form similarity penalty
     If two positive articles share a high Jaccard token overlap, treat
     them as "near-duplicates" — likely template-driven — and downweight.

Both are *defensive priors*: cheap, explainable, and the kind of thing a
procurement reviewer can audit. They don't require retraining the LLM.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timezone

from scs.models import RiskProfile, RiskSignal


_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _TOKEN_RE.findall(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Burst detector
# ---------------------------------------------------------------------------


def _burst_factor(
    signals: list[RiskSignal],
    window_days: float = 30.0,
    min_burst: int = 3,
) -> dict[int, float]:
    """For each positive signal, compute a burst-aware downweight in (0, 1].

    If N positive signals about this supplier are published within a
    window_days span, we downweight each by 1/log2(N+1). N below the
    threshold yields 1.0 (no penalty).
    """
    out: dict[int, float] = {}
    positive_idx = [
        (i, s.provenance.published_at)
        for i, s in enumerate(signals)
        if s.event_type.value == "positive" and s.provenance.published_at is not None
    ]

    for i, t_i in positive_idx:
        if t_i is None:
            out[i] = 1.0
            continue
        # Count positives within window_days of this one.
        nearby = sum(
            1
            for _, t_j in positive_idx
            if t_j is not None
            and abs((t_i - t_j).total_seconds()) <= window_days * 86400.0
        )
        if nearby >= min_burst:
            out[i] = 1.0 / math.log2(nearby + 1)
        else:
            out[i] = 1.0

    # Non-positive signals untouched
    for i, s in enumerate(signals):
        if i not in out:
            out[i] = 1.0
    return out


# ---------------------------------------------------------------------------
# Template-similarity detector
# ---------------------------------------------------------------------------


def _template_factor(
    signals: list[RiskSignal],
    similarity_threshold: float = 0.55,
) -> dict[int, float]:
    """Downweight signals that are near-duplicates of others (same supplier).

    For each positive signal, count how many other positive signals share
    Jaccard token overlap >= threshold. Penalty mirrors the burst penalty
    so the two combine multiplicatively.
    """
    out: dict[int, float] = {}
    positives = [
        (i, _tokens(s.summary))
        for i, s in enumerate(signals)
        if s.event_type.value == "positive"
    ]

    for i, toks_i in positives:
        sim_count = sum(
            1 for j, toks_j in positives if i != j and _jaccard(toks_i, toks_j) >= similarity_threshold
        )
        if sim_count >= 2:
            out[i] = 1.0 / math.log2(sim_count + 1.5)
        else:
            out[i] = 1.0

    for i in range(len(signals)):
        if i not in out:
            out[i] = 1.0
    return out


# ---------------------------------------------------------------------------
# Public API: combined defense
# ---------------------------------------------------------------------------


def calibrated_signal_weights(profile: RiskProfile) -> list[float]:
    """Return a list, same length as profile.signals, of multiplicative
    weights in (0, 1] capturing the combined defense."""
    bursts = _burst_factor(profile.signals)
    templates = _template_factor(profile.signals)
    return [
        bursts.get(i, 1.0) * templates.get(i, 1.0) for i in range(len(profile.signals))
    ]
