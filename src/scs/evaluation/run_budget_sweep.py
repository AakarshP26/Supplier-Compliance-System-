"""Sweep attack budget B and attack vector to produce the paper's Figure 2.

For each (vector, B) cell we run the full pipeline and record:
  * clean F1 (constant)
  * attacked F1
  * defended F1
  * flip rate clean→attacked
  * flip rate clean→defended

Output is a CSV at data/results/budget_sweep.csv that the paper uses
to plot 'attack effectiveness vs defense recovery as a function of B'.

Run:
    python -m scs.evaluation.run_budget_sweep
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scs.adversarial.attack import AttackConfig
from scs.evaluation.ground_truth import load_labels
from scs.evaluation.metrics import (
    adversarial_metrics,
    classification_metrics,
)
from scs.evaluation.run_experiment import score_all


VECTORS = ["press_release", "anon_blog"]
BUDGETS = [0, 1, 2, 3, 5, 7, 10, 15, 20]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/results/budget_sweep.csv"),
    )
    args = parser.parse_args()

    labels = load_labels()
    clean = score_all(use_defense=False)
    clean_metrics = classification_metrics(clean, labels)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "vector", "budget",
            "clean_f1",
            "attacked_acc", "attacked_f1", "attacked_flip", "attacked_lift",
            "defended_acc", "defended_f1", "defended_flip", "defended_lift",
        ])

        # B=0 row (no attack)
        for vector in VECTORS:
            writer.writerow([
                vector, 0,
                f"{clean_metrics.f1:.3f}",
                f"{clean_metrics.accuracy:.3f}", f"{clean_metrics.f1:.3f}", "0.000", "0.000",
                f"{clean_metrics.accuracy:.3f}", f"{clean_metrics.f1:.3f}", "0.000", "0.000",
            ])

        for vector in VECTORS:
            for B in BUDGETS:
                if B == 0:
                    continue  # already emitted above
                cfg = AttackConfig(budget=B, vector=vector)
                attacked = score_all(use_defense=False, attack_cfg=cfg)
                defended = score_all(use_defense=True, attack_cfg=cfg)

                a_cls = classification_metrics(attacked, labels)
                d_cls = classification_metrics(defended, labels)
                a_adv = adversarial_metrics(clean, attacked)
                d_adv = adversarial_metrics(clean, defended)

                writer.writerow([
                    vector, B,
                    f"{clean_metrics.f1:.3f}",
                    f"{a_cls.accuracy:.3f}", f"{a_cls.f1:.3f}",
                    f"{a_adv.flip_rate:.3f}", f"{a_adv.mean_score_lift:.2f}",
                    f"{d_cls.accuracy:.3f}", f"{d_cls.f1:.3f}",
                    f"{d_adv.flip_rate:.3f}", f"{d_adv.mean_score_lift:.2f}",
                ])
                print(f"  {vector:<14s} B={B:>2d}  attacked F1={a_cls.f1:.2f}  defended F1={d_cls.f1:.2f}")

    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
