# 01: Glossary

Plain-language definitions of every finance term in the project. Items marked [K] are team knowledge for the advisor to confirm.

## A. Markets and instruments

| Term | Plain meaning |
|---|---|
| **NSE, BSE** | India's two main stock exchanges (National Stock Exchange; BSE Limited). Most large companies list on both. [K] |
| **Nifty 50** | NSE's headline index of 50 large companies. [K] |
| **Sensex** | BSE's headline index of 30 large companies. [K] |
| **Price index vs total-return index (TRI)** | A price index tracks only price changes. A TRI also assumes dividends are reinvested. For comparing a real investor's results, TRI is the fair benchmark because the investor receives dividends. [K] |
| **ETF** | An exchange-traded fund: a basket traded like a share. In India, many ETFs track Nifty, gold or bonds. [K] |
| **Index (as an "asset")** | An index is not directly tradable, but its level series is a clean record of a market's behavior, which is what correlation analysis needs. |
| **G-sec** | Government of India securities (government bonds). The 10-year G-sec yield is the benchmark interest rate. [K] |
| **T-bill** | Short-term government security (91, 182, 364 days). Used as the "risk-free" return. [K] |
| **Liquid fund / liquid ETF** | Instrument holding very short-term money-market securities; acts as parking space for cash. [K] |
| **Mutual fund, NAV, SIP** | A pooled fund; NAV is its per-unit price (published daily by AMFI); SIP is a recurring fixed-amount purchase. [K] |
| **F&O (futures and options)** | Derivatives traded on the exchanges. Leveraged; most individual F&O traders lose money according to regulator studies (figures to be supplied by the advisor). [K] |
| **Delivery vs intraday** | Delivery trades are held beyond the day; intraday trades are squared off the same day. They are taxed and analyzed differently. [K] |

## B. Macro and flows

| Term | Plain meaning |
|---|---|
| **RBI** | Reserve Bank of India, the central bank. [K] |
| **MPC, repo rate** | RBI's Monetary Policy Committee sets the repo rate, the main policy interest rate. [K] |
| **Liquidity (system liquidity)** | How much spare cash banks hold. Tight liquidity pushes up short-term rates and stresses borrowers. [K] |
| **INR, USD/INR** | The rupee and its price in US dollars. A rising USD/INR means a weaker rupee. [K] |
| **FPI** | Foreign Portfolio Investor. Foreign money in Indian shares and bonds; sudden FPI selling is a classic Indian market stressor. [K] |
| **DII** | Domestic Institutional Investors (mutual funds, insurers). Often buy when FPIs sell. [K] |
| **India VIX** | NSE's volatility index: the market's expected near-term volatility. [K] |
| **Brent crude** | Global oil benchmark. India imports most of its oil, so oil prices affect the rupee and inflation. [K] |
| **Taper tantrum** | The 2013 episode when talk of reduced US monetary stimulus triggered capital outflows from emerging markets including India. [K] |

## C. Risk and statistics

| Term | Plain meaning |
|---|---|
| **Correlation** | A number from -1 to +1 describing how two things move together. +1 moves in lockstep; 0 is unrelated; -1 is opposite. |
| **Diversification** | Holding assets that do not move together so losses in one are offset by others. It depends on correlations staying low. |
| **Correlation breakdown / contagion** | Correlations that were low suddenly rise, so diversification fails in a crisis. |
| **Interdependence vs contagion** | Markets that were always linked (interdependence) are different from a *new* linkage appearing after a shock (contagion). Telling them apart is the research point of Forbes and Rigobon. |
| **Heteroskedasticity / volatility bias** | When volatility rises, measured correlation rises mechanically even if the underlying relationship has not changed. The Forbes-Rigobon adjustment removes this effect. |
| **Rank (Spearman) correlation** | Correlation of the *ranks* of values; less distorted by extreme days. |
| **Absorption ratio (AR)** | The fraction of all market movement explained by a few common factors. A high AR means the market is moving as one block. |
| **Principal component analysis (PCA)** | A method that finds the common factors behind many series. The "first component" is the largest common factor. |
| **Shrinkage (Ledoit-Wolf)** | A technique that makes noisy correlation estimates more stable. |
| **Bootstrap** | A way to test whether an observed change is bigger than chance by repeatedly resampling the data. |
| **Drawdown** | Fall from a previous peak to a later trough. Maximum drawdown is the worst such fall. |
| **Beta, alpha** | Beta: sensitivity to a benchmark. Alpha: return beyond what beta explains. [K] |
| **Tracking error, information ratio** | Tracking error: volatility of the difference from a benchmark. Information ratio: average excess return divided by tracking error. [K] |
| **Regime** | A period with a distinct pattern of behavior (calm, stressed, rate-hiking). |

