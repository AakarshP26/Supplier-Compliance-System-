"""Streamlit dashboard for the demo.

Run from the repo root with:

    streamlit run src/scs/dashboard/app.py

Pages:
  * Single supplier — full report card with score breakdown.
  * Compare two — side-by-side cards.
  * Adversarial demo — pick a supplier, sweep an attack, watch the
    score climb under attack and stay flat under the defense.
"""
from __future__ import annotations

import sys
from pathlib import Path

# When run directly via `streamlit run src/scs/dashboard/app.py`, the
# package isn't on sys.path. Insert the repo's `src` so imports work
# whether the user installs the package or just clones the repo.
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from scs.adversarial.attack import AttackConfig  # noqa: E402
from scs.adversarial.runner import run_attacked  # noqa: E402
from scs.compliance.pipeline import run as run_comp  # noqa: E402
from scs.data import load_suppliers  # noqa: E402
from scs.risk.pipeline import run as run_risk  # noqa: E402
from scs.scoring.fusion import fuse  # noqa: E402
from scs.service import assess  # noqa: E402


st.set_page_config(
    page_title="Supplier Compliance — Trust-Calibrated Scoring",
    page_icon="🛡️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@st.cache_data
def all_suppliers():
    return list(load_suppliers())


SUPPLIERS = all_suppliers()
SUPPLIER_BY_NAME = {s.name: s for s in SUPPLIERS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _score_color(score: float) -> str:
    if score >= 80:
        return "#1d9e75"  # teal
    if score >= 65:
        return "#639922"  # green
    if score >= 50:
        return "#ba7517"  # amber
    if score >= 35:
        return "#d85a30"  # coral
    return "#a32d2d"  # red


def render_score_card(report) -> None:
    score = report.score
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Score", f"{score.score:.1f} / 100")
    col2.metric("Grade", score.grade)
    col3.metric("Belief safe", f"{score.belief_safe:.2f}")
    col4.metric("Belief risky", f"{score.belief_risky:.2f}")
    st.progress(score.score / 100.0)


def render_compliance(report) -> None:
    rows = []
    for c in report.compliance.checks:
        rows.append(
            {
                "Source": c.source,
                "Status": c.status.upper(),
                "Credibility": f"{c.provenance.credibility:.2f}",
                "Detail": c.detail,
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_risk_signals(report) -> None:
    if not report.risk.signals:
        st.info("No news articles in the corpus for this supplier.")
        return
    rows = []
    for sig in report.risk.signals:
        rows.append(
            {
                "Event": sig.event_type.value,
                "Severity": sig.severity,
                "Sentiment": f"{sig.sentiment:+.2f}",
                "Source": sig.provenance.source_name,
                "Credibility": f"{sig.credibility:.2f}",
                "Corroborated": "✓" if sig.is_corroborated else "—",
                "Summary": sig.summary,
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render_contributions(report) -> None:
    rows = []
    for c in report.score.contributions:
        rows.append(
            {
                "Feature": c.feature,
                "Raw value": f"{c.raw_value:+.2f}",
                "Effective weight": f"{c.weight:.2f}",
                "Contribution": f"{c.contribution:+.1f}",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def page_single() -> None:
    st.title("Single supplier report")

    name = st.selectbox(
        "Supplier",
        options=[s.name for s in SUPPLIERS],
        index=0,
    )
    use_defense = st.toggle("Use trust-calibrated defense", value=True)

    supplier = SUPPLIER_BY_NAME[name]
    report = assess(supplier, use_defense=use_defense)

    st.subheader(f"{supplier.name}")
    st.caption(
        f"{supplier.legal_name or supplier.name} · "
        f"{supplier.country} · {supplier.category.value.replace('_', ' ')}"
    )

    render_score_card(report)

    tab_comp, tab_risk, tab_contrib = st.tabs(
        ["Compliance checks", "Risk signals", "Score breakdown"]
    )
    with tab_comp:
        render_compliance(report)
    with tab_risk:
        render_risk_signals(report)
    with tab_contrib:
        render_contributions(report)


def page_compare() -> None:
    st.title("Compare two suppliers")
    col_a, col_b = st.columns(2)
    with col_a:
        name_a = st.selectbox(
            "A", options=[s.name for s in SUPPLIERS], key="cmp_a", index=0,
        )
    with col_b:
        name_b = st.selectbox(
            "B", options=[s.name for s in SUPPLIERS], key="cmp_b",
            index=min(1, len(SUPPLIERS) - 1),
        )

    rep_a = assess(SUPPLIER_BY_NAME[name_a])
    rep_b = assess(SUPPLIER_BY_NAME[name_b])

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader(name_a)
        render_score_card(rep_a)
        st.markdown("**Top contributions**")
        render_contributions(rep_a)
    with col_b:
        st.subheader(name_b)
        render_score_card(rep_b)
        st.markdown("**Top contributions**")
        render_contributions(rep_b)


def page_adversarial() -> None:
    st.title("Adversarial demo: evidence-source poisoning")
    st.markdown(
        "Pick a supplier and watch their score change as an adversary plants "
        "synthetic positive articles. Toggle the defense to see the difference."
    )

    name = st.selectbox(
        "Supplier",
        options=[s.name for s in SUPPLIERS],
        key="adv",
        # Default to a known-bad supplier so the demo lands hard
        index=next(
            (i for i, s in enumerate(SUPPLIERS) if s.id == "shenzhen-shadow-corp"),
            0,
        ),
    )
    vector = st.radio(
        "Attack vector",
        options=["press_release", "anon_blog", "self_published"],
        horizontal=True,
    )
    max_budget = st.slider("Maximum attack budget", min_value=1, max_value=20, value=12)

    supplier = SUPPLIER_BY_NAME[name]
    comp_report = run_comp(supplier)

    rows = []
    for B in range(0, max_budget + 1):
        if B == 0:
            risk_no_def = run_risk(supplier)
            risk_def = risk_no_def
        else:
            risk_no_def, _ = run_attacked(supplier, AttackConfig(budget=B, vector=vector))
            risk_def = risk_no_def  # same evidence; the difference is in fusion

        score_no_def = fuse(supplier.id, comp_report, risk_no_def, use_defense=False).score
        score_def = fuse(supplier.id, comp_report, risk_def, use_defense=True).score
        rows.append(
            {"budget": B, "no_defense": score_no_def, "with_defense": score_def}
        )

    df = pd.DataFrame(rows).set_index("budget")
    st.line_chart(df)

    st.markdown(
        "**Reading guide.** A flat horizontal `with_defense` line that "
        "stays close to the true (B=0) score means the defense is holding. "
        "A `no_defense` line that climbs steeply with budget shows the "
        "underlying vulnerability."
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


PAGES = {
    "Single supplier": page_single,
    "Compare two": page_compare,
    "Adversarial demo": page_adversarial,
}

choice = st.sidebar.radio("Page", list(PAGES.keys()))
st.sidebar.markdown("---")
st.sidebar.caption(
    "Trust-calibrated scoring · "
    f"{len(SUPPLIERS)} seed suppliers loaded"
)
PAGES[choice]()
