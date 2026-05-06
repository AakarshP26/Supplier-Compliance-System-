"""Methodology page - the paper made interactive."""
from __future__ import annotations

import streamlit as st

from scs.dashboard import charts
from scs.dashboard.components import section
from scs.dashboard.styling import PALETTE


def _flowchart_svg() -> str:
    """Inline SVG showing the full Bangalore-only pipeline.

    Three evidence streams (compliance, news, parameters) feed into
    Yager fusion which produces a SupplierScore. The optional defense
    layer wraps the news stream.
    """
    primary  = "#1A365D"   # navy
    accent   = "#2E75B6"   # blue
    ok       = "#1F8A4C"   # green
    warn     = "#D97706"   # amber
    danger   = "#B91C1C"   # red
    muted    = "#595959"
    bg       = "#F4F6FA"
    border   = "#CFD3DC"

    return f"""
<svg viewBox="0 0 1100 580" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, system-ui, sans-serif">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{primary}"/>
    </marker>
    <marker id="arrowAccent" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{accent}"/>
    </marker>
  </defs>

  <!-- ==================== INPUT ==================== -->
  <rect x="450" y="20" width="200" height="60" rx="6"
        fill="white" stroke="{primary}" stroke-width="2"/>
  <text x="550" y="48" text-anchor="middle" font-size="15" font-weight="700" fill="{primary}">Supplier</text>
  <text x="550" y="68" text-anchor="middle" font-size="11" fill="{muted}">name · CIN · aliases · category · city</text>

  <!-- arrows from input down to 3 streams -->
  <line x1="550" y1="80" x2="170" y2="120" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="550" y1="80" x2="550" y2="120" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="550" y1="80" x2="930" y2="120" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- ==================== COMPLIANCE STREAM ==================== -->
  <rect x="40" y="120" width="260" height="180" rx="8"
        fill="{bg}" stroke="{accent}" stroke-width="1.5"/>
  <text x="170" y="145" text-anchor="middle" font-size="13" font-weight="700" fill="{primary}">1 · Compliance pipeline</text>
  <text x="170" y="162" text-anchor="middle" font-size="10" fill="{muted}">parallel async checks</text>

  <rect x="58" y="178" width="224" height="34" rx="4" fill="white" stroke="{border}"/>
  <text x="68" y="200" font-size="11" font-weight="600" fill="{primary}">OFAC SDN</text>
  <text x="170" y="200" font-size="10" fill="{muted}">fuzzy match ≥ 88</text>

  <rect x="58" y="218" width="224" height="34" rx="4" fill="white" stroke="{border}"/>
  <text x="68" y="240" font-size="11" font-weight="600" fill="{primary}">BIS CRS</text>
  <text x="170" y="240" font-size="10" fill="{muted}">R-number lookup</text>

  <text x="170" y="280" text-anchor="middle" font-size="10" fill="{muted}">→ pass / fail / unknown</text>

  <!-- ==================== NEWS STREAM ==================== -->
  <rect x="420" y="120" width="260" height="180" rx="8"
        fill="{bg}" stroke="{accent}" stroke-width="1.5"/>
  <text x="550" y="145" text-anchor="middle" font-size="13" font-weight="700" fill="{primary}">2 · News intelligence</text>
  <text x="550" y="162" text-anchor="middle" font-size="10" fill="{muted}">LLM extraction → corroboration</text>

  <rect x="438" y="178" width="224" height="34" rx="4" fill="white" stroke="{border}"/>
  <text x="448" y="200" font-size="11" font-weight="600" fill="{primary}">Article extractor</text>
  <text x="572" y="200" font-size="10" fill="{muted}">structured signal</text>

  <rect x="438" y="218" width="224" height="34" rx="4" fill="white" stroke="{border}"/>
  <text x="448" y="240" font-size="11" font-weight="600" fill="{primary}">Corroboration</text>
  <text x="572" y="240" font-size="10" fill="{muted}">cross-domain check</text>

  <text x="550" y="280" text-anchor="middle" font-size="10" fill="{muted}">→ event_type · severity · sentiment</text>

  <!-- ==================== PARAMETERS STREAM ==================== -->
  <rect x="800" y="120" width="260" height="180" rx="8"
        fill="{bg}" stroke="{accent}" stroke-width="1.5"/>
  <text x="930" y="145" text-anchor="middle" font-size="13" font-weight="700" fill="{primary}">3 · Verification parameters</text>
  <text x="930" y="162" text-anchor="middle" font-size="10" fill="{muted}">40+ Indian SME public-record fields</text>

  <rect x="818" y="178" width="224" height="34" rx="4" fill="white" stroke="{border}"/>
  <text x="828" y="200" font-size="11" font-weight="600" fill="{primary}">Numeric ramps</text>
  <text x="942" y="200" font-size="10" fill="{muted}">healthy ↔ concerning</text>

  <rect x="818" y="218" width="224" height="34" rx="4" fill="white" stroke="{border}"/>
  <text x="828" y="240" font-size="11" font-weight="600" fill="{primary}">Categorical maps</text>
  <text x="942" y="240" font-size="10" fill="{muted}">cert / NOC / yes-no</text>

  <text x="930" y="280" text-anchor="middle" font-size="10" fill="{muted}">unknown → uncertainty mass</text>

  <!-- ==================== DEFENSE LAYER (wraps news) ==================== -->
  <rect x="385" y="320" width="330" height="64" rx="6"
        fill="white" stroke="{warn}" stroke-width="1.5" stroke-dasharray="6 3"/>
  <text x="550" y="342" text-anchor="middle" font-size="12" font-weight="700" fill="{warn}">Trust-calibrated defense (optional)</text>
  <text x="550" y="362" text-anchor="middle" font-size="10" fill="{muted}">credibility prior × burst penalty × template-similarity penalty</text>
  <text x="550" y="376" text-anchor="middle" font-size="10" fill="{muted}">applied to news signals before fusion</text>
  <line x1="550" y1="300" x2="550" y2="320" stroke="{warn}" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- ==================== BPA conversion (3 → 1) ==================== -->
  <rect x="40" y="320" width="260" height="44" rx="6" fill="white" stroke="{primary}" stroke-width="1.5"/>
  <text x="170" y="342" text-anchor="middle" font-size="12" font-weight="700" fill="{primary}">BPAs from compliance</text>
  <text x="170" y="358" text-anchor="middle" font-size="10" fill="{muted}">credibility 0.95 · pass×0.5 · fail×0.85</text>
  <line x1="170" y1="300" x2="170" y2="320" stroke="{accent}" stroke-width="1.5" marker-end="url(#arrowAccent)"/>

  <rect x="800" y="320" width="260" height="44" rx="6" fill="white" stroke="{primary}" stroke-width="1.5"/>
  <text x="930" y="342" text-anchor="middle" font-size="12" font-weight="700" fill="{primary}">BPAs from parameters</text>
  <text x="930" y="358" text-anchor="middle" font-size="10" fill="{muted}">one BPA per known field</text>
  <line x1="930" y1="300" x2="930" y2="320" stroke="{accent}" stroke-width="1.5" marker-end="url(#arrowAccent)"/>

  <!-- arrows from each BPA box → fusion -->
  <line x1="170" y1="364" x2="500" y2="430" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="550" y1="384" x2="550" y2="430" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>
  <line x1="930" y1="364" x2="600" y2="430" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- ==================== YAGER FUSION ==================== -->
  <rect x="380" y="430" width="340" height="64" rx="8"
        fill="{primary}" stroke="{primary}" stroke-width="2"/>
  <text x="550" y="455" text-anchor="middle" font-size="14" font-weight="700" fill="white">Yager-rule DS fusion</text>
  <text x="550" y="475" text-anchor="middle" font-size="11" fill="white">conflict mass → uncertainty (not normalised away)</text>
  <text x="550" y="488" text-anchor="middle" font-size="10" fill="white" opacity="0.85">m_safe + m_risky + m_Θ = 1.0</text>

  <!-- arrow to score -->
  <line x1="550" y1="494" x2="550" y2="520" stroke="{primary}" stroke-width="1.5" marker-end="url(#arrow)"/>

  <!-- ==================== SCORE ==================== -->
  <rect x="350" y="520" width="400" height="48" rx="6"
        fill="white" stroke="{ok}" stroke-width="2"/>
  <text x="550" y="542" text-anchor="middle" font-size="13" font-weight="700" fill="{primary}">SupplierScore</text>
  <text x="550" y="560" text-anchor="middle" font-size="10" fill="{muted}">score 0–100 · grade A–F · belief decomposition · contributions waterfall</text>

</svg>
""".strip()


