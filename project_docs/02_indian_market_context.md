# 02: Indian Market Context

Background the team needs so that every design choice makes sense for India. Labels: **[V]** seen in a public source during research, **[K]** team knowledge to confirm, **[?]** unknown.

## 1. Market structure

- **Exchanges.** Equities trade on NSE and BSE; most large companies list on both and are identified by an NSE symbol and a BSE scrip code. [V] (company filings cite both)
- **Trading hours and calendar.** Regular session roughly 9:15 to 15:30 IST on weekdays, with exchange holidays (Diwali session aside) that differ from US holidays. All analysis aligns on the **Indian trading calendar**, never a US calendar. [K]
- **Settlement.** Cash-market settlement is T+1 (next trading day). [K]
- **Price bands and circuit breakers.** Individual stocks have daily price bands; the whole market has index-level circuit breakers that halt trading after large falls. These cap one-day returns and create odd data points the validator must recognize. [K]
- **Indices.** Headline: Nifty 50 (NSE) and Sensex (BSE). Broader and sector indices: Nifty Next 50, Midcap, Smallcap, Bank, IT, FMCG, Metal, Realty, Energy, and others. NSE publishes both price and total-return versions of many. [K]
- **India VIX.** NSE's implied-volatility index, a market-wide fear gauge. [K]

## 2. The macro system that moves Indian assets

| Driver | Why it matters to Indian assets | Typical stress signature |
|---|---|---|
| **RBI policy (repo rate, liquidity)** | Sets short rates; drives bond yields, bank and NBFC funding costs, rate-sensitive stocks | Rate shocks lift yields and hit bonds and rate-sensitive equities together |
| **FPI flows** | Foreign investors hold a large share of large-cap free float; their selling pressures equities, the rupee and bonds together | Equities down, INR weaker, bond yields up at once |
| **USD/INR** | Weak rupee raises import costs (oil, electronics), hurts foreign holders' returns | INR weakness often coincides with FPI outflows |
| **Crude oil (Brent)** | India imports most of its oil; higher oil worsens the current account and inflation | Oil spikes weigh on INR, bonds and oil-sensitive sectors |
| **US yields and the dollar** | Higher US yields and a stronger dollar pull capital away from emerging markets | Global risk-off hits Indian assets together |
| **Domestic credit and liquidity** | A funding squeeze at non-bank lenders can spread to banks, bonds and equities | A domestic liquidity shock raises short rates and spreads |
| **Domestic politics and policy events** | Elections, budgets, tax changes cause sharp short-lived moves | Short, sharp, broad moves |
| **Gold** | Traditional hedge and a household asset; priced in INR so it also moves with USD/INR | Often rises when INR weakens or risk-off hits |

## 3. Fiscal reporting calendar

- **Fiscal year:** April 1 to March 31. Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar. A label like "Q1 FY27" means April-June 2026. [V]
- **Result deadlines (LODR Regulation 33):** quarterly results within 45 days of quarter end and annual results within 60 days of year end. [K]
- **Audit status:** quarterly results are typically "limited review" or unaudited; annual results are audited. The product shall show the audit status where available. [K]
- **Standalone and consolidated:** most large companies publish both. [K]
- **Result formats differ by company type.** NSE publishes separate XBRL formats for Ind AS non-bank companies, banks, NBFCs, general insurers, life insurers and REITs/InvITs. [V] The MVP covers **non-financial Ind AS companies only**, because banks, NBFCs and insurers report on different line items (net interest income, asset quality, premiums) that our rule set does not handle.
- **Earnings calls:** SEBI requires listed companies to publish the audio or video recording of analyst and investor meets within 24 hours (or before the next trading day) and the transcript of post-earnings calls within five working days, on their websites and on the exchanges. [V] Quality and format of transcripts vary by company. [?]

## 4. Who the customers are

| Segment | Who | What they typically need from this product |
|---|---|---|
| **Retail** | Individual investors using Zerodha, Groww, Upstox, Angel One and similar brokers, plus mutual-fund SIP investors | Understand whether management commentary matches the numbers; honest review of their own trading |
| **Institutional** | Mutual fund houses (AMCs), portfolio management services (PMS), alternative investment funds (AIFs), insurers, treasury desks, family offices, possibly FPIs | Early warning when diversification stops working; defensible, evidence-backed explanations for risk committees; benchmark-relative review of portfolios |

[K] The advisor should confirm that this segmentation matches real market practice, and that F1 is more useful to institutions than to retail (the team's current belief), and that F2 is more useful to retail than to institutions (institutions have analysts who read filings and calls professionally).

## 5. Why India-specific design matters

- **Calendar and currency:** everything is INR and the Indian calendar; global series (US yields, oil) are inputs, never the subject.
- **Fiscal year:** a US-style calendar-quarter assumption would silently mislabel Indian periods.
- **Corporate actions:** bonus issues and stock splits are common in India. A log or price series that ignores them produces wildly wrong returns. [K]
- **Dividends and TRI:** dividend yields are meaningful for many Indian stocks; price-only benchmarks understate benchmark returns. [K]
- **Data availability:** India has no single free official API comparable to the US SEC's bulk data. Data collection is harder and more fragile (see `07_data_sources_and_quality.md`).
- **Regulation:** SEBI actively enforces against unregistered advice presented as education [V] (see `06_regulatory_and_compliance_india.md`).
