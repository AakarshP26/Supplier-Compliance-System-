"""Methodology page - the paper made interactive."""
from __future__ import annotations

import streamlit as st

from scs.dashboard import charts
from scs.dashboard.components import section
from scs.dashboard.styling import PALETTE


def render(use_defense: bool, threshold: float) -> None:
    st.title("📐 Methodology")
    st.caption("How the system actually works — the paper's §4, made interactive.")

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

{_pill('Government lists', PALETTE['ok'])}  OFAC SDN, World Bank Debarred,
BIS CRS — these are authoritative and slow to falsify.

{_pill('Tier-1 news', PALETTE['ok'])}  Reuters, FT, The Hindu — high
editorial barrier; placing fake stories here is hard.
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
- **Sample compliance lists.** OFAC, World Bank, and BIS data here are
  small offline snapshots for reproducibility. Production would pull
  live feeds.
        """
    )


def _pill(text: str, color: str) -> str:
    return (
        f"<span style='display:inline-block; padding:0.1rem 0.6rem; "
        f"border-radius:999px; font-size:0.75rem; font-weight:600; "
        f"background:{color}22; color:{color}; border:1px solid {color}55;'>"
        f"{text}</span>"
    )
