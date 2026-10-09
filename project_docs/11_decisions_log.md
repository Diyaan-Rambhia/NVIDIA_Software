# 11: Decisions Log

Every open question from `08` and `09`, with what was decided and by whom. The owner answered some directly and delegated the rest ("do whatever is best"); delegated items were resolved with the most conservative workable default and are marked so the advisor can review them.

**Status values**
- **Owner decided**: the owner gave the answer.
- **Adopted default**: the owner delegated; this is the recommended choice, working until the advisor says otherwise.
- **Provisional**: a placeholder needed to proceed, to be replaced.
- **TBD**: left open on purpose.
- **Needs professional**: cannot be settled by the team; a securities lawyer, tax professional or data-licensing contact must answer. The conservative working assumption is stated.

Labels: **[K]** team knowledge to confirm, **[V]** seen in public sources, **[P]** our proposal.

## A. Pricing and tiers (`08`)

| ID | Question | Decision | Status |
|---|---|---|---|
| D-01 | Q-PRC-1 billing period | Monthly | Owner decided |
| D-02 | Q-PRC-2 institutional trial | No free trial. Institutional features are paid-only. Institutions may use the retail-level free tier (F2 and F3 at retail-free limits) | Owner decided |
| D-03 | Q-PRC-3 verifying institutions | SEBI registration number, manually checked by an administrator against SEBI's published lists [K]. Entities regulated elsewhere (insurers, banks and treasuries, some funds) supply their own regulator's ID. Unregistered entities such as family offices go to manual review | Owner decided; extension adopted |
| D-04 | Q-PRC-4 contract terms | Click-through Terms of Service with limited liability, disclaimers and a liability cap; no custom contracts or purchase orders at launch. (The owner wrote "AOT"; interpreted as Terms of Service.) See `12` | Adopted default |
| D-05 | Q-PRC-5 annual plans | Later | Owner decided |
| D-06 | Q-PRC-6 GST and invoices | TBD. Store amount, tax and total as separate fields so GST can be added without redesign | TBD |
| D-07 | Q-PRC-7 refunds | TBD. In test mode no real money moves, so no refunds | TBD |
| D-08 | Q-PRC-8 lapse rule | At the end of a period without successful renewal the account returns to its segment's free plan; no grace period; no data deleted | Provisional |
| D-09 | Prices | Test-mode placeholders: `retail_paid` ₹499 per month; `institutional_paid` ₹24,999 per month. Not market-researched. Real prices are set before any live payment | Provisional |

## B. Scope and audience (`09` A)

| ID | Question | Decision | Status |
|---|---|---|---|
| D-10 | Q-A-1 is the split right | Yes: F1 institutional, F2 retail, F3 both | Owner decided |
| D-11 | Q-A-2 who are the institutions | All of them: AMCs, PMS, AIFs, insurers, treasuries, family offices, FPIs | Owner decided |
| D-12 | Q-A-3 cross-segment need | Not expected. Strict segmentation holds for paid features. The only crossover is that institutions can use the retail-level free tier | Owner decided |
| D-13 | Q-A-4 what builds institutional trust | Every result carries provenance (sources, parameters used, seed, code version); runs are reproducible; parameters are visible and adjustable; a methodology page explains each statistic; results are exportable as a report | Adopted default |

## C. Regulatory, privacy, licensing (`09` B; `06`)

The owner's instruction: **ensure limited financial and legal liability to us.**

| ID | Item | Working decision | Status |
|---|---|---|---|
| D-14 | Q-REG-1..8 | Cannot be answered by the team. Working assumptions, all conservative: treat F2's company-specific output as potentially research-like, so use neutral wording only and no views on the stock; treat F3 as potentially advice-like, so no buy/sell/hold language and no suitability; treat F1 as asset-class structure, not security recommendations. A securities lawyer reviews before any real user or any live payment | Needs professional |
| D-15 | Q-DP-1..4 | Process logs in memory by default; consent text and deletion on request if stored; remove identifiers. Consent wording, fiduciary duties and cross-border processing go to a lawyer | Needs professional |
| D-16 | Q-LIC-1..3 | Raw exchange and index data are never committed or exposed. Free sources only for the prototype. A licence check before any commercial launch | Needs professional |
| D-17 | Q-PAY-1..4 | No live payments until a legal entity exists and a professional has reviewed GST, invoices and refund policy | Needs professional |

