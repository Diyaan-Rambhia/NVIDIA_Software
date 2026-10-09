# Finance Documentation: Start Here

## Why this folder exists

The team that is building this platform is strong in software and **not** in finance. Every finance decision in the project (which assets to analyze, how to define a "contradiction" in a company's disclosures, which benchmark to compare a trader against, what we may legally say to users) was made by non-specialists using public sources and general knowledge. This folder writes all of it down in plain language so that a finance professional can review it, correct it, and fill the gaps.

**Nothing in here is final until the advisor confirms it.** Everything the advisor changes will be reflected in configuration files (`config/`), not in code, so corrections are cheap.

## What the product does, in finance terms

An India-focused analytics platform with two customer segments and three features.

| Feature | Customer | Finance question it answers |
|---|---|---|
| **F1 Contagion Detector** | Institutions only (asset managers, PMS/AIF managers, insurers, treasuries, family offices) | "Are assets that normally move independently starting to move together, is that real, and what plausible mechanism explains it?" |
| **F2 Filing Consistency Checker** | Retail only | "Does what management *says* about a period match what the company *reported* for that same period?" |
| **F3 Investment Log Advisor** | Both | "Given my actual trades, how did I do against sensible alternatives, and was my *process* sound, separately from luck?" |

Everything is for India: NSE and BSE, INR, IST, April-March fiscal years, SEBI regulation.

## How to review (suggested order for a time-limited advisor)

1. Read this file, then `06_regulatory_and_compliance_india.md`. **Highest stakes**: it defines what the product may and may not say.
2. Answer the priority questions in `09_open_questions_for_advisor.md` (marked **P1**).
3. Skim `03`, `04`, `05` (one per feature) and mark errors directly in the text.
4. Fill in or correct values in `10_parameters_register.md`.
5. Pricing (`08`) and glossary (`01`) can be reviewed last.

## Files

| File | Content |
|---|---|
| `01_glossary.md` | Every finance term used, in plain language, with India-specific meanings |
| `02_indian_market_context.md` | How Indian markets, rates, currency, flows and fiscal reporting work |
| `03_feature1_contagion_finance.md` | Correlation, contagion, the Indian asset universe, macro drivers, episodes, mechanism taxonomy |
| `04_feature2_filings_finance.md` | Ind AS reporting, result formats, metrics, the contradiction rules, language lexicon |
| `05_feature3_log_advisor_finance.md` | Return measures, benchmarks, process metrics, retail and institutional scopes, Indian trading costs and taxes |
| `06_regulatory_and_compliance_india.md` | SEBI rules, what counts as advice, privacy, data licensing, payments and GST |
| `07_data_sources_and_quality.md` | Every data source, finance-specific data-quality traps |
| `08_pricing_and_tiers.md` | Segments, tier logic, unit economics (no prices set yet) |
| `09_open_questions_for_advisor.md` | Numbered questions with why each matters |
| `10_parameters_register.md` | Every numeric parameter and threshold, current default, rationale, status |

## Status labels used throughout

| Label | Meaning |
|---|---|
| **[V]** | Seen in a public source while researching this project. Still worth a glance. |
| **[K]** | The team's general knowledge; **not verified**. The advisor should confirm or correct. |
| **[?]** | Genuinely unknown to the team. A decision or answer is needed. |
| **[PROPOSED]** | A choice the team made so that work could proceed. The advisor should accept, change or reject. |

## Boundaries the advisor should hold us to

- The product gives **analysis and education only**. It must never tell a user to buy, sell or hold a security, give a price target, or personalize advice. If the advisor believes a feature as designed crosses that line, we change the feature.
- We are not building trade execution, brokerage connections or a mobile app.
- Healthcare and pharmaceutical sectors are deliberately excluded from examples and universes (a hackathon rule on framing).
- Real-time and intraday data are deferred.

## What we need back

- Corrections to anything marked [K] or [PROPOSED].
- Answers to the P1 and P2 questions.
- Names of any sources, data vendors or professionals (for example a securities lawyer) you recommend we consult for the regulatory questions.
