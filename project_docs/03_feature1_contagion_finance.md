# 03: Feature 1, Contagion Detector (institutional): Finance Detail

Audience: institutions. Labels: **[V]** seen in a public source, **[K]** team knowledge to confirm, **[?]** unknown, **[PROPOSED]** our choice for the advisor to accept or change.

## 1. The idea in plain language

Portfolio managers build diversified portfolios assuming that, for example, Indian equities, government bonds and gold do not all fall together. That assumption is a statement about **correlations**. In a crisis the assumption can break: assets that normally move independently start moving together, and diversification stops protecting the portfolio. Feature 1 watches for that, checks whether the shift is genuine rather than a side effect of high volatility, and offers a ranked list of **plausible** reasons, each tied to numbers the system computed and to news it retrieved.

What it is **not**: a Value-at-Risk calculator, a price predictor, or a causal proof. It detects a change in the *structure* of co-movement and describes possible mechanisms.

## 2. The method, step by step, with the finance reasoning

### 2.1 Returns
Daily log returns from index or total-return series on the Indian trading calendar. [PROPOSED] Log returns are standard for compounding and statistics.

### 2.2 Correlation estimation over a **configurable window**
- A correlation is estimated from the last **W** trading days. Short windows react faster but are noisy; long windows are stable but slow. Because the right choice depends on the user's purpose (a trading desk wants fast; a risk committee wants stable), **W and every other window are user-configurable** within bounds. [PROPOSED defaults: W = 60, EWMA decay 0.94, baseline 250, gap 20, current 20.] The advisor should confirm sensible defaults and bounds (see `10_parameters_register.md`).
- **EWMA** (exponentially weighted) gives more weight to recent days. 0.94 is the long-standing RiskMetrics daily decay. [K]
- **Shrinkage** (Ledoit-Wolf) stabilizes estimates when there are many assets and few observations. [K]

### 2.3 Baseline versus current
The system compares correlation in a recent **current window** against a longer **baseline** window that ends a few days earlier (the **gap**), so the "new" period does not contaminate the "normal" one.

### 2.4 Why a raw correlation jump is not enough (the central finance point)
When markets become more volatile, measured correlation rises mechanically, even if the underlying relationship has not changed. If we flagged every rise we would flag every selloff. Forbes and Rigobon addressed this: they adjust measured correlation for the rise in volatility, and they conclude that much of what looked like contagion was in fact ongoing interdependence. [V]
- **Adjustment used:** `ρ* = ρ / sqrt(1 + δ(1 − ρ²))`, where δ is the relative increase in the shock market's variance. [V]
- **Known limits:** the adjustment assumes no omitted variables, no endogeneity and a stable relationship. Published critiques say these assumptions often fail. [V] So it is never used alone. We add:
  - **Rank (Spearman) correlation** as a robustness check; rank-based measures have been proposed as robust to the volatility bias. [V]
  - **Absorption ratio** (below).
- **Flag rule:** at least two of three signals must agree. [PROPOSED]

### 2.5 Absorption ratio
Kritzman and colleagues proposed measuring systemic risk by the share of total variance captured by a small number of principal components; a spike signals tighter coupling and they found it tended to precede drawdowns. [V] We compute the share explained by the first k components with k about one fifth of the number of assets [K, confirm against the paper], and a standardized shift comparing the last ~15 days to the prior year. [K] The advisor should confirm the parameter conventions and whether to use a covariance or correlation matrix.

### 2.6 Significance by bootstrap
To check that an observed correlation rise is larger than chance, we resample the baseline period many times (a block bootstrap, which preserves time dependence) and compare. With many pairs, some will look significant by luck, so a **multiple-testing control** is needed. [?] Choice pending (see Q-F1-4).

### 2.7 Attribution (what drove it)
1. **Cluster:** which assets account for most of the increase in average correlation.
2. **Common factor:** the first principal component, with each asset's loading.
3. **Macro association:** correlation between that common factor and daily changes in macro series (RBI repo and G-sec yield, India VIX, USD/INR, Brent crude, US 10-year yield, broad dollar index, FPI flows).
These are *associations*. The product says so.

### 2.8 Explanation by language model
An LLM (Nemotron) receives only the computed evidence items (each with an ID) plus retrieved news, and writes 2-4 ranked hypotheses that cite those IDs and URLs. Checks reject invented numbers, invented sources and causal language ("caused", "because of"). It must describe what evidence would **weaken** each hypothesis.

## 3. The Indian universe [PROPOSED; the advisor's most valuable input]

