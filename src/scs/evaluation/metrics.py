"""Metrics for the paper's evaluation tables.

We frame supplier-risk as a binary problem (risky vs safe) at score
threshold 50 — below = risky, above = safe. The metrics report:

  * Accuracy / precision / recall / F1 against ground-truth labels.
  * Flip rate: fraction of suppliers whose binary classification flipped
    from clean to attacked (or attacked to defended).
  * Average score delta (attacker's "lift" — what they gain in absolute
    score points by attacking).
  * Expected Calibration Error (ECE): are the model's belief masses
    well-calibrated against ground truth?
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from scs.models import SupplierScore


RISK_THRESHOLD = 50.0  # below = predicted risky


# ---------------------------------------------------------------------------
# Binary classification
# ---------------------------------------------------------------------------


def predicted_risky(score: SupplierScore, threshold: float = RISK_THRESHOLD) -> bool:
    return score.score < threshold


@dataclass
class ClassificationMetrics:
    n: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    tn: int
    fn: int


def classification_metrics(
    scores: dict[str, SupplierScore],
    ground_truth: dict[str, bool],
    threshold: float = RISK_THRESHOLD,
) -> ClassificationMetrics:
    """Compute precision / recall / F1 with risky=True as the positive class."""
    tp = fp = tn = fn = 0
    for sid, gt_risky in ground_truth.items():
        if sid not in scores:
            continue
        pred_risky = predicted_risky(scores[sid], threshold)
        if pred_risky and gt_risky:
            tp += 1
        elif pred_risky and not gt_risky:
            fp += 1
        elif not pred_risky and gt_risky:
            fn += 1
        else:
            tn += 1

    n = tp + fp + tn + fn
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return ClassificationMetrics(
        n=n, accuracy=accuracy, precision=precision, recall=recall, f1=f1,
        tp=tp, fp=fp, tn=tn, fn=fn,
    )


# ---------------------------------------------------------------------------
# Adversarial-specific
# ---------------------------------------------------------------------------


@dataclass
class AdversarialMetrics:
    n: int
    flip_rate: float          # fraction of suppliers whose risky/safe label flipped
    mean_score_lift: float    # mean (attacked - clean) score delta
    max_score_lift: float
    mean_abs_belief_shift: float


def adversarial_metrics(
    clean: dict[str, SupplierScore],
    perturbed: dict[str, SupplierScore],
    threshold: float = RISK_THRESHOLD,
) -> AdversarialMetrics:
    """How much did `perturbed` move scores away from `clean`?"""
    flips = 0
    lifts: list[float] = []
    belief_shifts: list[float] = []
    n = 0
    for sid, c in clean.items():
        if sid not in perturbed:
            continue
        n += 1
        p = perturbed[sid]
        lifts.append(p.score - c.score)
        belief_shifts.append(abs(p.belief_safe - c.belief_safe))
        if predicted_risky(c, threshold) != predicted_risky(p, threshold):
            flips += 1

    return AdversarialMetrics(
        n=n,
        flip_rate=flips / n if n else 0.0,
        mean_score_lift=sum(lifts) / n if n else 0.0,
        max_score_lift=max(lifts) if lifts else 0.0,
        mean_abs_belief_shift=sum(belief_shifts) / n if n else 0.0,
    )


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def expected_calibration_error(
    scores: Iterable[SupplierScore],
    ground_truth: dict[str, bool],
    n_bins: int = 10,
) -> float:
    """ECE on belief_safe vs the (binary) safe label.

    Standard reliability-diagram ECE: bin predictions by belief_safe and
    compare bin-mean confidence to bin-mean accuracy.
    """
    items = [(s, ground_truth[s.supplier_id]) for s in scores if s.supplier_id in ground_truth]
    if not items:
        return 0.0

    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for s, gt_risky in items:
        gt_safe = not gt_risky
        idx = min(int(s.belief_safe * n_bins), n_bins - 1)
        bins[idx].append((s.belief_safe, gt_safe))

    total = len(items)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        conf = sum(c for c, _ in bucket) / len(bucket)
        acc = sum(1 for _, t in bucket if t) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - conf)
    return ece
