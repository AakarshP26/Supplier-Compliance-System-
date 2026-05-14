"""Load ground-truth risky/safe labels for offline evaluation.

The dashboard and live scorer never touch this file — it exists solely
for the evaluation harness to compute accuracy / ECE / flip rates.
"""
from __future__ import annotations

import json
from functools import lru_cache

from scs.config import CONFIG


@lru_cache(maxsize=1)
def load_labels() -> dict[str, bool]:
    path = CONFIG.data_dir / "ground_truth.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {sid: rec["risky"] for sid, rec in raw.get("labels", {}).items()}


def load_rationales() -> dict[str, str]:
    path = CONFIG.data_dir / "ground_truth.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {sid: rec.get("rationale", "") for sid, rec in raw.get("labels", {}).items()}
