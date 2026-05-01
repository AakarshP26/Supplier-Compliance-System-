"""Tests for the compliance module.

These act both as regression tests and as the "expected behaviour" spec
for the paper's reproducibility statement.
"""
from __future__ import annotations

import pytest

from scs.compliance import bis_crs, ofac, pipeline, world_bank
from scs.data import get_supplier


def _supplier(sid: str):
    s = get_supplier(sid)
    assert s is not None, f"seed supplier {sid!r} missing"
    return s


# ---------------------------------------------------------------------------
# OFAC
# ---------------------------------------------------------------------------


class TestOFAC:
    def test_clean_supplier_passes(self):
        c = ofac.check(_supplier("dixon-tech"))
        assert c.status == "pass"
        assert c.provenance.credibility == pytest.approx(0.95)

    def test_known_sanctioned_entity_fails(self):
        c = ofac.check(_supplier("dnipro-microelectronics"))
        assert c.status == "fail"
        assert "RUSSIA-EO14024" in c.detail

    def test_alias_match_fails(self):
        # 'shell-electronics-bvi' is seeded with name 'Apex Global Sourcing'
        # which appears in the OFAC sample list.
        c = ofac.check(_supplier("shell-electronics-bvi"))
        assert c.status == "fail"


# ---------------------------------------------------------------------------
# World Bank
# ---------------------------------------------------------------------------


class TestWorldBank:
    def test_clean_supplier_passes(self):
        c = world_bank.check(_supplier("dixon-tech"))
        assert c.status == "pass"

    def test_currently_debarred_fails(self):
        c = world_bank.check(_supplier("shenzhen-shadow-corp"))
        assert c.status == "fail"
        assert "debarred" in c.detail.lower()


# ---------------------------------------------------------------------------
# BIS CRS
# ---------------------------------------------------------------------------


class TestBISCRS:
    def test_registered_indian_supplier_passes(self):
        c = bis_crs.check(_supplier("dixon-tech"))
        assert c.status == "pass"
        assert "R-" in c.detail  # registration number quoted

    def test_unregistered_indian_supplier_fails(self):
        c = bis_crs.check(_supplier("sahasra-electronics"))
        assert c.status == "fail"

    def test_unregistered_foreign_supplier_unknown(self):
        c = bis_crs.check(_supplier("dnipro-microelectronics"))
        assert c.status == "unknown"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_runs_all_checks(self):
        report = pipeline.run(_supplier("dixon-tech"))
        sources = {c.source for c in report.checks}
        assert sources == {"OFAC SDN", "World Bank Debarred", "BIS CRS"}

    def test_clean_supplier_is_clean(self):
        assert pipeline.run(_supplier("dixon-tech")).is_clean

    def test_failing_supplier_is_not_clean(self):
        report = pipeline.run(_supplier("shell-electronics-bvi"))
        assert not report.is_clean
        assert report.fail_count >= 2  # OFAC + WB at minimum

    def test_every_check_has_credibility(self):
        report = pipeline.run(_supplier("dixon-tech"))
        for c in report.checks:
            assert 0.0 <= c.provenance.credibility <= 1.0
