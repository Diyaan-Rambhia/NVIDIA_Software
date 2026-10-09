# 04: Feature 2, Filing Consistency Checker (retail): Finance Detail

Audience: retail investors. Labels: **[V]** seen in a public source, **[K]** team knowledge to confirm, **[?]** unknown, **[PROPOSED]** our choice for the advisor to accept or change.

## 1. The idea in plain language

A listed Indian company publishes (a) numeric results, and (b) management's commentary about them. Retail investors rarely cross-check one against the other. Feature 2 reads both for the **same fiscal period** and flags specific, checkable contradictions, for example management calling revenue growth "strong" when the reported figure grew by 2%. It then shows the quote beside the filed number so the investor can judge.

It is **not** sentiment analysis. It does not score the tone of language. It checks whether specific statements about a metric agree with that metric's reported value.

## 2. Sources and how Indian reporting works

### 2.1 Numbers
- Listed companies file results under SEBI LODR Regulation 33, quarterly and annually. [V] Results are filed in XBRL on NSE and BSE; individual filings can be downloaded from the exchanges and complete data series are sold by subscription. [V]
- **Result formats differ by company type** (Ind AS non-bank, banks, NBFCs, insurers, REITs/InvITs). [V] **Proposed MVP scope: non-financial Ind AS companies only.** Banks and financial companies are explicitly excluded because their key metrics (net interest income, net interest margin, gross and net NPA, CASA ratio, premiums, claims) are different and our rules do not cover them. [PROPOSED] The advisor should confirm the exclusion and say whether a later bank module is realistic.
- **Standalone vs consolidated.** Management commentary almost always refers to **consolidated** results for groups; a standalone figure placed beside a consolidated claim produces a false contradiction. The system keeps both labelled and only compares like with like. [K]
- **Fiscal calendar.** April-March. "Q1 FY27" = April-June 2026. Quarterly filings may show the quarter, the corresponding quarter of the previous year, the previous quarter, and cumulative figures; the Q4 quarter may need to be derived from annual minus nine-month cumulative. [K]
- **Units.** Figures are in INR crore, lakh or million depending on the company. The parser records units explicitly. [K]

### 2.2 Management language (same period)
- **Earnings press release** and **investor presentation**, filed with the exchanges. [K]
- **Earnings-call transcript and recording.** SEBI requires listed companies to publish recordings within 24 hours (or before the next trading day) and transcripts within five working days on their websites and the exchanges. [V] So transcripts are public; format and quality vary. [?]
- **Annual report "Management Discussion and Analysis"** is a further source for annual claims. [K] (not in the MVP)

## 3. What counts as a contradiction [PROPOSED]

A **claim** is a statement by management about a specific metric (for example "revenue grew strongly", "margins expanded", "cash generation was robust") for a specific period. A **candidate inconsistency** is a claim whose wording is incompatible with the reported number for that metric and period. The system uses explicit rules, not vibes.

| Rule | Management says | Reported numbers show | Why it matters | Base severity |
|---|---|---|---|---|
| **R1 Direction** | Metric rose or grew | Metric flat or down YoY or QoQ | The most basic mismatch | High |
| **R2 Magnitude** | Strong-intensity word (strong, robust, record, all-time high) about growth | Growth below a "strong" threshold | Intensity words imply a level of growth | Medium |
| **R3 Trend** | Accelerating or improving momentum or sequential improvement | Growth lower than the previous period's | Acceleration is a claim about change in growth | Medium |
| **R4 Profitability** | Margin expansion or improved profitability | Margin down YoY | Margins are what investors price | High |
| **R5 Cash quality** | Strong cash generation | Operating cash flow down YoY, or low conversion of profit to cash | Profit without cash is a warning sign | Medium |
| **R6 Working capital** | "Disciplined" inventory or "healthy" collections | Inventory growing far faster than revenue, or receivable days up materially | Working-capital build can precede write-offs | Low-Medium |
| **R7 Understatement** | Cautious word about a metric that improved strongly | Metric up well above the strong threshold | A mismatch in the other direction | Low (optional) |

**Thresholds** (what counts as "strong" growth, margin tolerance, conversion floors) are **sector-dependent** and are the single most finance-sensitive numbers in this feature. [?] Proposed starting point in `10_parameters_register.md` is deliberately conservative; the advisor should supply sector-aware guidance. For example, is 8% YoY revenue growth "strong" for an FMCG company? For an IT services company? For a capital-goods company?

