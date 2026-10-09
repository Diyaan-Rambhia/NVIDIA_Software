# 09: Open Questions for the Finance Advisor

Every unresolved finance, regulatory and data question, in one place. Priority: **P1** blocks design decisions early; **P2** needed before the feature is finalized; **P3** needed before any real launch. "Affects" says which part of the system changes with your answer. Please write answers in the last column or reply by number.

## A. Scope, audience and product

| ID | Pri | Question | Why it matters | Affects | Answer |
|---|---|---|---|---|---|
| Q-A-1 | P1 | Is the retail/institutional split and the feature assignment right: F1 for institutions only, F2 for retail only, F3 for both? | Defines access rules and the whole pitch | Plans, entitlements | |
| Q-A-2 | P1 | Who exactly are the institutional customers in India (AMCs, PMS, AIFs, insurers, treasuries, family offices, FPIs) and which would pay for F1? | Defines requirements and pricing | F1, pricing | |
| Q-A-3 | P2 | Would institutions also want F2, or retail want F1, in some form? | We chose strict segmentation | Plans | |
| Q-A-4 | P2 | What would make an institution trust the output (documentation, auditability, parameters, reproducibility)? | Shapes provenance and reporting | F1, outputs | |

## B. Regulatory (see `06`)

| ID | Pri | Question | Affects |
|---|---|---|---|
| Q-REG-1 | P1 | Does F2 (naming listed companies) amount to a research report requiring RA registration? | F2 design and wording |
| Q-REG-2 | P1 | Does F3's review of a user's own trades amount to investment advice? | F3 design |
| Q-REG-3 | P1 | Is F1 outside both regimes? Does selling to institutions change that? | F1 |
| Q-REG-4 | P1 | Does charging a subscription change the analysis? | All |
| Q-REG-5 | P1 | Required or advisable disclaimers and disclosures? | All outputs |
| Q-REG-6 | P2 | Rules on how we describe the product and on advertising? | README, video |
| Q-REG-7 | P2 | Any exemption or sandbox suitable for a hackathon prototype? | Scope |
| Q-REG-8 | P3 | If registration were needed for launch, which category and path? | Roadmap |
| Q-DP-1 | P2 | Consent and notice text for uploaded logs? | F3 |
| Q-DP-2 | P2 | Data-fiduciary duties at our scale? | F3, accounts |
| Q-DP-3 | P2 | Cross-border processing acceptable for this data class? | Hosting, model provider |
| Q-DP-4 | P3 | Under-18 users? | Accounts |
| Q-LIC-1 | P1 | May we use NSE/BSE/index data in a commercial analytics product, under which licence? | Data layer |
| Q-LIC-2 | P2 | May we store and show brief quotes from company transcripts? | F2 |
| Q-LIC-3 | P2 | Lowest-cost compliant data vendor if free sources are not acceptable? | Data layer, cost |
| Q-PAY-1..4 | P3 | GST registration timing, invoice format, refunds and lapse rules, institutional contract and TDS treatment | Payments |

## C. Feature 1: Contagion

| ID | Pri | Question | Affects |
|---|---|---|---|
| Q-F1-1 | P1 | Is the asset set in `03` §3 right for an institutional audience? What is missing (corporate bonds, spreads, REITs/InvITs, silver, copper)? | Universe |
| Q-F1-2 | P1 | Sensible defaults and bounds for the windows (estimation, baseline, gap, current, AR window) for Indian daily data? | Parameters |
| Q-F1-3 | P1 | Are the five episodes right? Better negative controls (calm and idiosyncratic periods)? | Validation |
| Q-F1-4 | P2 | Preferred multiple-testing control (or alternative to the bootstrap) when testing many pairs? | Statistics |
| Q-F1-5 | P2 | For each mechanism class in `03` §5: what evidence supports it and what contradicts it? | Explanation quality |
| Q-F1-6 | P2 | Index levels vs investable ETFs vs total-return series, which is acceptable for institutions? | Universe |
| Q-F1-7 | P2 | Timing alignment of US series (lag by one day?) given India's earlier close | Statistics |
| Q-F1-8 | P3 | What alert cadence, thresholds and report formats would institutions expect? | Product |

## D. Feature 2: Filings

| ID | Pri | Question | Affects |
|---|---|---|---|
| Q-F2-1 | P1 | Sector-aware thresholds for "strong" growth, margin tolerance, cash-conversion floors? | Rules |
| Q-F2-2 | P1 | Metric dictionary: standard definitions of revenue, EBITDA, operating profit, PAT, and how companies deviate? | Matching |
| Q-F2-3 | P1 | Standard adjusted-figure terminology and reconciliations in Indian results and calls? | Guard |
| Q-F2-4 | P2 | Lexicon additions, ambiguous words that should not trigger rules? | Lexicon |
| Q-F2-5 | P2 | Which 8 or so non-financial companies and which periods give a representative, fair evaluation set? | Evaluation |
| Q-F2-6 | P2 | Help labelling or reviewing the hand-labelled evaluation set? | Evaluation |
| Q-F2-7 | P2 | Acceptable wording about named companies from a defamation and regulatory view? | Outputs |
| Q-F2-8 | P3 | Is a banks/NBFC module realistic later? Which metrics? | Roadmap |

## E. Feature 3: Log advisor

| ID | Pri | Question | Affects |
|---|---|---|---|
| Q-F3-1 | P1 | Default benchmarks and the "same cash flow" replay convention | Returns |
| Q-F3-2 | P1 | Treatment of charges (brokerage, STT, stamp duty, exchange fees, GST) and whether tax is needed | Returns |
| Q-F3-3 | P1 | Institutional metrics: what would an Indian AMC or PMS expect? Mandate benchmarks? | Institutional scope |
| Q-F3-4 | P2 | Should time-weighted return be added? | Returns |
| Q-F3-5 | P2 | Confirm excluding futures and options from the MVP | Scope |
| Q-F3-6 | P2 | Mutual fund and SIP handling (NAVs, direct vs regular plans, consolidated statements) | Inputs |
| Q-F3-7 | P2 | Acceptable wording of reviews so they stay educational | Outputs |
| Q-F3-8 | P1 | Where can we get real, consented trade logs, and what is the cleanest way to obtain and anonymize them? | Inputs |

## F. Data

| ID | Pri | Question | Affects |
|---|---|---|---|
| Q-DATA-1 | P1 | Preferred free or low-cost source for NSE/BSE daily data acceptable for commercial use? | Data layer |
| Q-DATA-2 | P1 | Where to get NSE total-return index history? | Benchmarks |
| Q-DATA-3 | P2 | Point-in-time RBI, G-sec yield and FPI-flow data sources? | F1 |
| Q-DATA-4 | P2 | Preferred G-sec index or yield series as the "bond leg"? | F1 |
| Q-DATA-5 | P3 | Vendors with startup or academic pricing? | Cost |

## G. Pricing

| ID | Pri | Question | Affects |
|---|---|---|---|
| Q-PRC-1..8 | P2 | See `08_pricing_and_tiers.md` §6 | Plans |

## H. Parameters

| ID | Pri | Question |
|---|---|---|
| Q-PAR-1 | P1 | Review every row of `10_parameters_register.md`; mark each Accept, Change (give value) or Reject. |