How the team's own exposure is limited is set out in `12_terms_and_liability_framework.md`.

## D. Feature 1 (`09` C; `03`)

| ID | Question | Decision | Status |
|---|---|---|---|
| D-18 | Q-F1-4 multiple testing | Benjamini-Hochberg false-discovery-rate control across pairs at q = 0.10 | Adopted default |
| D-19 | Q-F1-1 universe | The asset set in `03` §3.1 stands. Add a corporate-bond spread if a free series is found. REITs and InvITs are excluded from the first build because of short histories. Healthcare and pharma stay excluded by project rule | Adopted default |
| D-20 | Q-F1-2 windows | Defaults and bounds in `10` accepted; all are user-configurable | Adopted default |
| D-21 | Q-F1-7 US timing | Lag US series by one day against Indian series (`us_series_lag_days` = 1, configurable), because India closes before the US opens [K] | Adopted default |
| D-22 | Q-F1-3 episodes | The five episodes in `03` §4. Two negative controls: a calm trending period and the early-2023 single-group shock. Tune on three episodes, hold out two (final split chosen before looking at results) | Adopted default |
| D-22a | Q-F1-6 index vs ETF vs TRI | Index levels are acceptable for monitoring co-movement; use total-return series where available; ETFs optional | Adopted default |
| D-22b | Q-F1-8 cadence | End-of-day batch scan after market close; exportable report. Real-time is deferred | Adopted default |

**Mechanism evidence guide (Q-F1-5, adopted default)**

| Mechanism | Evidence that supports it | Evidence that weakens it |
|---|---|---|
| Global risk-off with foreign outflow | US yields or dollar up, FPI net selling, rupee weaker, India VIX up, global equities down | FPIs buying, rupee stable, weakness concentrated in domestic names |
| Domestic liquidity or credit squeeze | Short rates and credit spreads up, financials leading losses, money-market stress | Calm funding rates, financials outperforming |
| Interest-rate shock | Sharp move in 10-year G-sec yield, bonds and rate-sensitive equities falling together | Stable yields |
| Currency stress | Rapid USD/INR rise preceding or accompanying equity and bond falls | Stable rupee |
| Commodity shock | Brent spike with rupee and bond weakness; oil-sensitive sectors lead | Stable crude |
| Policy or event shock | News of a specific policy, budget or election event; sharp, short, broad move | No identifiable event; slow-building move |
| Forced selling or liquidity scramble | Diversifiers (gold, bonds) fall with equities; volumes surge; broad indiscriminate declines | Diversifiers rising |

## E. Feature 2 (`09` D; `04`)

| ID | Question | Decision | Status |
|---|---|---|---|
| D-23 | Q-F2-1 thresholds | Default "strong growth" = 8% YoY, with starting sector overrides in `10` (FMCG 6%, IT services 8%, autos 10%, capital goods 12%, metals 10%, energy 8%, telecom 8%, consumer durables 10%). Guesses to be calibrated on labelled data | Adopted default |
| D-24 | Q-F2-2 metric dictionary | Revenue = revenue from operations. EBITDA = profit before tax + finance costs + depreciation and amortization − other income [K]. If the company states its own EBITDA, store it separately and compare like with like. Operating profit is not used unless the filing defines it | Adopted default |
| D-25 | Q-F2-3 adjusted-figure terms | adjusted EBITDA, adjusted PAT, before exceptional items, ex-exceptional, normalized, underlying, constant currency, excluding one-offs, ex Ind AS 116, ex forex gain or loss, like-for-like, organic | Adopted default |
| D-26 | Q-F2-4 lexicon | Add Indian-English commentary phrases to the lexicon. Ambiguous words never trigger a rule alone: resilient, stable, steady, consistent, satisfactory, healthy (without a number), in line with expectations | Adopted default |
| D-27 | Q-F2-5 companies | About 8 non-financial NSE large caps across FMCG, IT services, autos, capital goods, metals, energy, telecom and consumer durables; no financials; no healthcare or pharma. Specific names are chosen during the data feasibility check, based on whether XBRL results and transcripts can actually be retrieved. At least two fiscal periods each | Adopted default |
| D-28 | Q-F2-6 labelling | Two team members label independently and reconcile disagreements; the advisor reviews only the disputed cases | Adopted default |
| D-29 | Q-F2-7 wording | "Management's description appears inconsistent with the reported figure"; never "lied", "fraud" or "misleading"; every flag shows quote, figure and source; lawyer check before real users | Adopted default; legal check needed |
| D-30 | Q-F2-8 banks and NBFCs | Not in scope now. A later module would use net interest income, net interest margin, gross and net NPA, CASA ratio | Adopted default |
| D-30a | New rule R0 | Add "stated number" check: if management states a specific percentage on a reported basis, compare it with the filed figure (tolerance 0.5 percentage points) | Adopted default |