## 4. The biggest source of false contradictions, and how we handle it

| Cause | Example | Handling |
|---|---|---|
| **Adjusted or normalized figures** | Management says "EBITDA margin expanded" using an adjusted EBITDA that excludes one-offs; the reported margin fell | **Adjusted-figure guard:** if the claim or its context uses adjusted, normalized, "before exceptional items", "ex one-offs" or constant-currency language, the candidate is downgraded or suppressed unless the reconciliation shows the same direction on the reported figure |
| **Standalone vs consolidated mix-up** | Claim about group, number from the parent only | Matching requires the same basis |
| **Different metric definitions** | "Operating profit" vs EBITDA vs EBIT | A metric dictionary maps phrases to defined line items; ambiguous phrases are not matched |
| **Different base period** | "Growth of 12%" refers to a half-year, number is quarterly | Claims carry their period and base; mismatches rejected |
| **Segment-level statements** | "Our export business grew strongly" vs company-level revenue | Segment claims are not matched to company-level numbers |
| **Relative statements** | "Strong versus the industry" | Relative claims need peer data; they are skipped in MVP |
| **EBITDA is not a formal Ind AS line** | Companies compute it differently | Both company-reported and our derived EBITDA are stored and labelled; the checker uses the company's own stated EBITDA if given |

The advisor's review of this table is critical: every missed cause becomes a false accusation against a company.

## 5. Language lexicon [PROPOSED, K]

A configuration file maps words to categories. Illustrative content for Indian management commentary:
- **Strong-intensity positive:** strong, robust, record, all-time high, outstanding, healthy (when used about growth), best-ever, significant growth, double-digit.
- **Accelerating:** accelerated, picked up, gained momentum, sequential improvement.
- **Cautious:** muted, soft, subdued, challenging, headwinds, moderated, resilient (ambiguous).
- **Direction words:** grew, increased, expanded, improved, declined, contracted, de-grew.
- **Margin words:** expansion, improvement, bps.
The advisor should add the idioms used in Indian earnings calls and mark ambiguous words ("resilient", "stable", "steady") that should **not** trigger rules.

## 6. How the LLM is used, and the guardrails

1. **Extraction (Nemotron Nano):** pulls out claims as exact quotes with offsets, the metric named, the period, and whether the basis is reported, adjusted or constant-currency.
2. **Rules (deterministic):** match each claim to the reported value and apply R1-R7.
3. **Adjudication (Nemotron Ultra):** for each candidate, say confirm, downgrade or reject, and what benign explanation was considered. **It cannot invent new candidates.**
4. **Verifier (deterministic):** a flag is shown only if the quote exists verbatim in the source, every quoted number matches the filed number, and the period and basis match.
This design keeps accusations traceable: a retail user always sees the exact sentence and the exact filed number.

## 7. What the user sees

For each flag: the quote; the metric, period and basis; the filed value and the comparison value; which rule fired; severity; the adjudicator's explanation including the benign explanation considered; a link to the source document. A banner states that this is educational analysis of disclosures, not a statement that the company has done anything wrong, and not advice about the stock.

**Wording discipline:** the product says "management's description appears inconsistent with the reported figure" and never "the company lied", "fraud" or "misleading". [PROPOSED; legal review requested, see `06`]

## 8. Evaluation plan

Humans hand-label 15-20 company-periods (is each claim consistent or inconsistent with the filing?). We report **precision** (of the flags shown, how many are real) and recall, and prioritize precision. Proposed target: precision ≥ 0.80 on displayed flags. [PROPOSED] The advisor is asked to help choose companies across sectors and to review or label disputed cases.

## 9. Known limitations

- Rules capture only simple, checkable claims; much commentary is vague or forward-looking and is ignored.
- Sector differences make a single threshold crude.
- Transcript text from audio may contain transcription errors.
- Companies correct, restate and reclassify; we use figures as filed for the period.
- Only non-financial Ind AS companies are supported in the MVP.

## 10. Questions for the advisor (see also `09`)

Q-F2-1 sector-aware thresholds; Q-F2-2 metric dictionary and definitions (EBITDA); Q-F2-3 adjusted-figure terminology and standard reconciliations; Q-F2-4 lexicon additions and ambiguous words; Q-F2-5 which companies and periods; Q-F2-6 bank and NBFC scope later; Q-F2-7 acceptable wording about companies (legal risk).
