"""Tests for the compliance module.

These act both as regression tests and as the "expected behaviour" spec
for the paper's reproducibility statement.
"""
from __future__ import annotations

import pytest

from scs.compliance import bis_crs, ofac, pipeline
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

    def test_illustrative_shell_entity_fails(self):
        # 'yelahanka-shadow-traders' is an illustrative Bangalore shell
        # designed to demonstrate OFAC fuzzy-match fail in a domestic context.
        c = ofac.check(_supplier("yelahanka-shadow-traders"))
        assert c.status == "fail"

    def test_alias_match_fails(self):
        # 'rajajinagar-evasion-shell' has alias "RJN Trading" matching the
        # OFAC sample list entry.
        c = ofac.check(_supplier("rajajinagar-evasion-shell"))
        assert c.status == "fail"


# ---------------------------------------------------------------------------
# BIS CRS
# ---------------------------------------------------------------------------


class TestBISCRS:
    def test_registered_indian_supplier_passes(self):
        c = bis_crs.check(_supplier("dixon-tech"))
        assert c.status == "pass"
        assert "R-" in c.detail  # registration number quoted

    def test_unregistered_indian_supplier_fails(self):
        # peenya-grey-market is an illustrative entity with no BIS
        # registration in our reference data.
        c = bis_crs.check(_supplier("peenya-grey-market"))
        assert c.status == "fail"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_runs_all_checks(self):
        report = pipeline.run(_supplier("dixon-tech"))
        sources = {c.source for c in report.checks}
        assert sources == {"OFAC SDN", "BIS CRS"}

    def test_clean_supplier_is_clean(self):
        assert pipeline.run(_supplier("dixon-tech")).is_clean

    def test_failing_supplier_is_not_clean(self):
        report = pipeline.run(_supplier("yelahanka-shadow-traders"))
        assert not report.is_clean
        assert report.fail_count >= 1  # OFAC fail at minimum

    def test_every_check_has_credibility(self):
        report = pipeline.run(_supplier("dixon-tech"))
        for c in report.checks:
            assert 0.0 <= c.provenance.credibility <= 1.0
