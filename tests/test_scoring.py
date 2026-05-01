"""Tests for Dempster-Shafer fusion + the adversarial harness.

Includes the canonical regression: a debarred supplier under a 20-budget
press-release attack must score below the risky/safe threshold once the
defense is enabled. If this ever fails, something has regressed in the
defense.
"""
from __future__ import annotations

import pytest

from scs.adversarial.attack import AttackConfig, craft_attack
from scs.adversarial.runner import run_attacked
from scs.compliance.pipeline import run as run_comp
from scs.data import get_supplier
from scs.evaluation.metrics import RISK_THRESHOLD
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import BPA, combine_yager, combine_many, fuse


# ---------------------------------------------------------------------------
# DS algebra
# ---------------------------------------------------------------------------


class TestBPA:
    def test_valid_bpa_constructs(self):
        b = BPA(safe=0.3, risky=0.4, theta=0.3)
        assert b.safe == pytest.approx(0.3)

    def test_invalid_sum_raises(self):
        with pytest.raises(ValueError):
            BPA(safe=0.5, risky=0.5, theta=0.3)

    def test_combine_unit_theta_is_identity(self):
        a = BPA(safe=0.6, risky=0.1, theta=0.3, label="a")
        unit = BPA(safe=0.0, risky=0.0, theta=1.0, label="∅")
        c = combine_yager(a, unit)
        assert c.safe == pytest.approx(a.safe)
        assert c.risky == pytest.approx(a.risky)
        assert c.theta == pytest.approx(a.theta)

    def test_combine_two_safes_strengthens_safe(self):
        a = BPA(safe=0.5, risky=0.0, theta=0.5)
        b = BPA(safe=0.5, risky=0.0, theta=0.5)
        c = combine_yager(a, b)
        assert c.safe > a.safe
        assert c.risky == 0.0

    def test_conflict_routed_to_theta(self):
        # Yager's modification: conflict goes to uncertainty, not normalised
        a = BPA(safe=0.8, risky=0.0, theta=0.2)
        b = BPA(safe=0.0, risky=0.8, theta=0.2)
        c = combine_yager(a, b)
        # Both singletons should have small mass; uncertainty large
        assert c.theta > c.safe
        assert c.theta > c.risky


# ---------------------------------------------------------------------------
# End-to-end fusion
# ---------------------------------------------------------------------------


class TestFusion:
    def test_clean_supplier_scores_high(self):
        s = get_supplier("dixon-tech")
        score = fuse(s.id, run_comp(s), run_risk(s))
        assert score.score >= 80.0
        assert score.grade in {"A", "B"}

    def test_sanctioned_supplier_scores_low(self):
        s = get_supplier("dnipro-microelectronics")
        score = fuse(s.id, run_comp(s), run_risk(s))
        assert score.score < RISK_THRESHOLD

    def test_debarred_supplier_scores_low(self):
        s = get_supplier("shenzhen-shadow-corp")
        score = fuse(s.id, run_comp(s), run_risk(s))
        assert score.score < RISK_THRESHOLD

    def test_belief_masses_sum_to_one(self):
        s = get_supplier("dixon-tech")
        score = fuse(s.id, run_comp(s), run_risk(s))
        total = score.belief_safe + score.belief_risky + score.uncertainty
        assert total == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Adversarial regression
# ---------------------------------------------------------------------------


class TestAdversarial:
    def test_attack_articles_are_synthetic(self):
        s = get_supplier("dixon-tech")
        result = craft_attack(s.name, s.id, AttackConfig(budget=4))
        assert len(result.injected) == 4
        assert all(a.is_synthetic for a in result.injected)

    def test_attack_lifts_score(self):
        s = get_supplier("shenzhen-shadow-corp")
        comp = run_comp(s)
        clean_score = fuse(s.id, comp, run_risk(s)).score
        risk_attacked, _ = run_attacked(s, AttackConfig(budget=20, vector="press_release"))
        attacked_score = fuse(s.id, comp, risk_attacked, use_defense=False).score
        # Attack should successfully raise the score.
        assert attacked_score > clean_score + 30.0

    def test_defense_blocks_attack_lift(self):
        # Canonical regression for the paper's main result.
        s = get_supplier("shenzhen-shadow-corp")
        comp = run_comp(s)
        clean = fuse(s.id, comp, run_risk(s)).score
        risk_attacked, _ = run_attacked(s, AttackConfig(budget=20, vector="press_release"))
        defended = fuse(s.id, comp, risk_attacked, use_defense=True).score
        # Defense must keep the supplier classified risky (score < threshold).
        assert defended < RISK_THRESHOLD
        # And undo most of the attack's lift.
        attacker_lift_undone = (
            fuse(s.id, comp, risk_attacked, use_defense=False).score - defended
        )
        assert attacker_lift_undone > 30.0

    def test_defense_does_not_hurt_clean(self):
        # A regression fence: defense must not move clean scores
        # appreciably (no attack present -> no burst -> no penalty).
        s = get_supplier("dixon-tech")
        comp = run_comp(s)
        risk = run_risk(s)
        no_def = fuse(s.id, comp, risk, use_defense=False).score
        defended = fuse(s.id, comp, risk, use_defense=True).score
        assert abs(no_def - defended) < 5.0
