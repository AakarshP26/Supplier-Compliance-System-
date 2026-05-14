"""Onboarding page - submit a new supplier and see the full risk report.

The user fills a form. Optionally they paste news article bodies the LLM
should analyse. On submit the system runs the full pipeline (compliance
+ risk extraction + DS fusion + defense) and renders the report card.

Persistence: new suppliers live in st.session_state for the session.
This is deliberate — the seed list stays clean and reproducible, while
demos can show the system handling cold-start entries on the fly.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from scs.compliance.pipeline import run as run_comp
from scs.models import (
    ComplianceCheck, ComplianceReport, Provenance, RiskProfile, Supplier, SupplierCategory,
)
from scs.risk.extractor import extract_signal
from scs.risk.news import NewsArticle
from scs.risk.pipeline import _annotate_corroboration
from scs.scoring.fusion import fuse

from scs.dashboard import charts
from scs.dashboard.components import (
    section, kpi, hero, status_pill, compliance_status_html,
)
from scs.dashboard.styling import PALETTE, score_color


COUNTRY_OPTIONS = [
    "IN", "US", "TW", "CN", "KR", "JP", "DE", "NL", "CH", "GB", "FR",
    "VN", "TH", "MY", "SG", "PH", "ID", "MX", "BR", "CA", "AU", "IL",
    "AE", "RU", "VG", "BS", "KY", "Other",
]


def _initial_state() -> None:
    """Initialise session-state containers used across reruns."""
    if "onboarded_suppliers" not in st.session_state:
        st.session_state.onboarded_suppliers = []  # list[dict]
    if "onboarded_articles" not in st.session_state:
        st.session_state.onboarded_articles = {}   # dict[str, list[NewsArticle]]
    if "last_assessment" not in st.session_state:
        st.session_state.last_assessment = None    # the most recent (supplier, comp, risk, score)


# ---------------------------------------------------------------------------
# Pipeline: run on the fresh supplier object directly (don't touch globals)
# ---------------------------------------------------------------------------


def _run_for_new_supplier(
    supplier: Supplier,
    pasted_articles: list[NewsArticle],
    use_defense: bool,
) -> dict[str, Any]:
    """Run compliance + risk + fusion for a brand-new supplier."""
    comp: ComplianceReport = run_comp(supplier)

    # Risk extraction over the user's pasted articles only (a brand-new
    # supplier hasn't been crawled yet — that's the realistic scenario).
    signals = [extract_signal(supplier.name, art) for art in pasted_articles]
    signals = _annotate_corroboration(signals)
    risk = RiskProfile(
        supplier_id=supplier.id,
        signals=signals,
        article_count=len(pasted_articles),
    )
    score = fuse(supplier.id, comp, risk, use_defense=use_defense)
    return {"supplier": supplier, "compliance": comp, "risk": risk, "score": score}


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------


def _render_form(use_defense: bool) -> dict[str, Any] | None:
    """Render the input form. Returns the submitted data dict or None."""
    with st.form("onboard_form", clear_on_submit=False):
        st.markdown("#### 1 · Supplier identity")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            name = st.text_input(
                "Trading name *",
                placeholder="e.g. Karnataka Precision Components Pvt Ltd",
                help="The name everyone calls them by. Required.",
            )
        with c2:
            country = st.selectbox("Country *", options=COUNTRY_OPTIONS, index=0)
        with c3:
            category = st.selectbox(
                "Category *",
                options=[c.value for c in SupplierCategory],
                index=1,  # default: ems
                format_func=lambda v: v.replace("_", " "),
                help="Where in the electronics value chain do they sit?",
            )

        c4, c5, c6 = st.columns([2, 1, 1])
        with c4:
            legal_name = st.text_input(
                "Legal name", placeholder="As registered (e.g. with MCA, Companies House)",
            )
        with c5:
            cin = st.text_input(
                "CIN / corporate id", placeholder="e.g. U32109KA2018PTC112233",
                help="Indian Corporate Identification Number, or equivalent foreign id.",
            )
        with c6:
            year = st.number_input(
                "Year incorporated", min_value=1900, max_value=date.today().year,
                value=2020, step=1,
            )

        c7, c8 = st.columns(2)
        with c7:
            website = st.text_input("Website", placeholder="https://example.com")
        with c8:
            aliases_raw = st.text_input(
                "Aliases (comma-separated)",
                placeholder="e.g. KPC, Karnataka Precision, KPC Components",
                help="Other names this supplier is known by — used for fuzzy matching against compliance lists.",
            )

        st.markdown("#### 2 · News intelligence (optional)")
        st.caption(
            "Paste 0 or more news article bodies you've seen about this supplier. "
            "Each one will be passed through the LLM extractor (or the keyword "
            "fallback in offline mode) and combined into the risk score."
        )

        n_articles = st.number_input(
            "How many articles will you paste?", min_value=0, max_value=10, value=2, step=1,
        )

        article_inputs: list[dict[str, Any]] = []
        for i in range(int(n_articles)):
            with st.expander(f"Article {i + 1}", expanded=(i < 2)):
                title = st.text_input(
                    "Title", key=f"title_{i}",
                    placeholder=f"e.g. {name or 'Acme'} wins multi-year supply contract",
                )
                body = st.text_area(
                    "Body (1–2 short paragraphs is fine)",
                    key=f"body_{i}", height=120,
                    placeholder="Paste the article body. The LLM will summarise into a structured RiskSignal.",
                )
                col_x, col_y = st.columns([3, 1])
                with col_x:
                    url = st.text_input(
                        "Source URL", key=f"url_{i}",
                        placeholder="https://www.reuters.com/...  (URL drives credibility prior)",
                        help="Source domain determines the credibility prior. Higher-tier outlets weigh more in fusion.",
                    )
                with col_y:
                    pub = st.date_input(
                        "Published", key=f"pub_{i}", value=date.today(),
                    )
                article_inputs.append(dict(
                    title=title.strip(), body=body.strip(),
                    url=url.strip() or None, pub=pub,
                ))

        st.markdown("---")
        c1, c2 = st.columns([1, 3])
        with c1:
            submitted = st.form_submit_button("🚀 Run analysis", type="primary", use_container_width=True)
        with c2:
            st.caption(
                "Submitting is local-only. The supplier lives in your "
                "browser session and disappears when you close the tab."
            )

        if not submitted:
            return None

        # Validate
        if not name.strip():
            st.error("Trading name is required.")
            return None

        return dict(
            name=name.strip(),
            legal_name=legal_name.strip() or None,
            country=country if country != "Other" else "XX",
            category=SupplierCategory(category),
            cin=cin.strip() or None,
            website=website.strip() or None,
            year=int(year),
            aliases=[a.strip() for a in aliases_raw.split(",") if a.strip()],
            articles=[a for a in article_inputs if a["title"] and a["body"]],
        )


# ---------------------------------------------------------------------------
# Render the assessment after a successful submit
# ---------------------------------------------------------------------------


def _render_assessment(result: dict[str, Any], threshold: float) -> None:
    supplier = result["supplier"]
    comp = result["compliance"]
    risk = result["risk"]
    score = result["score"]

    hero(supplier, score)

    pred = "RISKY" if score.score < threshold else "SAFE"
    pred_color = PALETTE["danger"] if score.score < threshold else PALETTE["ok"]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi("Score", f"{score.score:.1f}", color=score_color(score.score))
    with c2: kpi("Belief safe",  f"{score.belief_safe:.2f}", color=PALETTE["ok"])
    with c3: kpi("Belief risky", f"{score.belief_risky:.2f}", color=PALETTE["danger"])
    with c4: kpi("Uncertainty",  f"{score.uncertainty:.2f}", color=PALETTE["unknown"])
    with c5: kpi("Compliance fails", str(comp.fail_count),
                  color=PALETTE["danger"] if comp.fail_count else PALETTE["ok"])
    with c6: kpi("Prediction", pred, color=pred_color)

    section("Belief decomposition · risk topology")
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(charts.belief_donut(score), use_container_width=True)
    with col_b:
        st.plotly_chart(charts.risk_radar(risk), use_container_width=True)

    section("Compliance check results")
    rows = []
    for c in comp.checks:
        rows.append({
            "Source": c.source,
            "Status": c.status.upper(),
            "Credibility": c.provenance.credibility,
            "Detail": c.detail,
        })
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True, hide_index=True,
        column_config={
            "Credibility": st.column_config.ProgressColumn(
                "Cred.", format="%.2f", min_value=0.0, max_value=1.0,
            ),
        },
    )

    section("Extracted risk signals from your pasted articles")
    if not risk.signals:
        st.info(
            "No news provided. The score above is driven entirely by "
            "compliance signals — useful for a cold-start supplier with "
            "no public footprint, but uncertainty mass will be high."
        )
    else:
        rows = []
        for sg in risk.signals:
            rows.append({
                "Event": sg.event_type.value,
                "Severity": sg.severity,
                "Sentiment": sg.sentiment,
                "Source": sg.provenance.source_name,
                "Credibility": sg.credibility,
                "Corroborated": "✓" if sg.is_corroborated else "—",
                "Summary": sg.summary,
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True, hide_index=True,
            column_config={
                "Severity": st.column_config.ProgressColumn(
                    "Sev", format="%d", min_value=0, max_value=5,
                ),
                "Sentiment":  st.column_config.NumberColumn(format="%+.2f"),
                "Credibility": st.column_config.ProgressColumn(
                    "Cred.", format="%.2f", min_value=0.0, max_value=1.0,
                ),
            },
        )

    section("Score breakdown")
    st.plotly_chart(charts.contributions_waterfall(score), use_container_width=True)


# ---------------------------------------------------------------------------
# Page entrypoint
# ---------------------------------------------------------------------------


def render(use_defense: bool, threshold: float) -> None:
    _initial_state()

    st.title("➕ Onboard a new supplier")
    st.caption(
        "Run the full risk pipeline against a supplier that isn't in the "
        "directory yet. Useful when procurement is evaluating an unfamiliar "
        "vendor for the first time."
    )

    with st.expander("How this page works", expanded=False):
        st.markdown(
            """