def render(use_defense: bool, threshold: float) -> None:
    st.title("📐 Methodology")
    st.caption("How the system actually works — pipeline overview, math, and limitations.")

    # ---------- Architecture flowchart ----------
    section("Pipeline architecture")
    st.markdown(
        """
The figure below shows the full data flow: a supplier object enters at
the top, three independent evidence streams produce BPAs, the optional
trust-calibrated defense layer wraps the news stream, and Yager-rule
fusion combines everything into a single SupplierScore.
        """
    )
    # Render the SVG inside an HTML component — st.markdown's sanitizer
    # can strip <svg>/<defs>/<marker> elements even with unsafe_allow_html.
    # components.v1.html bypasses that and gives a clean iframe.
    import streamlit.components.v1 as components
    components.html(
        f"""
<div style="display:flex; justify-content:center; padding:8px;">
  <div style="max-width:1100px; width:100%;">
    {_flowchart_svg()}
  </div>
</div>
        """,
        height=620,
        scrolling=False,
    )
    st.caption(
        "Three independent evidence streams (compliance, news, "
        "verification parameters) → BPAs → Yager fusion → SupplierScore. "
        "Defense layer is dashed because it is optional and only applies "
        "to the news stream."
    )

    section("Threat model")
    st.markdown(
        """
A supplier under evaluation has both motive and capability to manipulate the
public information ecosystem the LLM pipeline consumes. The threat model
distinguishes what the adversary **can** do (with effort or money) from what
they **cannot** plausibly modify.
        """
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            f"""
**Out of reach for the adversary**

{_pill('Government lists', PALETTE['ok'])}  OFAC SDN, BIS CRS, MCA21,
GSTN — these are authoritative and slow to falsify.

{_pill('Tier-1 news', PALETTE['ok'])}  Reuters, FT, The Hindu, Economic
Times — high editorial barrier; placing fake stories here is hard.
            """
        )
    with col_b:
        st.markdown(
            f"""
**Available attack channels**

{_pill('Press-release wires', PALETTE['danger'])}  PR Newswire, Business
Wire — pay-to-distribute, no fact checking.

{_pill('Anonymous blogs', PALETTE['danger'])}  Medium, blogspot, X —
free, no editorial layer.

{_pill('Self-published', PALETTE['warn'])}  Brand-new domain controlled
by the adversary.
            """
        )

    section("Source credibility priors")
    st.plotly_chart(charts.credibility_pyramid(), use_container_width=True)
    st.caption(
        "The fusion layer reads these priors directly. Government lists "
        "carry mass that's hard to displace; anonymous blogs barely move "
        "the posterior unless many corroborate."
    )

    section("Dempster–Shafer evidence combination (Yager's rule)")
    st.markdown(
        r"""
We use a frame of discernment $\Theta = \{\text{safe}, \text{risky}\}$.
Each piece of evidence is mapped to a basic probability assignment (BPA)
$m: 2^\Theta \to [0,1]$, where:

$$
m(\{\text{safe}\}) = m_s, \quad
m(\{\text{risky}\}) = m_r, \quad
m(\Theta) = 1 - m_s - m_r
$$

The mass on $\Theta$ is the *uncertainty*. Two BPAs combine via Yager's
modified rule (conflict goes to uncertainty rather than being normalised
away — important under adversarial input):

$$
\begin{aligned}
(m_1 \oplus m_2)(\{\text{safe}\}) &= m_1^s m_2^s + m_1^s m_2^\Theta + m_1^\Theta m_2^s \\
(m_1 \oplus m_2)(\{\text{risky}\}) &= m_1^r m_2^r + m_1^r m_2^\Theta + m_1^\Theta m_2^r \\
(m_1 \oplus m_2)(\Theta) &= m_1^\Theta m_2^\Theta + (m_1^s m_2^r + m_1^r m_2^s)
\end{aligned}
$$

Each evidence item's BPA scales with three factors:
        """
    )
    c1, c2, c3 = st.columns(3)
    with c1: st.info("**Source credibility** π ∈ [0,1] from the credibility registry.")
    with c2: st.info("**Corroboration** ×1.0 if echoed by an independent registrable domain, ×0.5 otherwise.")
    with c3: st.info("**Recency / defense weight** in (0,1] from burst + template-similarity penalty.")

    section("Defense: burst + template-similarity downweighting")
    st.markdown(
        r"""
Two cheap, model-free pattern detectors compose multiplicatively into the
defense weight $w_i$ that downscales each signal's BPA:

**Burst penalty.** If $N$ positive signals about the same supplier land
within a $\Delta t$ window, each gets weight $1 / \log_2(N+1)$. Many
positive items in a short window is a coordination signature.

**Template-similarity penalty.** If a positive signal's summary has
Jaccard token overlap $J \geq 0.55$ with at least two other positive
signals, weight is $1 / \log_2(\text{count}+1.5)$. Copy-paste astroturf
gets caught.

Both are interpretable, both leave clean data essentially untouched
(no burst, no near-duplicates → $w_i = 1$).
        """
    )

    section("Final score")
    st.markdown(
        r"""
After fusion, the score is rescaled from belief difference to a 0–100
range:

$$
\text{score} = 50 + 50 \cdot (m^s - m^r)
$$

Threshold for "risky" is 50 by default. The dashboard's sidebar lets you
shift this if your operator's tolerance differs.
        """
    )

    section("Limitations (honest)")
    st.markdown(
        """
- **Small budgets bypass.** B≤2 falls below the burst threshold — the
  defense is no-op there. Future work: lower thresholds at the cost of
  higher false positives on legitimate news bursts.
- **Coordinated multi-domain attacks.** A sophisticated adversary
  rotating across many low-credibility domains AND varying templates can
  partially evade. Honest finding in §5.4 of the paper.
- **Mock LLM in offline mode.** The default backend uses regex on
  keywords — strictly weaker than a real LLM. Real Anthropic backend is
  selectable via env var.
- **Sample compliance lists.** OFAC and BIS CRS data here are small
  offline snapshots for reproducibility. Production would pull live
  feeds (sanctionssearch.ofac.treas.gov, crsbis.in).
- **Synthetic profile values.** Real listed firms have real identities
  (CIN, category, location), but their parameter values (current ratio,
  defect rate, etc.) are realistic patterns, not scraped from MCA21.
        """
    )

    section("On the supplier directory")
    st.markdown(
        """
The directory is **100% Indian, Bangalore-focused**. It holds two
kinds of entries:

**Real-listed entities.** Companies with public-record analogues —
Indian PLI awardees (Dixon, Lava, Optiemus, Foxconn India, Wistron India,
Pegatron India, Bhagwati, Amber, Syrma SGS, Kaynes, Cyient DLM, Avalon,
Epack, VVDN, Centum, Bharat FIH, MosChip, Tata Electronics, Vedanta-
Foxconn JV); Indian PSUs and listed firms (BEL Bengaluru, ITI, Tejas
Networks, HFCL, Sterlite Tech, Tata Elxsi, Bosch India, Honeywell
Automation India, Continental Automotive India); real Bangalore SMEs
including **Ecopmin Technologies (Peenya)**, Rashmi Electricals (Peenya),
and Tek Tools Bengaluru (Peenya).

**Illustrative SME-scale entities.** Marked with `is_illustrative=True`
and a `note` field describing what they represent. This includes both
healthy SMEs (Mysuru Precision Electronics, Deccan PCB Works, etc.) and
**four risk-target demonstrators** specifically designed for the
adversarial-lab demo: yelahanka-shadow-traders (OFAC fail + adversarial
target), peenya-grey-market (BIS CRS fail), bommanahalli-relabel
(counterfeit broker), rajajinagar-evasion-shell (alias-match fail).
These exist to demonstrate the system's full range of behaviour
without misrepresenting any real firm. They appear with a ⓘ marker
throughout the dashboard and can be filtered out via the "Real only"
toggle on the **Find suppliers** page.

This disclosure is exposed in the sidebar and on every page where
illustrative entries appear.
        """
    )


def _pill(text: str, color: str) -> str:
    return (
        f"<span style='display:inline-block; padding:0.1rem 0.6rem; "
        f"border-radius:999px; font-size:0.75rem; font-weight:600; "
        f"background:{color}22; color:{color}; border:1px solid {color}55;'>"
        f"{text}</span>"
    )
