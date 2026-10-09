# 05: Feature 3, Investment Log Advisor (retail and institutional): Finance Detail

Labels: **[V]** seen in a public source, **[K]** team knowledge to confirm, **[?]** unknown, **[PROPOSED]** our choice for the advisor.

## 1. The idea in plain language

Take the user's real record of trades. Work out how they actually did. Then answer: "What if the same rupees had gone in and out on the same days into something simple, like an index?" Then review whether the **process** was sound, which is different from whether the outcome was good. The output explains its reasoning and does **not** tell the user to buy, sell or hold anything.

## 2. Two scopes

| | Retail scope | Institutional scope |
|---|---|---|
| **User** | Individual investor | Portfolio manager, desk, family office, small AMC/PMS analyst |
| **Input** | Broker trade book or similar export; mutual fund holdings (optional) | Larger trade blotter or holdings file; many tickers; possibly multiple benchmarks |
| **Volume limits** | Small (free: up to 20 trades per log; paid: larger) | Much larger |
| **Return measures** | XIRR; benchmark replays | XIRR; benchmark replays; benchmark-relative statistics |
| **Process metrics** | Concentration, holding periods, entry after run-ups, drawdown, turnover, disposition effect | Same, plus sector contribution and cost estimates |
| **Tone** | Educational, behavioral | Analytical, benchmark-relative |

[PROPOSED] The institutional scope is the team's guess at what a professional wants. The advisor should say what institutional users actually expect (for example attribution against a mandate benchmark, tracking-error budgets, factor exposures).

## 3. Inputs: real logs only

The project policy is **real trade logs only**: broker exports from team members or volunteers with written consent and identifiers removed. [PROPOSED] Typical Indian sources: broker tradebook or contract-note exports and consolidated account statements for mutual funds. [K] The exact column layouts differ by broker; a language model proposes a column mapping that the user must confirm.

Minimum fields: date, symbol, side (buy/sell), quantity, price. Optional: charges, exchange, segment (delivery, intraday, F&O).

**Out of MVP:** futures and options. They require margin, expiry, lot sizes and mark-to-market logic. [PROPOSED] Equity delivery and ETF trades and mutual-fund purchases only. The advisor should confirm this is the right cut, noting that regulator studies report heavy losses among individual F&O traders [K], which is a tempting but complex use case.

## 4. Return measures

- **XIRR (money-weighted).** Solves for the annualized rate that equates all cash flows (buys negative, sells positive, plus the present value of holdings). This is the measure Indian platforms and mutual-fund investors know. [K] It reflects the investor's own timing.
- **Time-weighted return (optional later).** Removes cash-flow timing; useful for comparing a manager to a benchmark.
- **After-cost and after-tax.** Brokerage, STT, stamp duty, exchange charges and GST on brokerage reduce returns; tax on gains does too. [K] **MVP:** use charges if the log supplies them; **no** tax modelling. [PROPOSED] The advisor should say whether after-tax comparison is essential (rates and holding-period rules have changed in recent years [K]).
- **Corporate actions.** Bonus issues and splits change quantities and prices; ignoring them gives nonsense returns. The system adjusts using action records, and reports any it cannot resolve. [K]

## 5. Benchmarks (the "what else could I have done" alternatives) [PROPOSED]

| Benchmark | Reason | Note |
|---|---|---|
| **Nifty 50 total return** | The default "just buy the index" alternative | Total return, so dividends are included |
| **Style or sector index matched to holdings** (for example Nifty Next 50, Midcap, Bank) | A fairer comparison for someone holding mid caps or banks | Chosen from the log's holdings |
| **Risk-free proxy** (short-term T-bill or liquid-fund rate) | "What if I had not taken equity risk at all?" | Source for the Indian short-term rate is TBD |
| **Optional:** gold, a bond index | Alternative asset-class choices | Advisor to say whether to include |

**Replay logic.** Each rupee the user invested on a date is invested in the benchmark that day; each sale proceeds are withdrawn from the benchmark. If the replay would sell more than it holds, it flags the result as partial. [PROPOSED] The advisor should check this convention against industry practice for "same cash flow" comparison.

**Hindsight risk.** Almost any alternative looks better or worse after the fact. The review therefore reports *relative results* and *process*, and never says "you should have bought X".

## 6. Process metrics (retail and institutional)

| Metric | What it tells you | Definition |
|---|---|---|
| **Concentration (HHI)** | Whether the portfolio depended on a few names | Sum of squared position weights over time |
| **Holding-period distribution** | Churning versus patience | Days between buy and sell per lot |
| **Entry after run-up** | Chasing performance | Share of buys made when the stock's trailing 20-day return was in its own top decile [PROPOSED threshold] |
| **Maximum drawdown** | Pain experienced | Worst fall from a peak in portfolio value |
| **Turnover** | Trading intensity and cost drag | Traded value over average portfolio value |
| **Disposition effect (PGR vs PLR)** | Selling winners early, holding losers | Odean's proportions of gains realized versus losses realized on sale days [V] |

**Ex-ante framing.** A decision is judged only on what was knowable on its date (position size, diversification, volatility and momentum at entry). Later prices alone do not make a past decision good or bad. [PROPOSED]

## 7. Institutional metrics (to be confirmed) [PROPOSED]

- **Beta and alpha** against a chosen benchmark (regression of portfolio returns on benchmark returns).
- **Tracking error** (volatility of the active return) and **information ratio** (average active return divided by tracking error).
- **Sector contribution** to relative performance.
- **Implementation cost** from supplied charges.
The advisor should replace or extend this with what an Indian AMC or PMS would expect, including mandate-specific benchmarks.

## 8. What the review says and does not say

**Says:** how the outcome compares with the alternatives; which behaviors in the log are statistically common pitfalls (concentration, performance chasing, premature selling of winners); what was and was not within the investor's control; what the numbers cannot tell us.

**Never says:** buy, sell, hold, price targets, "you should have", suitability for the user's goals or risk tolerance. [PROPOSED; this is the legal boundary in `06`] A disclaimer appears on every review.

## 9. Privacy

Trade logs are personal financial data under India's data-protection law. [K] Default: processed in memory and not stored. Storing requires explicit consent, a stated purpose and deletion on request. Public use of any real log (including in the demo video) requires the owner's explicit written consent and removal of identifiers. See `06`.

## 10. Known limitations

- Index replay ignores taxes and liquidity.
- A short log gives weak statistics; the review says so.
- Mutual-fund and ETF logs differ from direct-equity logs; corporate-action handling is only as good as the action data.
- Behavioral metrics are indicative, not diagnostic.

## 11. Questions for the advisor (see also `09`)

Q-F3-1 benchmarks and replay convention; Q-F3-2 treatment of charges and taxes; Q-F3-3 institutional metrics; Q-F3-4 whether to add time-weighted return; Q-F3-5 F&O exclusion; Q-F3-6 mutual-fund handling; Q-F3-7 acceptable wording of reviews; Q-F3-8 suggested sources of real logs.
