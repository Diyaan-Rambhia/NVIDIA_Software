# 07: Data Sources and Data Quality

Labels: **[V]** seen in a public source during research, **[K]** team knowledge to confirm, **[?]** unknown. Technical specifics are in `PROJECT.md` §6.5; this file explains the *finance* meaning and the traps.

## 1. The honest picture

India has no single, official, free, well-documented API for prices and filings comparable to the US SEC's bulk data. [V] Consequences:
- Price data comes from unofficial libraries, index-provider downloads, or limited free tiers of commercial APIs. Endpoints change; one open-source NSE library notes that its index-history function currently does not work because endpoints may have changed or are rate-limited, and tells users to respect NSE's terms. [V]
- Filings: individual results are available in XBRL from the exchanges; complete series are sold by subscription. [V]
- Therefore the first build step is a **feasibility check** on real data before anything else relies on a source.

## 2. Source-by-source

| # | Source | Content | Used for | Cost / access | Risk |
|---|---|---|---|---|---|
| 1 | NSE Indices (niftyindices.com) | Index history, total-return indices, India VIX | F1 universe, F3 benchmarks | Free downloads [K] | Terms of use; manual or scripted download fragility [?] |
| 2 | yfinance (Yahoo) with NSE/BSE tickers | Daily prices for stocks, ETFs, some indices, adjusted for splits and dividends | F1, F3 | Free, unofficial [K] | Not an official feed; may break or be restricted; terms restrictive |
| 3 | Alpha Vantage | Daily series for BSE symbols (per a user report) | Fallback | Free tier 25 requests per day [V] | Coverage and currency of Indian data unverified |
| 4 | Twelve Data | Global daily data | Fallback | Free tier about 800 requests per day, coverage depends on tier [V] | Indian coverage on free tier unverified |
| 5 | EODHD and similar vendors | Global end-of-day including India | If free sources fail | Paid from about $20 per month [V]; free tier very limited | Cost against zero budget |
| 6 | NSE/BSE financial-results XBRL | Reported numbers in structured form | F2 | Individual filings free; bulk by subscription [V] | Access method, format by company type, throttling [?] |
| 7 | NSE/BSE announcements and company IR pages | Press releases, presentations, call recordings and transcripts | F2 | Free; mandated publication [V] | PDF extraction quality; inconsistent formats |
| 8 | NSE/BSE corporate-actions records | Splits, bonus, dividends, rights | F3 | Free via exchange pages [K] | Access method [?] |
| 9 | RBI (DBIE) and FBIL | Policy rate, G-sec yields, T-bill rates, INR reference rate, MIBOR | F1 macro, F3 risk-free | Free [K] | Access method and series IDs [?] |
| 10 | FRED (St. Louis Fed) | US yields, broad dollar index, Brent/WTI, global volatility | F1 macro | Free API key [K] | Series IDs and terms to confirm |
| 11 | NSDL (FPI) and NSE (FII/DII) statistics | Foreign and domestic institutional flows | F1 macro | Free [K] | Access method; reporting delay; definitions [?] |
| 12 | AMFI | Mutual fund NAVs | F3 (mutual funds, optional) | Free [K] | Format and history [?] |
| 13 | Real broker exports | The user's trades | F3 | From consenting people | Consent, privacy, format variety |
| 14 | Tavily | News and web results | F1 explanations | Free tier 1,000 credits per month [V] | Coverage, publisher copyright |

## 3. Finance-specific data-quality traps (and our response)

| Trap | Why it matters | Response |
|---|---|---|
| **Price index vs total return** | Comparing a user's dividend-inclusive return with a price-only benchmark understates the benchmark | Use TRI where available; label every series |
| **Adjusted vs unadjusted prices** | A bonus issue or split looks like a crash in unadjusted prices and ruins correlations and returns | Use adjusted series; validator flags suspicious one-day returns |
| **Corporate-action quantities in trade logs** | A 1:1 bonus doubles shares; logs recorded before the action appear to understate holdings | Adjust quantities from action records; report unresolved |
| **Survivorship bias** | Using today's constituents ignores delisted or removed companies | Use indices and ETFs for F1; note the limitation for single stocks |
| **Look-ahead bias** | Using information not available on the date (e.g. revised data, restated results, index membership) | No-lookahead tests; as-filed figures only |
| **Point-in-time macro data** | Macro series are revised; a replay using revised data cheats | Prefer as-published values; record vintage where possible; note limitation |
| **Holiday and calendar mismatch** | Indian vs US holidays differ; naive alignment drops or fabricates days | Align on Indian trading dates; handle foreign series' holidays explicitly |
| **Non-synchronous trading** | India closes before US opens; same-date correlation with US series misses timing | Consider lagging US series by one day [?] (advisor) |
| **Different units** | Crore vs lakh vs million; INR vs USD | Record units; convert explicitly |
| **Currency basis** | Brent in USD vs INR-converted Brent mix commodity and rupee effects | Decide basis per series; record |
| **Standalone vs consolidated** | Wrong basis produces false contradictions | Keep labelled; match like with like |
| **Fiscal vs calendar periods** | Mislabeled quarters | Fiscal-period utilities with known-answer tests |
| **Duplicate or missing data** | Silent gaps distort rolling statistics | Validator reports; no silent repair |
| **Thin trading in some instruments** | Stale prices understate correlation | Prefer liquid indices/ETFs; note limitation |

## 4. Storage and licence stance [PROPOSED]

- Downloaded data is stored in the project database or gitignored folders; **never committed** to the public repository.
- The API serves **derived analytics**, not raw vendor data.
- Every stored series has a manifest: source, retrieval time, date range, price type, adjustment status.

## 5. Questions for the advisor (see also `09`)

Q-DATA-1 preferred free or low-cost sources for NSE/BSE daily data, and which are acceptable for a commercial product; Q-DATA-2 availability of NSE total-return series; Q-DATA-3 where to obtain point-in-time RBI and FPI data; Q-DATA-4 timing alignment with US series; Q-DATA-5 any trusted data vendors with startup or academic pricing; Q-DATA-6 whether a G-sec index or yield series is the better "bond leg".