### 3.1 Asset set (the series whose correlations are analyzed)
| Group | Candidates | Why |
|---|---|---|
| Large-cap equity | Nifty 50, Nifty Next 50 | Core Indian equity beta |
| Mid and small cap | Nifty Midcap, Nifty Smallcap | Typically more fragile in stress |
| Financials | Nifty Bank | Transmits funding and liquidity stress |
| Sector equity | Nifty IT, FMCG, Metal, Realty, Energy | Different macro sensitivities (exports/USD, defensives, global metals, rates, oil). **No healthcare or pharma** by project rule |
| Rates | G-sec index or a 10-year benchmark-yield-derived series | The bond leg of diversification |
| Gold | Domestic gold price in INR or a gold ETF | Classic diversifier, also INR-sensitive |
| Currency | USD/INR | Captures FPI and external stress |
| Commodity | Brent crude | India's key external input price |
| Global equity | A US large-cap index | Linkage with global risk appetite |

### 3.2 Macro-factor set (explanatory, not necessarily in the correlation matrix)
RBI repo rate and 10-year G-sec yield; India VIX; US 10-year yield; broad dollar index; Brent crude; FPI net flows; system liquidity; a corporate-bond spread if obtainable. [PROPOSED] Which of these can be obtained free and reliably is an open data question (`07_data_sources_and_quality.md`).

### 3.3 Questions the advisor should settle
- Is this the right set for an institutional audience, or are there asset classes institutions would expect (corporate bonds, AAA spreads, REITs/InvITs, sectoral credit, commodities like silver or copper)?
- Index levels versus investable ETFs: acceptable for a correlation analysis?
- Is ~10-15 series enough, too many or too few?

## 4. Candidate stress episodes [PROPOSED, K]

The method is tested by **replaying** history using only data available at each date. Episode windows are fixed in advance and not adjusted after seeing results.

| Episode | What happened (summary) | Dominant mechanism class |
|---|---|---|
| 2013 taper tantrum | Talk of reduced US stimulus triggered emerging-market outflows; the rupee fell sharply | Global risk-off, FPI outflow, currency stress |
| 2018 IL&FS default and NBFC squeeze | A large infrastructure lender defaulted; non-bank funding froze | Domestic credit and liquidity shock |
| 2020 COVID crash | Global liquidity crunch; even diversifiers sold | Global risk-off and liquidity scramble |
| 2022 tightening and FPI selling | Rapid global rate rises; large foreign outflows; weaker rupee | Rate shock, FPI outflow, currency stress |
| 2024 election-result volatility | A sharp, brief domestic market reaction | Domestic policy or event shock |

**Negative controls** (the method should *not* flag broadly): calm trending periods and an event hitting one business group rather than the whole market (for example the early-2023 shock to one large group). [K] The advisor should confirm episodes and suggest better controls. A method that flags crises but also flags calm is useless, so we report the **fraction of all days flagged**.

## 5. Mechanism taxonomy for the explanations [PROPOSED]

Hypotheses are categorized so the language model chooses from finance-literate classes rather than inventing stories:

1. **Global risk-off with foreign outflow** (US yields or dollar up, FPI selling, INR weaker, equities and bonds down together).
2. **Domestic liquidity or credit squeeze** (short rates and spreads up, financials and rate-sensitive stocks hit).
3. **Interest-rate shock** (G-sec yields move sharply; equity and bond legs both fall).
4. **Currency stress** (rapid INR depreciation spilling into equities and bonds).
5. **Commodity shock** (oil or metals spike affecting the external balance and inflation).
6. **Policy or event shock** (election, budget, regulatory change).
7. **Forced selling or liquidity scramble** (assets sold because they are liquid, not because of fundamentals; diversifiers fall too).

For each, the advisor should say what evidence would **support** and what would **contradict** it, so the model's "what would weaken this" statements are sound.

## 6. How institutions would use it, and how not to

- **Use:** a monitoring signal for risk committees; a prompt to review concentration, liquidity and hedges; a documented, evidenced narrative.
- **Do not claim:** that it predicts crashes, that it tells anyone to sell, or that mechanisms are proven. Until replay evidence shows lead time, wording stays at "regime detection".
- **Configurability:** institutions will want to set windows and thresholds; the parameter form exists for this and every result records the parameters used.

## 7. Known limitations (to be told to users)

- Correlation is backward-looking and noisy; short windows give false alarms, long windows give late alarms.
- Index data differs from tradable prices; liquidity and costs are ignored.
- Overlapping windows are not independent; apparent confirmation can be repeated information.
- Few episodes means weak statistical evidence about performance; we report misses.
- Macro associations are not causes; news retrieved may be incomplete or biased.

## 8. Questions for the advisor (see also `09`)

Q-F1-1 universe; Q-F1-2 windows and bounds; Q-F1-3 episodes and controls; Q-F1-4 multiple-testing control; Q-F1-5 mechanism taxonomy and what evidence supports each; Q-F1-6 institutional expectations (cadence, alerts, reporting format).
