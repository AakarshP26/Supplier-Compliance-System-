"""Streamlit dashboard entrypoint.

Run with:
    streamlit run src/scs/dashboard/app.py
or via:
    make dashboard

Pages:
  • Overview       - portfolio view across all 25 suppliers
  • Supplier       - rich single-supplier report with belief decomposition,
                     risk topology, news timeline, evidence sources,
                     score waterfall.
  • Compare        - up to 5 suppliers side-by-side (radar overlay,
                     parallel coordinates, metric matrix).
  • Adversarial    - the paper's central experiment, made interactive.
  • Methodology    - the maths, the threat model, the defense.
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
    page_overview, page_detail, page_compare, page_lab, page_method,
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
<div class="scs-tag">Trust-calibrated scoring · v0.1</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    page = st.radio(
        "Navigate",
        options=[
            "Overview",
            "Supplier detail",
            "Compare",
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


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

PAGES = {
    "Overview": page_overview.render,
    "Supplier detail": page_detail.render,
    "Compare": page_compare.render,
    "Adversarial lab": page_lab.render,
    "Methodology": page_method.render,
}

PAGES[page](use_defense=use_defense, threshold=float(threshold))
