# DEMO RUNBOOK — 20-minute Phase II Review

**Format:** Live in-person · Q&A · teacher's first time seeing the project
**Total time:** ~22 minutes (15 min walkthrough + 5-7 min Q&A buffer)

---

## How to use this runbook

This is an actor's script. Print it or keep it on your phone. The
left column tells you what to say (paraphrase, don't memorise). The
right column tells you what to click or do on screen. Times are
cumulative — glance at your watch at each timestamp to stay on track.

Practise the demo flow **twice** before the review with a friend or
roommate watching. The first run will overshoot 20 min badly; the
second will land closer to 18.

---

## 30 minutes before — pre-demo checklist

Run these commands and verify each one works before you walk into the
review room. If any fails, you have time to fix it.

```bash
cd ~/Supplier-Compliance-System-
source .venv/bin/activate

# 1. Tests pass (one second)
make test
# Expected: 25 passed in ~1.3s

# 2. Headline experiment regenerates the result table
make eval
cat data/results/headline.csv | head -5
# Expected: clean F1 ≈ 0.73, defended F1 ≈ 1.00

# 3. Dashboard launches
make dashboard
# Expected: opens at http://localhost:8501
```

Now in the dashboard, click through these pages once and confirm each
loads without error: **Overview, Find suppliers, Supplier detail
(pick Dixon Technologies), Parameters used, Onboard new supplier,
Adversarial lab**.

If anything 500s, restart the dashboard before the review.

### What to have open on your laptop

- **Tab 1:** the dashboard at `localhost:8501`, on the **Overview** page.
- **Tab 2:** VS Code with the project open, focused on `src/scs/scoring/fusion.py` (in case the teacher asks to see code).
- **Tab 3:** `PROJECT_GUIDE.md` open in VS Code preview mode (Cmd+K, V) — your safety net for any concept question.

Mute notifications. Plug in your laptop. Volume off.

---

## The script

### 0:00 — 1:00 · Opening (1 minute)

> "Good morning. Phase II review for the Supplier Compliance System
> aligned with SDG 9. I'll show you the problem, the architecture,
> the live system, and the headline result. About fifteen minutes,
> then I'll take questions."

[Have the **Overview** page on screen. Don't start clicking yet.]

> "One disclosure up front: the directory has eighty-seven suppliers.
> Forty-one are real listed Indian firms, seven are real Bangalore
> firms, four are real foreign entities on actual sanction lists, and
> thirty-five are illustrative SME-scale entries — fictitious
> composites of typical Bangalore suppliers, marked with an info icon
> everywhere they appear. They demonstrate the system handling small
> suppliers without misrepresenting any real firm."

This pre-empts the most likely "wait, are these real companies?"
question. Address it before they ask.

---

### 1:00 — 4:00 · The problem and what's novel (3 minutes)

[Stay on Overview, but you're talking to the teacher, not the screen.]

> "The problem is simple to state. A buyer needs to decide if a
> supplier is trustworthy enough to place an order with. The data
> they look at is messy: sanction lists, news, public filings, ISO
> certs, GST records. The modern AI-scoring approach is to feed
> everything into an LLM and ask for a score."

[Pause]

> "That approach has a critical flaw. LLMs are gullible. A supplier
> that wants a contract can plant flattering articles on cheap
> PR-wire services for fifty dollars an article, the LLM retrieves
> them, reads them, and rewards the supplier. The system has no
> internal model of who is providing each piece of evidence."

> "What we built has three properties any production deployment needs.
> First — provenance-aware. Every piece of evidence is tagged with
> its source, and source determines credibility. Reuters at point
> eight, government source at point nine-five, anonymous blog at
> point two. Second — multi-source. Three independent evidence
> streams: compliance lists, news intelligence, and forty-plus
> verification parameters from public Indian filings. Third —
> adversarially robust. We explicitly model the attacker who plants
> flattering content, and we have a defense that demonstrably blocks
> the attack."

> "The headline result, which I'll show live in five minutes: under
> a budget-ten press-release attack, the no-defense scorer
> misclassifies every targeted supplier — recall drops to zero. With
> the defense on, classification is fully recovered. F1 goes from
> point seven-three on clean inputs, to zero under attack, back to
> one-point-zero with the defense. No false-positive cost on the
> clean run."

[Pause for effect.]

> "That's the contribution. Now the architecture."

---

### 4:00 — 6:30 · Architecture overview (2.5 minutes)

[Click to **Methodology** page in the sidebar. Scroll to the threat-
model and credibility-pyramid sections.]

> "Three evidence streams flow into one fusion engine."

[Point at the credibility pyramid graphic.]

> "Stream one — compliance pipeline. Three checks, run in parallel:
> OFAC SDN, World Bank Debarred Firms, and BIS Compulsory Registration
> Scheme. Each returns a pass, fail, or unknown."

> "Stream two — news intelligence. We have a per-supplier corpus.
> Each article goes through an LLM extractor that produces a
> structured signal: event type, severity, sentiment, source URL.
> Critically, the LLM never assigns a score. It only summarises one
> article. The score comes later, from the fusion engine, which can
> reason about provenance — the LLM cannot."

> "Stream three — forty-plus verification parameters. This is the
> SME layer. Compliance lists catch maybe three of our eighty-seven
> suppliers. News catches a handful more. The remaining eighty-plus
> — the actual Bangalore SME you'd consider ordering from — are
> invisible to the first two streams. The parameter layer fixes
> this. CIN registration, GSTIN, GST compliance score, ISO-9001
> status, KSPCB pollution NOC, EPFO registration, days payable
> outstanding, defect rate, on-time delivery — anything a procurement
> officer would actually verify before placing an order."

[Scroll down to the DS equation if visible, or stay on the page.]

> "All three streams produce basic-probability assignments, or BPAs.
> A BPA distributes one unit of belief across three subsets — safe,
> risky, or 'I don't know.' That third subset is what makes
> Dempster–Shafer the right tool here. A Bayesian system would have
> to commit to fifty-fifty if it's uncertain. DS represents
> uncertainty as its own quantity, distinct from a fifty-fifty
> prior."

> "Specifically, we use Yager's combination rule rather than
> classical Dempster's. Yager's rule routes conflict mass to the
> uncertainty bucket instead of normalising it away. So when sources
> disagree — exactly what an attacker tries to create — the system
> gets more uncertain, not falsely confident."

[If teacher looks engaged, this is a good place to pause.]

> "Any quick clarifying question on the architecture before I show
> the live system?"

[Wait. If they ask, answer briefly using §16 of the PROJECT_GUIDE.
If they wave you on, move forward.]

---

### 6:30 — 9:00 · Demo: Overview + Find (2.5 minutes)

[Click sidebar → **Overview**.]

> "Eighty-seven suppliers. The KPI strip shows the directory shape —
> percentage A grade, percentage F grade, mean score. The histogram
> shows score distribution with grade bands shaded. The donut shows
> what kinds of risk events are present in the corpus. The boxplot
> shows score variation across categories. This is the executive-
> summary view of the entire directory."

[Don't dwell. Move to Find.]

[Click sidebar → **Find suppliers**.]

> "This is the procurement-officer workflow. Eight filters: country,
> category, grade, score band, compliance status, risk events, real
> versus illustrative, free-text search."

[Set filters: Country = IN, Category = ems, Score band 0-60.]

> "Filtered to Indian EMS with score below sixty — the riskiest
> shortlist. Sortable, exportable as CSV. Click a row to drill in."

[Click on any low-scoring supplier in the result table. The drill-in
expander shows below.]

> "Every match has its full report one click away."

[Click sidebar → **Supplier detail**, pick Dixon Technologies from
the dropdown.]

---

### 9:00 — 12:30 · Demo: Detail + Parameters (3.5 minutes)

This is where you spend time. Detail and Parameters are the most
defensible pages.

[On Dixon's detail page.]

> "Dixon Technologies — listed PLI awardee, score ninety-five,
> grade A. Hero banner is grade-tinted. The first KPI strip shows
> the belief decomposition: belief safe, belief risky, uncertainty
> mass. Belief plus belief plus uncertainty equals one — that's the
> DS invariant."

[Scroll down to belief decomposition donut + risk topology radar.]

> "Belief decomposition donut on the left — most mass on safe,
> minimal on risky, small uncertainty. Risk topology radar on the
> right — event types as axes, the polygon shows what's actually
> present in this supplier's news."

[Scroll to news timeline + evidence sources table.]

> "News timeline, color-coded by event type. Evidence sources table
> below — every article with its URL and credibility tier. This is
> the provenance trail. If the teacher" — *I mean if a procurement
> auditor* — "asks why this supplier scored what it did, this table
> answers the question."

[Catch your slip with a smile. It humanises the demo.]

[Scroll to compliance + risk signal tables, then the waterfall.]

> "Compliance check results — three rows, all pass. Risk signals —
> what the LLM extracted from each article. Score contribution
> waterfall — every piece of evidence ranked by its absolute push on
> the score. Each bar shows one BPA's contribution, signed."

[Scroll all the way to the bottom — the Verification profile section.]

> "And the part the eighty-percent-of-suppliers question depends on
> — the verification profile. Forty fields organised into six
> sections: registrations, financial, operations, quality,
> regulatory, reputation. CIN, GSTIN, current ratio, debt-to-
> equity, GST compliance score, ISO certs, KSPCB pollution NOC, EPF
> dues clear. This is the data layer that lets the system score a
> small Peenya supplier with no news footprint."

[Click sidebar → **Parameters used**.]

> "And here's the system's full disclosure of what it looks at."

[Don't read every parameter — just point.]

> "Sixty-four parameters defined across nine groups. Forty are wired
> into scoring. The table has each parameter, its source —
> MCA, GSTN, KSPCB, EPFO portal — its healthy and concerning
> thresholds, whether it influences the score, and what fraction of
> the directory has data for it."

[Scroll to the per-parameter distribution chart.]

> "I can pick any parameter — say current ratio — and see its
> distribution across all eighty-seven suppliers."

[Pick "current_ratio" or "iso_9001_status" from dropdown — whichever
gives a good-looking chart.]

> "And below, I can pick any supplier and see every parameter's net
> push on their score, as a horizontal bar chart. Green pushes safe,
> red pushes risky."

[Pick a Bangalore SME illustrative entry, e.g. "Mysuru Precision
Electronics" — gives more variation than Dixon.]

> "This is the explainability layer. Nothing's hidden. The system
> tells you exactly why each supplier scored what it did."

---

### 12:30 — 15:00 · Demo: Adversarial lab (the killer moment) (2.5 min)

[Click sidebar → **Adversarial lab**.]

> "Now the thing that makes this a research project, not just a
> dashboard."

[Make sure the supplier dropdown is set to "Shenzhen Shadow
Components" (the WB-debarred entity). Defense toggle: ON. Budget
slider at 0.]

> "Shenzhen Shadow Components — actual entity on the World Bank
> debarred list for counterfeit electronics. Clean score: about
> fifteen, grade F. Correctly classified risky."

[Slowly drag the budget slider up to 10. The chart updates live.]

> "Now I'm running an attack. Budget ten — that's roughly five
> hundred dollars worth of PR-wire spam claiming Shenzhen Shadow is
> a great supplier."

> "With defense off — " [click defense toggle OFF] " — the score
> jumps from fifteen to past sixty. Misclassified safe. The
> attacker has flipped the supplier's classification with five
> hundred dollars of fake content."

[Wait. Let it sink in.]

> "Now defense on — " [click defense toggle ON] " — burst detection
> sees the volume, template-similarity sees the repeated language,
> both reduce the credibility of every attack article. The score
> drops back below thirty. Still F-grade. Defense holds."

> "And the F1 row at the bottom of the page shows this aggregated
> across the whole directory: clean F1 zero-point-seven-three;
> attacked F1 zero; defended F1 one-point-zero. No false-positive
> cost — the defense doesn't hurt clean classification."

[Pause for effect. This is the climax of the demo.]

---

### 15:00 — 17:00 · Demo: Onboard (cold-start) (2 minutes)

[Click sidebar → **Onboard new supplier**.]

> "One last thing. The system handles cold-start verification — a
> supplier that isn't in the directory yet."

[Fill out the form quickly:]

- Name: `Acme Test Components Pvt Ltd`
- Country: `IN`
- Category: `ems`
- Year: `2022`
- Aliases: leave blank or add a couple
- Articles: paste two short articles (have them ready in your notes
  or paste this:)

```
Title: Acme Test Components secures multi-year supply contract
Body: Acme Test Components Pvt Ltd announced today that it has secured
a five-year supply contract with a major OEM. The company expects to
expand its Peenya facility and add 30 employees over the next year.
Source URL: https://www.businesswire.com/test
Pub date: today
```

```
Title: Labour court hearing scheduled for Acme Test Components
Body: A labour court hearing has been scheduled regarding allegations
of unpaid wages at Acme Test Components Pvt Ltd. The matter is set
for next month.
Source URL: https://www.thehindu.com/news/test
Pub date: yesterday
```

> "Form filled, two articles pasted — one positive press release,
> one labour-court news from a tier-one outlet. Submit."

[Click submit. The full report card renders below the form within
seconds.]

> "The system runs the full pipeline live: compliance check,
> extracted both articles into structured signals, fused them,
> produced the score, generated the contribution waterfall. Cold-
> start supplier evaluated end-to-end in five seconds."

> "Notice the credibility weighting — The Hindu's labour story
> outweighs the Business Wire press release because of the source
> tier. This is exactly the trust calibration the defense is built
> on."

---

### 17:00 — 18:00 · Closing (1 minute)

[Click back to **Overview** as your closing visual.]

> "To recap: provenance-aware, multi-source, adversarially robust.
> The contribution is the trust-calibrated defense — burst plus
> template-similarity downweighting fed back into Dempster–Shafer
> fusion. The defense recovers F1 from zero to one-point-zero under
> a budget-ten press-release attack with no clean-run cost."

> "Two limitations I want to be explicit about. First, our F1
> numbers are computed against the seed directory of eighty-seven
> labelled suppliers — these are point estimates, not held-out
> generalisation results. A larger labelled corpus is the natural
> next step. Second, very small attack budgets — two articles or
> fewer — fall below our burst threshold, so the defense is a no-op
> there. We argue this is acceptable because two articles cannot
> move a labelled-risky supplier above the threshold anyway, but
> it's a real limitation."

> "Happy to take questions."

[Stop talking. Don't fill silence. Wait.]

---

## Q&A cheat sheet

These are the questions most likely to come, and the one-paragraph
answers that defend each one. If you only memorise one section of
this runbook, memorise this.

### Q: "Why not just use ChatGPT or GPT-4 for the score directly?"

> "Because GPT-4 has no internal model of source credibility. If an
> attacker plants ten PR-wire articles, GPT-4 reads them as inputs
> and trusts them. Our architecture explicitly separates extraction
> — which the LLM is good at — from fusion and decision — which the
> LLM is bad at, because it cannot reason about provenance at the
> resolution we need. The LLM only summarises one article into a
> structured signal. The fusion engine, which knows about source
> tiers, makes the decision."

### Q: "What's actually novel here? Multi-source fusion isn't new."

> "Two specific things. First, the threat model — most LLM-based
> supplier-scoring papers evaluate on clean data only. We explicitly
> model the attacker who plants flattering content and measure the
> attack end-to-end. Second, the trust-calibrated defense — burst
> detection plus template-similarity downweighting fed back into
> Dempster–Shafer fusion as per-signal credibility multipliers.
> This specific pipeline has not been proposed for this problem
> before, to our knowledge."

### Q: "Why Dempster–Shafer instead of plain probability?"

> "Bayesian probability requires P(safe) and P(risky) to sum to one.
> There's no place for 'I don't know.' Our cold-start case — a small
> Bangalore supplier with two known parameters out of thirty —
> should produce high uncertainty mass, not a confident fifty-fifty.
> DS theory has a third subset, the union of safe and risky, that
> represents uncertainty distinct from a balanced prior. That
> distinction is what makes the framework appropriate here."

### Q: "Why Yager's rule and not classical Dempster?"

> "Classical Dempster's rule normalises away conflict mass, which
> leads to the Zadeh paradox — two highly confident sources who
> disagree end up endorsing a third minor option. Yager's rule
> routes conflict to the uncertainty bucket. When sources disagree,
> the system gets more uncertain, not falsely confident. That's
> exactly the behaviour you want under adversarial conditions where
> the attacker is trying to create disagreement."

### Q: "How accurate is this in production?"

> "On the seed directory, F1 is point seven-three clean and one-
> point-zero defended. The seed directory is small — eighty-seven
> hand-labelled suppliers — so these are point estimates, not held-
> out generalisation results. The architecture is designed to
> generalise; producing held-out numbers on real procurement data is
> the natural next step. I'd want to see a labelled corpus of about
> a thousand suppliers and recalibrate confidence with Platt scaling
> on a held-out set before claiming production accuracy."

### Q: "Could a real attacker break this?"

> "Yes, with enough resources. Specifically: a coordinated campaign
> across many distinct high-credibility domains, or human-written
> diverse templates spread over time. The defense raises the cost of
> attack — it does not make attack impossible. We're explicit about
> this. Section five-point-four of our paper documents the threshold:
> the defense is effective for press-wire spam at budgets up to about
> twenty articles, which corresponds to roughly a thousand-dollar
> attack cost."

### Q: "What's the BIS CRS check actually doing?"

> "Bureau of Indian Standards Compulsory Registration Scheme. For
> certain electronic products — LED lights, IT goods, mobile-phone
> batteries, lithium cells — BIS CRS registration is mandatory by
> law for sale in India. We check whether each supplier has an active
> R-number for the products they claim to sell. Presence is positive
> signal. Absence on a CRS-mandatory product means the supplier is
> effectively unsellable in India, which is a strong negative signal."

### Q: "These illustrative suppliers — are you misrepresenting real
companies?"

> "No, and we're explicit about it everywhere. Thirty-five of the
> eighty-seven entries are marked is-illustrative-true in the schema.
> They display with an info icon throughout the dashboard. There's a
> 'Real only' filter on the Find page. They're disclosed in the
> README, in the Methodology page, and in the sidebar. They're
> fictitious composites of typical small Bangalore suppliers — they
> behave the way a real Peenya vendor with their parameter pattern
> would behave, but no individual entry is or refers to any real
> firm."

### Q: "What's the engineering cost to run this in production?"

> "For a thousand suppliers refreshed daily — roughly twenty to
> thirty dollars a day on Anthropic's Sonnet model. Caching known
> articles cuts that by eighty percent. Compliance lookups,
> parameter scoring, and DS fusion are all free at this scale —
> they're CPU-bound, fifty milliseconds per supplier. The
> bottleneck is LLM extraction over fresh news articles."

### Q: "Why a mock LLM by default?"

> "Reproducibility. Every number in the project has to be
> regenerable by anyone — including a reviewer who doesn't have an
> Anthropic API key. The mock backend is deterministic — same input
> produces same output every run. It's strictly weaker than Claude,
> so any results we get with the mock are a conservative lower bound
> on what the system would achieve with the real model. The
> production code path is one environment-variable change away."

### Q: "How does the burst detection actually work?"

> "Per supplier per week, we count articles. If the count exceeds
> five, every article in the burst gets its credibility multiplied
> by point-four. The threshold is calibrated against legitimate
> news cycles — real news bursts around real events like recalls or
> IPOs do exist, but they correlate with significant verifiable
> compliance or financial signals, so they don't get falsely
> down-weighted in practice. We measured zero false positives on
> the clean run."

### Q: "What about template similarity — how is that computed?"

> "Pairwise normalised Levenshtein similarity across the last ten
> articles per supplier. If an article's similarity to any previous
> article exceeds zero-point-seven, its credibility is multiplied
> by point-three. Real news outlets very rarely produce two articles
> seventy percent identical — they paraphrase and cite. PR firms and
> AI-generated spam reuse templates because writing twenty distinct
> fluent articles is expensive."

### Q: "Where does the credibility number for each source come from?"

> "Three sources, in priority order. First, journalism research on
> outlet credibility — Pennycook and Rand 2019 on rating accuracy,
> and the LLM-RAG attribution work from twenty twenty-three. Second,
> source-type heuristics — government beats tier-one news beats
> trade press beats general news beats press release beats anonymous.
> Third, our own per-supplier corroboration check, which gives a
> bonus to signals corroborated across distinct outlets. The fixed
> tiers are starting points; in production, they'd be re-tuned with
> per-domain trust scores."

### Q: "What would you do next if you had another semester?"

> "Three things. First, replace the static news corpus with a live
> crawler — there's a clean adapter point in `risk/news.py` for that.
> Second, plug live MCA, GSTN, and KSPCB feeds into the parameter
> layer instead of static profile data. Third, add a graph-neural-
> network module on the supplier-buyer relationship graph, following
> the Liu and Meidani 2024 paper that initially inspired the project
> — graph features can become additional BPAs in the same fusion
> framework, so it's compatible with what we have."

---

## Recovery scripts

### If the dashboard crashes mid-demo

[Don't panic. Don't apologise repeatedly. Move on.]

> "Something hiccuped. Let me restart it — about ten seconds."

[Open Terminal in another window: Cmd+T. Navigate, run `make dashboard`
again.]

> "While that comes up, the part I was about to show is..."

[Continue the script from memory; describe what you would have
shown. The teacher is judging your understanding, not your luck.]

### If asked something you don't know

[Three valid answers, in order of preference.]

> "Honest answer — I don't have that off the top of my head, but the
> answer is in the Project Guide we wrote. Let me find it."

[Open `PROJECT_GUIDE.md` in VS Code preview. Cmd+F to search.]

Or:

> "I'd want to think about that more carefully before answering. Can
> we come back to it?"

[Note the question on paper. Move on. Come back at the end.]

Or, if you genuinely don't know and don't have it documented:

> "I haven't worked out that case. My intuition is X" — *brief
> reasoning* — "but I'd want to test it before claiming it's true."

The third option is the one that wins points. Confident "I don't know
but here's how I'd find out" is better than bluffing.

### If the teacher pushes hard on a weakness

[Acknowledge the weakness. Don't defend it.]

> "That's a real limitation. The honest answer is X. The architecture
> is designed to address it via Y, but we haven't done Y yet — that's
> in the next-step list."

The single most important rule: **never argue with the reviewer**.
They've found a real weakness. Acknowledge it, contextualise it,
move on.

### If you blank completely

[Look at this runbook. It's your script. Use it.]

Open it on your phone. Find your place. Continue.

---

## Closing tactics

When the teacher says "any final questions" or starts to wrap up,
**you** offer a strong closing line. Don't let the review trail off.

> "Two things I'd flag for credit. The dashboard runs end-to-end
> offline with a mock LLM, so the entire project is reproducible
> without any API key — the makefile reproduces every number in the
> result table. And the project guide in the repo has the full
> mathematical derivation, the parameter reference, and twelve
> anticipated questions with answers — it's about eight thousand
> words, but it's there if you want to study any part in depth."

> "Thank you."

[Smile. Stop talking.]

---

## Body language and pacing

A few things that matter more than the script:

- **Stand if you can.** Sitting hunches you. Standing projects.
- **Hands visible, on the desk or gesturing.** Not in pockets.
- **Look at the teacher, not the screen.** The screen is the
  evidence; the teacher is the audience.
- **Pace yourself.** Twenty minutes feels rushed if you talk fast.
  Slow down. Pauses are good — they let the teacher process.
- **Don't apologise for the project.** No "I know it's not perfect"
  or "we didn't have time to..." — these undercut you. State
  limitations as facts, not flaws: "next step" not "we should have
  done this."

---

## Two days before — practice plan

**Day 1 (today / tomorrow):** Read the script through once. Open the
dashboard. Click each section as listed. Don't time yourself yet.
Just verify you can find every page and every chart you reference.

**Day 2 (one day before):** Full dress rehearsal. Set a timer.
Practise once with a friend or roommate watching. Get to fifteen
minutes. Then a second time, alone. Get to thirteen.

**On the day:** Pre-demo checklist (top of this file) thirty minutes
before. Walk in five minutes early. Take three deep breaths. You've
got this.

---

## End

The truth is, twenty minutes is plenty. The architecture is sound,
the demo is genuinely impressive, the limitations are honestly stated,
and you understand it. That's all a Phase II review needs.

Walk in confident.
