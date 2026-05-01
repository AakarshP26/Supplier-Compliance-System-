"""Headline experiment: clean → attacked → defended.

Produces the paper's main table:

  | Condition          | Accuracy | F1   | Flip rate | Mean lift | ECE  |
  | clean              |   ...    | ...  |    -      |    -      | ...  |
  | attacked, no def.  |   ...    | ...  |   ...     |   ...     | ...  |
  | attacked + defense |   ...    | ...  |   ...     |   ...     | ...  |

Run as:
    python -m scs.evaluation.run_experiment              # default attack
    python -m scs.evaluation.run_experiment --budget 10  # sweep budget
    python -m scs.evaluation.run_experiment --vector anon_blog
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from scs.adversarial.attack import AttackConfig
from scs.adversarial.runner import run_attacked
from scs.compliance.pipeline import run as run_comp
from scs.data import load_suppliers
from scs.evaluation.ground_truth import load_labels
from scs.evaluation.metrics import (
    adversarial_metrics,
    classification_metrics,
    expected_calibration_error,
)
from scs.models import SupplierScore
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse


def score_all(use_defense: bool, attack_cfg: AttackConfig | None = None) -> dict[str, SupplierScore]:
    """Score every seed supplier under a given condition."""
    out: dict[str, SupplierScore] = {}
    for supplier in load_suppliers():
        comp = run_comp(supplier)
        if attack_cfg is None:
            risk = run_risk(supplier)
        else:
            risk, _ = run_attacked(supplier, attack_cfg)
        out[supplier.id] = fuse(supplier.id, comp, risk, use_defense=use_defense)
    return out


def run_experiment(attack_cfg: AttackConfig) -> dict:
    """Run all three conditions and return a structured result dict."""
    labels = load_labels()

    clean = score_all(use_defense=False)
    attacked = score_all(use_defense=False, attack_cfg=attack_cfg)
    defended = score_all(use_defense=True, attack_cfg=attack_cfg)

    return {
        "config": asdict(attack_cfg),
        "metrics": {
            "clean": {
                "classification": asdict(classification_metrics(clean, labels)),
                "ece": expected_calibration_error(clean.values(), labels),
            },
            "attacked": {
                "classification": asdict(classification_metrics(attacked, labels)),
                "vs_clean": asdict(adversarial_metrics(clean, attacked)),
                "ece": expected_calibration_error(attacked.values(), labels),
            },
            "defended": {
                "classification": asdict(classification_metrics(defended, labels)),
                "vs_clean": asdict(adversarial_metrics(clean, defended)),
                "ece": expected_calibration_error(defended.values(), labels),
            },
        },
        "per_supplier_scores": {
            sid: {
                "clean": clean[sid].score,
                "attacked": attacked[sid].score,
                "defended": defended[sid].score,
                "ground_truth_risky": labels.get(sid),
            }
            for sid in clean
        },
    }


def _fmt(x: float, w: int = 6, p: int = 3) -> str:
    return f"{x:>{w}.{p}f}"


def print_table(result: dict) -> None:
    cfg = result["config"]
    print(f"\nAttack config: budget={cfg['budget']} vector={cfg['vector']}\n")
    headers = ["condition", "n", "acc", "P", "R", "F1", "flip", "lift", "ECE"]
    print("  ".join(f"{h:>10s}" for h in headers))
    print("  ".join("-" * 10 for _ in headers))

    for name in ("clean", "attacked", "defended"):
        m = result["metrics"][name]
        c = m["classification"]
        adv = m.get("vs_clean")
        flip = adv["flip_rate"] if adv else 0.0
        lift = adv["mean_score_lift"] if adv else 0.0
        row = [
            name,
            str(c["n"]),
            _fmt(c["accuracy"]),
            _fmt(c["precision"]),
            _fmt(c["recall"]),
            _fmt(c["f1"]),
            _fmt(flip),
            _fmt(lift),
            _fmt(m["ece"]),
        ]
        print("  ".join(f"{v:>10s}" for v in row))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--vector", default="press_release",
                        choices=["press_release", "anon_blog", "self_published"])
    parser.add_argument("--out", type=Path, default=None,
                        help="Optional path to dump result JSON.")
    args = parser.parse_args()

    cfg = AttackConfig(budget=args.budget, vector=args.vector)
    result = run_experiment(cfg)
    print_table(result)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, default=str))
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