## F. Feature 3 (`09` E; `05`)

| ID | Question | Decision | Status |
|---|---|---|---|
| D-31 | Q-F3-1 benchmarks | Nifty 50 total return, a matched style or sector index, and a risk-free proxy. Replay convention as in `05` §5 | Adopted default |
| D-32 | Q-F3-2 charges and tax | Include charges when the log supplies them; no tax modelling in the first build | Adopted default |
| D-33 | Risk-free proxy | 91-day Treasury-bill yield | Adopted default |
| D-34 | Q-F3-3 institutional metrics | Beta, alpha, tracking error and information ratio against a user-selected benchmark (default Nifty 50 total return), plus sector contribution. Full Brinson-style attribution is later | Adopted default |
| D-35 | Q-F3-4 time-weighted return | Stretch goal after the MVP | Adopted default |
| D-36 | Q-F3-5 futures and options | Excluded from the first build | Adopted default |
| D-37 | Q-F3-6 mutual funds | First build covers direct equity and ETFs; mutual funds (NAV from AMFI) are a stretch goal | Adopted default |
| D-38 | Q-F3-7 review wording | Describe outcomes versus alternatives and observed behaviors; never "should have", buy, sell, hold or price targets; disclaimer on every review | Adopted default |
| D-38a | Q-F3-8 real logs | Team members' own broker exports and consenting friends or family. Use a written consent form and an identifier-removal checklist; store in `private/logs/` only | Adopted default |

## G. Data (`09` F; `07`)

| ID | Question | Decision | Status |
|---|---|---|---|
| D-39 | Q-DATA-1 source and cost | Free sources first (index-provider downloads, exchange downloads, yfinance for the prototype). If free sources fail, a low-cost vendor such as EODHD at roughly $20 per month [V; confirm]. Exchange-data licensing is checked before any commercial launch | Owner decided (free, low cost); detail adopted |
| D-40 | Q-DATA-2 total-return series | Download from NSE Indices; verify availability during the feasibility check | Adopted default |
| D-41 | Q-DATA-3 point-in-time macro | Use series as published by RBI, FBIL and NSDL; document that revisions are not tracked | Adopted default |
| D-42 | Q-DATA-4 bond leg | Use daily changes in the 10-year benchmark G-sec yield, sign-flipped so that "up" means bond prices rising, plus a gilt ETF or index price series if obtainable. Chosen finally in the feasibility check | Adopted default |
| D-43 | Q-DATA-5 vendors with startup pricing | Skip for now; free-first | Adopted default |

## H. Parameters and quotas (`09` H; `10`)

| ID | Item | Decision | Status |
|---|---|---|---|
| D-44 | All parameter defaults | Accepted as working values | Owner decided (delegated) |
| D-45 | Paid quotas and caps | `retail_paid`: F2 30 analyses per day; F3 10 logs per day and 500 trades per log. `institutional_paid`: F1 200 scans and 20 explanations per day; F3 50 logs per day and 5,000 trades per log; F2 at retail-free level. LLM requests: 10 per minute per account. Daily model budget: $1.00 to start, revised after the first cost report. Tavily: 3 searches per explanation | Adopted default |

## I. Still genuinely open

D-06 GST and invoices; D-07 refunds; D-08 and D-09 confirmation; D-14 to D-17 all regulatory, privacy, data-licensing and payment questions (need a professional); D-29 final wording of company-specific flags.