## D. Returns and investor behavior

| Term | Plain meaning |
|---|---|
| **XIRR** | Annualized return for investments made on irregular dates. The standard way Indian platforms report returns for SIPs and multi-buy portfolios. [K] |
| **Money-weighted vs time-weighted return** | Money-weighted (XIRR) reflects the investor's own timing of cash in and out. Time-weighted strips timing out and measures the underlying investments. Both are informative; they answer different questions. |
| **Counterfactual benchmark replay** | "If the same rupees had gone in and out on the same days but into a benchmark instead, what would the result be?" |
| **Disposition effect** | The tendency to sell winners too soon and hold losers too long (Odean, 1998). |
| **Hindsight bias** | Judging a past decision by what happened afterward, using information that was not available then. The product must avoid it. |
| **Process vs outcome** | A good decision can lose money (bad luck); a bad decision can make money (good luck). The review separates the two. |
| **HHI (concentration)** | Herfindahl-Hirschman index: sum of squared portfolio weights. High means concentrated. |
| **Turnover** | How much of the portfolio is traded over a period. High turnover means higher costs. |

## E. Company reporting

| Term | Plain meaning |
|---|---|
| **Ind AS** | Indian Accounting Standards, converged with IFRS; used by most large listed companies. [K] |
| **Fiscal year (FY)** | April to March. "FY27" = April 2026 to March 2027; "Q1 FY27" = April-June 2026. [V] (naming pattern confirmed in company filings) |
| **Standalone vs consolidated** | Standalone: the single company. Consolidated: the company plus subsidiaries. Management often talks about consolidated; mixing them creates false contradictions. [K] |
| **Revenue from operations** | Sales from the core business; the usual "revenue" line. [K] |
| **EBITDA** | Earnings before interest, taxes, depreciation and amortization. Not a formally defined Ind AS line; companies compute it themselves, so definitions vary. [K] |
| **PAT** | Profit after tax. [K] |
| **Exceptional items** | One-off gains or losses shown separately; management often discusses profit "before exceptional items". [K] |
| **Adjusted / normalized figures** | Management's own versions of a metric excluding items it considers one-off. Not the reported figure. The main source of apparent but false contradictions. |
| **Constant currency** | Growth measured as if exchange rates had not changed. [K] |
| **YoY, QoQ** | Year-on-year and quarter-on-quarter change. Indian companies often say "sequential" for QoQ. [K] |
| **bps (basis points)** | 100 bps = 1 percentage point. Margin changes are quoted in bps. [K] |
| **XBRL** | Structured tagging of financial data in filings, which lets software read numbers reliably. [V] |
| **LODR** | SEBI's listing regulations; they require results, call recordings and transcripts to be published. [V] |
| **Earnings call** | Management's call with analysts after results. [V] SEBI requires recordings and transcripts to be made public. |
| **Investor presentation, press release** | Company documents accompanying results, containing management commentary. [K] |

## F. Regulation and compliance

| Term | Plain meaning |
|---|---|
| **SEBI** | The capital-markets regulator. [V] |
| **Investment Adviser (IA) / Research Analyst (RA)** | Categories SEBI regulates. Acting as either for the public requires registration. [V] |
| **Finfluencer** | A social-media personality giving market views. SEBI has issued rules for them. [V] |
| **DPDP Act** | India's data-protection law (2023), governing consent and handling of personal data. [K] |
| **GST** | Goods and Services Tax, charged on subscriptions and many fees. [K] |
| **KYC** | Know-Your-Customer identity verification, required of businesses by payment gateways and of investors by brokers. [K] |
| **STT** | Securities Transaction Tax, a tax on trades on the exchanges. [K] |