1. **Identity** — name, country, category at minimum. The system runs
   compliance checks (OFAC SDN, World Bank Debarred, BIS CRS) against
   whatever names and aliases you provide.
2. **News intelligence (optional)** — paste 0 or more recent articles.
   Each is fed through the LLM extractor (or the deterministic keyword
   fallback if `USE_MOCK_LLM=1`). The source URL drives the credibility
   prior used in fusion.
3. **Submit** — Dempster–Shafer fusion combines compliance + news signals
   into the final score; you see the same belief decomposition, risk
   topology, and contribution waterfall as on the **Supplier detail**
   page.
4. **No persistence** — the supplier exists in your browser session
   only. Reproducible benchmarks stay seeded from the JSON files.
            """
        )

    # ---------- Past submissions ----------
    if st.session_state.onboarded_suppliers:
        section(f"Onboarded this session ({len(st.session_state.onboarded_suppliers)})")
        rows = []
        for entry in st.session_state.onboarded_suppliers:
            rows.append({
                "Supplier":   entry["supplier"].name,
                "Country":    entry["supplier"].country,
                "Category":   entry["supplier"].category.value.replace("_", " "),
                "Score":      entry["score"].score,
                "Grade":      entry["score"].grade,
                "Articles":   entry["risk"].article_count,
                "Submitted":  entry["submitted_at"].strftime("%H:%M:%S"),
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100),
            },
        )
        if st.button("🗑️ Clear session submissions"):
            st.session_state.onboarded_suppliers = []
            st.session_state.last_assessment = None
            st.rerun()

    # ---------- Form ----------
    section("Submit")
    submitted = _render_form(use_defense)

    if submitted is not None:
        # Build Supplier object
        sid = "session-" + submitted["name"].lower().replace(" ", "-")[:30]
        try:
            supplier = Supplier(
                id=sid,
                name=submitted["name"],
                legal_name=submitted["legal_name"],
                country=submitted["country"],
                category=submitted["category"],
                cin=submitted["cin"],
                website=submitted["website"],
                incorporated=date(submitted["year"], 1, 1),
                aliases=tuple(submitted["aliases"]),
                is_illustrative=False,
                note="Onboarded via dashboard, session-only.",
            )
        except Exception as e:
            st.error(f"Could not build supplier object: {e}")
            return

        # Build pasted articles
        articles: list[NewsArticle] = []
        for i, a in enumerate(submitted["articles"]):
            articles.append(NewsArticle(
                id=f"{sid}-pasted-{i:03d}",
                supplier_id=sid,
                title=a["title"],
                body=a["body"],
                url=a["url"],
                published_at=datetime.combine(a["pub"], datetime.min.time(), tzinfo=timezone.utc),
            ))

        with st.spinner("Running compliance + risk pipeline…"):
            result = _run_for_new_supplier(supplier, articles, use_defense)

        st.session_state.last_assessment = result
        st.session_state.onboarded_suppliers.append({
            "supplier": result["supplier"],
            "score": result["score"],
            "risk": result["risk"],
            "compliance": result["compliance"],
            "submitted_at": datetime.now(timezone.utc),
        })

        st.success("Analysis complete — scroll down for the full report.")

    # ---------- Render the most recent assessment ----------
    if st.session_state.last_assessment is not None:
        section("Latest assessment")
        _render_assessment(st.session_state.last_assessment, threshold)
