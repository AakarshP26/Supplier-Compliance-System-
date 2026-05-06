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
from scs.profile import CertStatus, SupplierProfile
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
    profile=None,
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
    incorp_year = supplier.incorporated.year if supplier.incorporated else None
    score = fuse(
        supplier.id, comp, risk, use_defense=use_defense,
        profile=profile, incorporation_year=incorp_year,
    )
    return {
        "supplier": supplier, "compliance": comp, "risk": risk,
        "score": score, "profile": profile,
    }


# ---------------------------------------------------------------------------
# Profile builder: convert raw form inputs to a SupplierProfile
# ---------------------------------------------------------------------------


def _f(v) -> float | None:
    """Treat 0.0 as 'not provided' so DS fusion routes to uncertainty."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _i(v) -> int | None:
    """Treat 0 as 'not provided'."""
    if v is None:
        return None
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _yn(v) -> str | None:
    """Map 'unknown'/empty to None; pass 'yes'/'no' through."""
    if v in (None, "", "unknown"):
        return None
    if v in ("yes", "no"):
        return v
    return None


_CERT_MAP = {
    "active":  CertStatus.ACTIVE,
    "expired": CertStatus.EXPIRED,
    "pending": CertStatus.PENDING,
    "na":      CertStatus.NA,
    "unknown": CertStatus.UNKNOWN,
}


def _cert(v) -> CertStatus:
    return _CERT_MAP.get(v, CertStatus.UNKNOWN)


def _build_profile_from_inputs(
    sid: str, params: dict[str, Any]
) -> SupplierProfile | None:
    """Convert the onboarding form inputs to a SupplierProfile object.

    Returns None if the params dict is empty (the onboarding flow
    didn't include the parameter section).
    """
    if not params:
        return None

    # YN fields default to "unknown" in the schema, so we must pass the
    # string when set; otherwise omit the key.
    kwargs: dict[str, Any] = {"supplier_id": sid}

    # --- Identity / registrations ---
    if params.get("gstin"): kwargs["gstin"] = params["gstin"]
    if params.get("pan"):   kwargs["pan"] = params["pan"]
    if params.get("iec"):   kwargs["iec"] = params["iec"]
    udyam = params.get("udyam_registration")
    if udyam == "yes":
        kwargs["udyam_registration"] = "ONBOARDED"
    if (yn := _yn(params.get("epfo_registration"))): kwargs["epfo_registration"] = yn
    if (yn := _yn(params.get("esic_registration"))): kwargs["esic_registration"] = yn

    # --- Financial ---
    kwargs["annual_turnover_cr"]      = _f(params.get("annual_turnover_cr"))
    kwargs["net_worth_cr"]            = _f(params.get("net_worth_cr"))
    kwargs["current_ratio"]           = _f(params.get("current_ratio"))
    kwargs["debt_to_equity"]          = _f(params.get("debt_to_equity"))
    kwargs["gst_compliance_score"]    = _f(params.get("gst_compliance_score"))
    kwargs["days_payable_outstanding"] = _i(params.get("days_payable_outstanding"))

    # --- Operational ---
    kwargs["employees"]                = _i(params.get("employees"))
    kwargs["plant_area_sqft"]          = _i(params.get("plant_area_sqft"))
    kwargs["on_time_delivery_pct"]     = _f(params.get("on_time_delivery_pct"))
    kwargs["defect_rate_ppm"]          = _f(params.get("defect_rate_ppm"))
    kwargs["capacity_utilization_pct"] = _f(params.get("capacity_utilization_pct"))

    # --- Quality certs ---
    kwargs["iso_9001"]   = _cert(params.get("iso_9001"))
    kwargs["iso_14001"]  = _cert(params.get("iso_14001"))
    kwargs["iatf_16949"] = _cert(params.get("iatf_16949"))
    kwargs["as_9100"]    = _cert(params.get("as_9100"))
    kwargs["ipc_a_610"]  = _cert(params.get("ipc_a_610"))
    if (yn := _yn(params.get("bis_crs_active"))): kwargs["bis_crs_active"] = yn

    # --- Regulatory ---
    if (yn := _yn(params.get("mca_status_active"))):       kwargs["mca_status_active"] = yn
    if (yn := _yn(params.get("pollution_noc_kspcb"))):     kwargs["pollution_noc_kspcb"] = yn
    if (yn := _yn(params.get("fire_noc"))):                kwargs["fire_noc"] = yn
    if (yn := _yn(params.get("factories_act_license"))):   kwargs["factories_act_license"] = yn
    if (yn := _yn(params.get("epf_dues_clear"))):          kwargs["epf_dues_clear"] = yn
    if (yn := _yn(params.get("income_tax_returns_filed"))): kwargs["income_tax_returns_filed"] = yn

    # Drop None numeric values to be schema-clean
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        return SupplierProfile(**kwargs)
    except Exception as e:
        st.warning(f"Could not build profile from inputs: {e}")
        return None


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

        st.markdown("#### 2 · News intelligence (optional — 1 article)")
        st.caption(
            "Paste a single news article you've seen about this supplier. "
            "It will be passed through the LLM extractor (or the keyword "
            "fallback in offline mode) and folded into the risk score."
        )

        with st.expander("Article (optional)", expanded=True):
            n_title = st.text_input(
                "Title", key="art_title",
                placeholder=f"e.g. {name or 'Acme'} wins multi-year supply contract",
            )
            n_body = st.text_area(
                "Body (1–2 short paragraphs is fine)",
                key="art_body", height=120,
                placeholder="Paste the article body. The LLM will summarise into a structured RiskSignal.",
            )
            col_x, col_y = st.columns([3, 1])
            with col_x:
                n_url = st.text_input(
                    "Source URL", key="art_url",
                    placeholder="https://www.thehindu.com/...  (URL drives credibility prior)",
                    help="Source domain determines credibility prior. Tier-1 (Reuters, The Hindu, ET) "
                         "weighs more in fusion than press releases or anonymous blogs.",
                )
            with col_y:
                n_pub = st.date_input(
                    "Published", key="art_pub", value=date.today(),
                )

        st.markdown("#### 3 · Compliance & verification parameters (optional)")
        st.caption(
            "Provide the supplier's public-record parameters so the system can "
            "score them on financial health, operations, regulatory standing, and "
            "quality. Leave any field blank if you don't have data — the DS fusion "
            "treats missing values as uncertainty rather than penalising them."
        )

        param_inputs: dict[str, Any] = {}

        # --- Registrations & identity ---
        with st.expander("📋 Registrations & identity", expanded=False):
            r1, r2, r3 = st.columns(3)
            with r1:
                param_inputs["gstin"] = st.text_input(
                    "GSTIN", key="p_gstin",
                    placeholder="29ABCDE1234F1Z8",
                    help="15-char GST id; first 2 are state code (29 = Karnataka).",
                )
                param_inputs["pan"] = st.text_input("PAN", key="p_pan", placeholder="ABCDE1234F")
            with r2:
                param_inputs["udyam_registration"] = st.selectbox(
                    "Udyam (MSME) registered?", ["unknown", "yes", "no"], key="p_udyam",
                )
                param_inputs["epfo_registration"] = st.selectbox(
                    "EPFO registered?", ["unknown", "yes", "no"], key="p_epfo",
                )
            with r3:
                param_inputs["esic_registration"] = st.selectbox(
                    "ESIC registered?", ["unknown", "yes", "no"], key="p_esic",
                )
                param_inputs["iec"] = st.text_input("IEC code", key="p_iec",
                                                     placeholder="IEC0123456")

        # --- Financial health ---
        with st.expander("💰 Financial health", expanded=False):
            f1, f2, f3 = st.columns(3)
            with f1:
                param_inputs["annual_turnover_cr"] = st.number_input(
                    "Annual turnover (₹ crore)", key="p_turnover",
                    min_value=0.0, max_value=100000.0, value=0.0, step=0.5,
                )
                param_inputs["net_worth_cr"] = st.number_input(
                    "Net worth (₹ crore)", key="p_networth",
                    min_value=-1000.0, max_value=100000.0, value=0.0, step=0.5,
                    help="Negative net worth is a strong solvency red flag.",
                )
            with f2:
                param_inputs["current_ratio"] = st.number_input(
                    "Current ratio", key="p_cr",
                    min_value=0.0, max_value=20.0, value=0.0, step=0.05,
                    help="Healthy ≥ 1.5; concerning < 1.0.",
                )
                param_inputs["debt_to_equity"] = st.number_input(
                    "Debt-to-equity", key="p_de",
                    min_value=0.0, max_value=20.0, value=0.0, step=0.1,
                    help="Healthy ≤ 1.0; concerning > 2.5.",
                )
            with f3:
                param_inputs["gst_compliance_score"] = st.number_input(
                    "GST compliance score (0-100)", key="p_gst",
                    min_value=0.0, max_value=100.0, value=0.0, step=1.0,
                    help="GSTN portal score; healthy ≥ 80; concerning ≤ 50.",
                )
                param_inputs["days_payable_outstanding"] = st.number_input(
                    "Days payable outstanding", key="p_dpo",
                    min_value=0, max_value=500, value=0, step=1,
                    help="Healthy ≤ 45 days; concerning ≥ 120 (suggests payment distress).",
                )

        # --- Operations ---
        with st.expander("🏭 Operations", expanded=False):
            o1, o2, o3 = st.columns(3)
            with o1:
                param_inputs["employees"] = st.number_input(
                    "Employees", key="p_emp",
                    min_value=0, max_value=100000, value=0, step=1,
                )
                param_inputs["plant_area_sqft"] = st.number_input(
                    "Plant area (sqft)", key="p_area",
                    min_value=0, max_value=10000000, value=0, step=100,
                )
            with o2:
                param_inputs["on_time_delivery_pct"] = st.number_input(
                    "On-time delivery %", key="p_otd",
                    min_value=0.0, max_value=100.0, value=0.0, step=0.5,
                    help="Healthy ≥ 95%; concerning < 80%.",
                )
                param_inputs["defect_rate_ppm"] = st.number_input(
                    "Defect rate (ppm)", key="p_def",
                    min_value=0, max_value=1000000, value=0, step=100,
                    help="Healthy ≤ 500 ppm; concerning ≥ 5000 ppm.",
                )
            with o3:
                param_inputs["capacity_utilization_pct"] = st.number_input(
                    "Capacity utilization %", key="p_cap",
                    min_value=0.0, max_value=100.0, value=0.0, step=1.0,
                    help="Sweet spot: 50-85%. Below 30% (idle) or above 95% (no headroom) are red flags.",
                )

        # --- Quality certifications ---
        with st.expander("✅ Quality certifications", expanded=False):
            q1, q2, q3 = st.columns(3)
            CERT_OPTS = ["unknown", "active", "expired", "pending", "na"]
            with q1:
                param_inputs["iso_9001"] = st.selectbox(
                    "ISO 9001 (QMS)", CERT_OPTS, key="p_iso9k",
                )
                param_inputs["iso_14001"] = st.selectbox(
                    "ISO 14001 (env)", CERT_OPTS, key="p_iso14k",
                )
            with q2:
                param_inputs["iatf_16949"] = st.selectbox(
                    "IATF 16949 (auto)", CERT_OPTS, key="p_iatf",
                )
                param_inputs["as_9100"] = st.selectbox(
                    "AS9100 (aerospace)", CERT_OPTS, key="p_as9k",
                )
            with q3:
                param_inputs["ipc_a_610"] = st.selectbox(
                    "IPC-A-610 (acceptability)", CERT_OPTS, key="p_ipc",
                )
                param_inputs["bis_crs_active"] = st.selectbox(
                    "BIS CRS active?", ["unknown", "yes", "no"], key="p_biscrs",
                )

        # --- Regulatory ---
        with st.expander("📜 Regulatory & licences", expanded=False):
            g1, g2 = st.columns(2)
            YN_OPTS = ["unknown", "yes", "no"]
            with g1:
                param_inputs["mca_status_active"] = st.selectbox(
                    "MCA registration active?", YN_OPTS, key="p_mca",
                )
                param_inputs["pollution_noc_kspcb"] = st.selectbox(
                    "KSPCB pollution NOC?", YN_OPTS, key="p_kspcb",
                )
                param_inputs["fire_noc"] = st.selectbox(
                    "Fire NOC current?", YN_OPTS, key="p_fire",
                )
            with g2:
                param_inputs["factories_act_license"] = st.selectbox(
                    "Factories Act licence?", YN_OPTS, key="p_fact",
                )
                param_inputs["epf_dues_clear"] = st.selectbox(
                    "EPF dues clear?", YN_OPTS, key="p_epfd",
                )
                param_inputs["income_tax_returns_filed"] = st.selectbox(
                    "Income tax returns filed?", YN_OPTS, key="p_itr",
                )

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

        # Build the article list — at most one article
        articles = []
        if n_title.strip() and n_body.strip():
            articles.append(dict(
                title=n_title.strip(), body=n_body.strip(),
                url=(n_url.strip() or None), pub=n_pub,
            ))

        return dict(
            name=name.strip(),
            legal_name=legal_name.strip() or None,
            country=country if country != "Other" else "XX",
            category=SupplierCategory(category),
            cin=cin.strip() or None,
            website=website.strip() or None,
            year=int(year),
            aliases=[a.strip() for a in aliases_raw.split(",") if a.strip()],
            articles=articles,
            params=param_inputs,
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

        # Build pasted articles (at most one)
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

        # Build a SupplierProfile from the parameter inputs (treat 'unknown'
        # / 0 / empty as "missing" so DS fusion routes them to uncertainty).
        profile = _build_profile_from_inputs(sid, submitted.get("params", {}))

        with st.spinner("Running compliance + risk pipeline…"):
            result = _run_for_new_supplier(supplier, articles, use_defense, profile=profile)

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
