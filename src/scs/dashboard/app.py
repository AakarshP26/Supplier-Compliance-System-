"""Streamlit dashboard entrypoint.

Run with:
    streamlit run src/scs/dashboard/app.py
or via:
    make dashboard

Pages:
  • Overview        — portfolio view across all 86 suppliers
  • Find suppliers  — multi-criteria filter + shortlist with CSV export
  • Supplier        — rich single-supplier report (belief decomposition,
                      risk topology, news timeline, evidence sources,
                      score waterfall)
  • Compare         — up to 5 suppliers side-by-side (radar overlay,
                      parallel coordinates, metric matrix)
  • Onboard         — submit a new supplier with optional news, run a
                      session-only assessment
  • Adversarial lab — the paper's central experiment, made interactive
  • Methodology     — threat model, equations, defense, limitations
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st  # noqa: E402

from scs.dashboard import (  # noqa: E402
    page_overview, page_find, page_detail, page_compare,
    page_onboard, page_lab, page_method, page_parameters,
)
from scs.dashboard.styling import inject_css  # noqa: E402


st.set_page_config(
    page_title="Trust-Calibrated Supplier Compliance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
<div class="scs-brand">🛡️ Supplier Compliance</div>
<div class="scs-tag">Trust-calibrated scoring · v0.2</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    page = st.radio(
        "Navigate",
        options=[
            "Overview",
            "Find suppliers",
            "Supplier detail",
            "Parameters used",
            "Compare",
            "Onboard new supplier",
            "Adversarial lab",
            "Methodology",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("**Global controls**")

    use_defense = st.toggle(
        "Trust-calibrated defense",
        value=True,
        help=(
            "On: applies burst + template-similarity downweighting on top of "
            "credibility-weighted Dempster-Shafer fusion. "
            "Off: vanilla credibility-weighted fusion."
        ),
    )

    threshold = st.slider(
        "Risky / safe threshold",
        min_value=0, max_value=100, value=50, step=5,
        help="Suppliers scoring below this threshold are predicted risky.",
    )

    st.markdown("---")
    st.caption(
        "💾 **Backend.** Mock LLM by default. To use Anthropic, set "
        "`ANTHROPIC_API_KEY` and `USE_MOCK_LLM=0` in `.env`."
    )
    st.caption(
        "📊 **Reproducibility.** All numbers regenerable via "
        "`make eval` and `make sweep`."
    )
    st.markdown("---")
    st.caption(
        "**Data.** 87 suppliers in directory — Indian-focused (Bangalore "
        "concentration). 41 real listed Indian firms (PLI awardees, "
        "PSUs, listed EMS, semi design, automotive). 7 real Bangalore-"
        "specific firms (Saankhya Labs, Signalchip, Wipro 3D, Zetwerk, "
        "Tessolve, Tata Elxsi Whitefield, Capgemini Engineering). 35 "
        "illustrative SMEs marked ⓘ. 4 deliberately-risky foreign for "
        "OFAC/WB demos. No illustrative entry refers to any real firm."
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

PAGES = {
    "Overview":              page_overview.render,
    "Find suppliers":        page_find.render,
    "Supplier detail":       page_detail.render,
    "Parameters used":       page_parameters.render,
    "Compare":               page_compare.render,
    "Onboard new supplier":  page_onboard.render,
    "Adversarial lab":       page_lab.render,
    "Methodology":           page_method.render,
}

PAGES[page](use_defense=use_defense, threshold=float(threshold))
