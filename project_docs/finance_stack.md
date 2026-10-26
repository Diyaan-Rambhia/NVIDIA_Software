# Financial Mathematics and Stack Specifications

This document defines all financial calculations in FinInsight.
The platform operates as an educational and research tool for Indian equities.
No financial advisor review exists.
Every finance value is provisional, no advisor review.

## 1. Core Principles and Educational Safe Harbor

FinInsight calculates deterministic financial metrics for equity analysis.
The system does not provide investment advice.
It does not recommend buying, selling, or holding any asset.
It does not publish price targets or execution timing.
All analytical thresholds originate from declarative configuration files.
Every finance parameter remains provisional, no advisor review.

## 2. Continuous Logarithmic Returns

Continuous logarithmic returns measure relative price movement across trading sessions.
Logarithmic returns allow exact time-series addition across multiple periods.

### 2.1 Log Return Calculation
We compute log returns from daily adjusted closing prices.

Formula:
$$r_t = \ln\left(\frac{P_t}{P_{t-1}}\right) = \ln(P_t) - \ln(P_{t-1})$$

Where:
- $P_t$ is the adjusted closing price on day $t$.
- $P_{t-1}$ is the adjusted closing price on day $t-1$.
- $\ln$ is the natural logarithm.

Example, not market data:
Suppose an equity trades at two consecutive closing prices:
- Day 0 adjusted price ($P_0$): 100.0 INR.
- Day 1 adjusted price ($P_1$): 105.0 INR.

Calculation:
$$r_1 = \ln(105.0 / 100.0) = \ln(1.050) \approx 0.048790$$
The logarithmic return equals +4.879 percent.

## 3. Calendar Alignment

Cross-asset correlation analysis requires exact time alignment across instruments.
Indian equities trade Monday through Friday from 09:15 to 15:30 IST.

### 3.1 Trading Calendar Alignment
We perform an inner join on common trading dates across all selected assets.
If an asset lacks trading on a date, we drop that date.
This alignment prevents artificial zero-return distortion.

Formula:
$$T_{\text{aligned}} = \bigcap_{i=1}^N T_i$$

Example, not market data:
Suppose two equities trade on specific dates:
- Equity A dates: Day 1, Day 2, Day 4.
- Equity B dates: Day 1, Day 2, Day 3, Day 4.

Calculation:
The common date set is Day 1, Day 2, and Day 4.
Day 3 drops from joint covariance estimation.

## 4. Fiscal Periods

Indian companies report financial results on an April-to-March fiscal calendar.
We standardize reporting dates into four quarters.

### 4.1 Fiscal Period Date Derivation
We map fiscal period labels to calendar quarter-end dates.
- Quarter 1 (Q1): April 1 to June 30.
- Quarter 2 (Q2): July 1 to September 30.
- Quarter 3 (Q3): October 1 to December 31.
- Quarter 4 (Q4): January 1 to March 31.

Formula:
$$\text{EndDate}(Q, FY) = \text{CalendarDate}(Q, FY)$$

Example, not market data:
Consider period label "Q1 FY27".
FY27 starts on April 1 and ends on March 31.
Q1 represents the three months ending June 30.
The canonical period-end date is June 30.

## 5. Covariance Estimators

Covariance measures how two asset return series move together over time.
FinInsight implements three covariance estimators.

### 5.1 Rolling Sample Covariance
Rolling sample covariance applies equal weights to observations over window $W$.

Formula:
$$S_{ij} = \frac{1}{W - 1} \sum_{t=1}^W (r_{i,t} - \bar{r}_i)(r_{j,t} - \bar{r}_j)$$

Example, not market data:
Take 3 mean-zero returns for two assets ($W=3$):
- Asset 1: $[+0.02, -0.01, -0.01]$
- Asset 2: $[+0.01, 0.00, -0.01]$

Calculation:
$$S_{12} = \frac{(0.02)(0.01) + (-0.01)(0.00) + (-0.01)(-0.01)}{3 - 1}$$
$$S_{12} = \frac{0.00020 + 0.00000 + 0.00010}{2} = 0.00015$$

### 5.2 EWMA Covariance
Exponentially Weighted Moving Average assigns higher weight to recent returns.
The decay factor $\lambda$ controls weighting speed.
Default $\lambda = 0.94$ (provisional, no advisor review).

Formula:
$$w_t = (1 - \lambda) \lambda^{W - t}$$
$$\Sigma_{ij}^{\text{EWMA}} = \sum_{t=1}^W w_t (r_{i,t} - \bar{r}_i)(r_{j,t} - \bar{r}_j)$$

Example, not market data:
For two periods with weights $w_1 = 0.30$ and $w_2 = 0.70$:
- Period 1 product: $0.00010$.
- Period 2 product: $0.00040$.

Calculation:
$$\Sigma_{12} = (0.30)(0.00010) + (0.70)(0.00040) = 0.00003 + 0.00028 = 0.00031$$

### 5.3 Ledoit-Wolf Shrinkage Covariance
Ledoit-Wolf shrinkage pulls sample covariance toward a constant correlation target matrix $F$.
This reduces sample error when sample windows are short.

Formula:
$$\Sigma^{\text{LW}} = (1 - \delta^*) S + \delta^* F$$
Where $\delta^* \in [0, 1]$ is the optimal shrinkage intensity.

Example, not market data:
Suppose sample covariance $S = 0.00040$, target $F = 0.00020$, and intensity $\delta^* = 0.25$:

Calculation:
$$\Sigma^{\text{LW}} = (1 - 0.25)(0.00040) + (0.25)(0.00020) = 0.00030 + 0.00005 = 0.00035$$

## 6. Forbes-Rigobon Correlation Shift

Unadjusted correlation rises mechanically when asset return volatility increases.
This mechanical rise causes false contagion signals during market turmoil.

### 6.1 Forbes-Rigobon Adjusted Shift
Forbes and Rigobon (2002) adjust correlation to isolate true shift from volatility spikes.

Formula:
$$\rho^* = \frac{\rho}{\sqrt{1 + \delta (1 - \rho^2)}}$$
Where:
- $\delta = \frac{\sigma_{\text{stress}}^2}{\sigma_{\text{baseline}}^2} - 1$ is relative variance change.
- $\rho$ is unadjusted correlation in stress window.
- $\Delta \rho = \rho^* - \rho_{\text{baseline}}$ is net adjusted shift.

Example, not market data:
Assume:
- Baseline correlation $\rho_{\text{baseline}} = 0.40$.
- Baseline variance $\sigma_{\text{baseline}}^2 = 0.0001$.
- Stress variance $\sigma_{\text{stress}}^2 = 0.0002$.
- Stress unadjusted correlation $\rho = 0.70$.

Calculation:
1. Relative variance increase: $\delta = (0.0002 / 0.0001) - 1 = 1.0$.
2. Denominator factor: $\sqrt{1 + 1.0 \times (1 - 0.49)} = \sqrt{1.51} \approx 1.2288$.
3. Adjusted correlation: $\rho^* = 0.70 / 1.2288 \approx 0.5697$.
4. Net shift: $\Delta \rho = 0.5697 - 0.40 = +0.1697$.

## 7. Spearman Rank Correlation

Spearman rank correlation evaluates monotonic relationships without assuming linear returns.

### 7.1 Spearman Monotonic Rank Correlation
We rank asset returns ordinally before computing correlation.
This reduces vulnerability to extreme outlier returns.

Formula:
$$r_s = 1 - \frac{6 \sum d_i^2}{n(n^2 - 1)}$$
Where $d_i = \text{rank}(x_i) - \text{rank}(y_i)$ and $n$ is observation count.

Example, not market data:
Take 3 return observations ($n=3$):
- Day 1: Asset X rank 3, Asset Y rank 3 ($d_1 = 0, d_1^2 = 0$).
- Day 2: Asset X rank 2, Asset Y rank 1 ($d_2 = 1, d_2^2 = 1$).
- Day 3: Asset X rank 1, Asset Y rank 2 ($d_3 = -1, d_3^2 = 1$).
- $\sum d_i^2 = 0 + 1 + 1 = 2$.

Calculation:
$$r_s = 1 - \frac{6 \times 2}{3(9 - 1)} = 1 - \frac{12}{24} = 1 - 0.5 = 0.50$$

## 8. Systemic Absorption Ratio

The absorption ratio measures variance concentration across an equity market universe.
Rising absorption ratio indicates that common market factors dominate individual asset dynamics.

### 8.1 Principal Component Absorption Ratio
We compute eigenvalues of the normalized asset covariance matrix.
The absorption ratio measures variance explained by the top $k$ principal components.

Formula:
$$\text{AR} = \frac{\sum_{i=1}^k \lambda_i}{\sum_{j=1}^N \lambda_j}$$
Where:
- $N$ is total asset count.
- $k = \max(1, \lceil N \times k_{\text{fraction}} \rceil)$.
- $k_{\text{fraction}} = 0.20$ (provisional, no advisor review).

Example, not market data:
In a 4-asset system ($N=4, k=1$), sorted eigenvalues equal:
- $\lambda_1 = 2.4, \lambda_2 = 0.8, \lambda_3 = 0.5, \lambda_4 = 0.3$.
- Total variance: $2.4 + 0.8 + 0.5 + 0.3 = 4.0$.

Calculation:
$$\text{AR} = \frac{2.4}{4.0} = 0.60 \quad (60\%)$$

## 9. Moving-Block Bootstrap

Financial returns show time-series dependency and volatility clustering.
Standard random sampling breaks autocorrelation structure.

### 9.1 Moving-Block Bootstrap Significance
We resample continuous overlapping blocks of returns of length $L$ with replacement.
This empirical test computes two-sided p-values for observed correlation shifts.

Formula:
$$p = \frac{1}{B} \sum_{b=1}^B \mathbb{I}\left(|\Delta \rho^{(b)}| \ge |\Delta \rho_{\text{observed}}|\right)$$
Where $B=500$ bootstrap iterations and $L=10$ days (provisional, no advisor review).

Example, not market data:
Suppose $B=10$ bootstrap samples evaluate observed shift $\Delta \rho_{\text{obs}} = 0.25$.
Sample bootstrap shifts:
$[0.05, 0.12, 0.26, 0.08, 0.30, 0.02, 0.15, 0.18, 0.27, 0.10]$

Calculation:
Three values ($0.26, 0.30, 0.27$) equal or exceed $0.25$.
$$p = \frac{3}{10} = 0.30$$
The shift is not statistically significant at the 5 percent level.

## 10. Severity Tiers

FinInsight maps quantitative indicators into deterministic market stress tiers.

### 10.1 Stress Regime Classification
We evaluate standardized delta AR z-scores and significant pair shift fractions.

Tiers and thresholds (provisional, no advisor review):
- **Normal:** Delta AR $< 1.0$ and $< 10\%$ of pairs significant.
- **Elevated:** Delta AR $\ge 1.0$ and $\ge 10\%$ of pairs significant ($p < 0.05$).
- **High:** Delta AR $\ge 1.5$ and $\ge 20\%$ of pairs significant ($p < 0.05$).
- **Severe:** Delta AR $\ge 2.0$ and $\ge 35\%$ of pairs significant ($p < 0.01$).

Example, not market data:
A 10-pair system records:
- Delta AR z-score: $1.70$.
- Significant pair shifts ($p < 0.05$): 2 out of 10 pairs ($20\%$).

Calculation:
Delta AR ($1.70$) exceeds the High floor ($1.5$).
Shift fraction ($20\%$) matches the High floor ($20\%$).
The system flags the **High** stress tier.

## 11. Portfolio XIRR Return Solver

XIRR computes annualized return for portfolios with irregular trade dates and cash flows.

### 11.1 Net Present Value XIRR Solver
We solve for discount rate $r$ that sets net present value to zero.
We use day-count basis 365.0 days.

Formula:
$$\text{NPV}(r) = \sum_{i=1}^M \frac{C_i}{(1 + r)^{\frac{d_i - d_1}{365.0}}} = 0$$
Where:
- $C_i$ is cash flow on date $d_i$.
- Newton-Raphson iterations run with fallback to bisection within bracket $[-0.99, 10.0]$.

Example, not market data:
Cash flows:
- Date 1: Initial purchase of 100,000 INR ($C_1 = -100,000$).
- Date 2 (365 days later): Portfolio valuation of 110,000 INR ($C_2 = +110,000$).

Calculation:
$$\text{NPV}(r) = -100,000 + \frac{110,000}{(1 + r)^{1.0}} = 0$$
$$1 + r = \frac{110,000}{100,000} = 1.10 \implies r = 0.10 \quad (10\%)$$

## 12. Benchmark Replay

Benchmark replay evaluates portfolio performance against standard market indices.

### 12.1 Cash-Flow Matched Index Simulation
Every buy transaction buys units of NIFTY 50 or SENSEX.
Every sell transaction sells proportional index units.

Formula:
$$\Delta U_t = \frac{|C_{\text{buy}, t}|}{I_t}$$
$$\Delta U_t = - U_{t-1} \times \min\left(1.0, \frac{C_{\text{sell}, t}}{V_{\text{portfolio}, t}}\right)$$
Where $I_t$ is index price and $V$ is portfolio value.

Example, not market data:
Buy trade:
- Capital invested: 50,000 INR.
- Benchmark index price: 10,000 INR.

Calculation:
$$\Delta U = \frac{50,000}{10,000} = 5.0 \text{ units}$$
If terminal index price is 12,000 INR, terminal value equals $5.0 \times 12,000 = 60,000$ INR.

## 13. Behavioral Process Metrics

Behavioral metrics evaluate investment discipline separate from market returns.

### 13.1 Herfindahl-Hirschman Concentration Index
HHI measures position concentration across $N$ held assets.

Formula:
$$\text{HHI} = \sum_{i=1}^N w_i^2$$
Where $w_i = V_i / \sum V$.

Example, not market data:
Two assets held with weights $w_1 = 0.80$ and $w_2 = 0.20$.
Calculation:
$$\text{HHI} = 0.80^2 + 0.20^2 = 0.64 + 0.04 = 0.68$$

### 13.2 Portfolio Turnover Rate
Turnover measures trading volume relative to average portfolio equity.

Formula:
$$\text{Turnover} = \frac{\min(\sum \text{Buys}, \sum \text{Sells})}{\bar{V}_{\text{portfolio}}}$$

Example, not market data:
Total buys = 40,000 INR, total sells = 30,000 INR, average equity = 100,000 INR.
Calculation:
$$\text{Turnover} = \frac{30,000}{100,000} = 0.30 \quad (30\%)$$

### 13.3 Disposition Effect (PGR and PLR)
Measures the bias of realizing gains too quickly while holding losing positions.

Formulas:
$$\text{PGR} = \frac{\text{Realized Gains}}{\text{Realized Gains} + \text{Paper Gains}}$$
$$\text{PLR} = \frac{\text{Realized Losses}}{\text{Realized Losses} + \text{Paper Losses}}$$
$$\text{Disposition Ratio} = \frac{\text{PGR}}{\text{PLR}}$$

Example, not market data:
Realized gains = 8, paper gains = 2 ($\text{PGR} = 8/10 = 0.80$).
Realized losses = 2, paper losses = 8 ($\text{PLR} = 2/10 = 0.20$).
Calculation:
$$\text{Disposition Ratio} = \frac{0.80}{0.20} = 4.0$$
Ratio above 1.0 indicates disposition bias.

### 13.4 Maximum Drawdown
Measures the largest peak-to-trough decline before a new peak occurs.

Formula:
$$\text{MDD} = \max_t \left( \frac{\text{Peak}_t - V_t}{\text{Peak}_t} \right)$$

Example, not market data:
Portfolio peaks at 150,000 INR and declines to 120,000 INR.
Calculation:
$$\text{MDD} = \frac{150,000 - 120,000}{150,000} = \frac{30,000}{150,000} = 0.20 \quad (20\%)$$

## 14. Institutional Performance Metrics

Institutional metrics annualize performance using 252 trading days.

### 14.1 Sharpe Ratio
Sharpe ratio measures excess return per unit total standard deviation.

Formula:
$$\text{Sharpe} = \frac{\bar{R}_p - R_f}{\sigma_p \sqrt{252}}$$

Example, not market data:
Annualized portfolio return = 15% (0.15), risk-free rate = 7% (0.07), annualized volatility = 16% (0.16).
Calculation:
$$\text{Sharpe} = \frac{0.15 - 0.07}{0.16} = \frac{0.08}{0.16} = 0.50$$

### 14.2 Sortino Ratio
Sortino ratio measures excess return per unit downside deviation.

Formula:
$$\text{Sortino} = \frac{\bar{R}_p - R_f}{\sigma_{\text{down}} \sqrt{252}}$$
Where $\sigma_{\text{down}} = \sqrt{\frac{1}{T} \sum \min(0, R_t - R_f)^2}$.

Example, not market data:
Excess return = 0.08, downside volatility = 0.10.
Calculation:
$$\text{Sortino} = \frac{0.08}{0.10} = 0.80$$

### 14.3 Calmar Ratio
Calmar ratio measures annualized return divided by maximum drawdown.

Formula:
$$\text{Calmar} = \frac{\text{CAGR}}{\text{Max Drawdown}}$$

Example, not market data:
CAGR = 14% (0.14), max drawdown = 20% (0.20).
Calculation:
$$\text{Calmar} = \frac{0.14}{0.20} = 0.70$$

### 14.4 Information Ratio
Information ratio measures active return relative to benchmark divided by tracking error.

Formula:
$$\text{IR} = \frac{\bar{R}_p - \bar{R}_b}{\sigma(R_p - R_b) \sqrt{252}}$$

Example, not market data:
Portfolio return = 16%, benchmark return = 12%, tracking error = 8%.
Calculation:
$$\text{IR} = \frac{0.16 - 0.12}{0.08} = \frac{0.04}{0.08} = 0.50$$

## 15. Filing Metrics

We normalize reported metrics from official quarterly Ind AS XBRL disclosures.

### 15.1 Year-over-Year Growth
Measures quarterly performance against the identical quarter in prior fiscal year.

Formula:
$$\text{YoY} = \frac{M_t - M_{t-4}}{M_{t-4}}$$

Example, not market data:
Current quarter revenue = 120 INR, prior year quarter revenue = 100 INR.
Calculation:
$$\text{YoY} = \frac{120 - 100}{100} = +0.20 \quad (+20\%)$$

### 15.2 Quarter-over-Quarter Growth
Measures sequential performance change against immediately preceding quarter.

Formula:
$$\text{QoQ} = \frac{M_t - M_{t-1}}{M_{t-1}}$$

Example, not market data:
Current quarter profit = 55 INR, prior quarter profit = 50 INR.
Calculation:
$$\text{QoQ} = \frac{55 - 50}{50} = +0.10 \quad (+10\%)$$

### 15.3 Operating and Net Profit Margins
Measures operating profit margin (OPM) and net profit margin (PAT margin).

Formulas:
$$\text{OPM} = \frac{\text{Operating Profit}}{\text{Revenue from Operations}}$$
$$\text{NPM} = \frac{\text{Profit After Tax}}{\text{Revenue from Operations}}$$

Example, not market data:
Revenue = 1,000 INR, Operating Profit = 180 INR, Profit After Tax = 120 INR.
Calculation:
$$\text{OPM} = \frac{180}{1,000} = 0.18 \quad (18\%), \quad \text{NPM} = \frac{120}{1,000} = 0.12 \quad (12\%)$$

### 15.4 Days Sales Outstanding
Measures average days required to collect trade receivables from customers.

Formula:
$$\text{DSO} = \frac{\text{Trade Receivables}}{\text{Annualized Revenue}} \times 365.0$$

Example, not market data:
Trade receivables = 200 INR, Annualized revenue = 1,460 INR.
Calculation:
$$\text{DSO} = \frac{200}{1,460} \times 365.0 = 50.0 \text{ days}$$

### 15.5 Operating Cash Flow Conversion
Measures proportion of operating profit converted into cash flow from operations.

Formula:
$$\text{OCF Conversion} = \frac{\text{Cash Flow from Operations}}{\text{Operating Profit}}$$

Example, not market data:
Cash flow from operations = 80 INR, Operating profit = 100 INR.
Calculation:
$$\text{OCF Conversion} = \frac{80}{100} = 0.80 \quad (80\%)$$

### 15.6 Fourth-Quarter Derivation
Companies report full-year audited totals and nine-month cumulative figures.
We derive fourth-quarter metrics by subtraction.

Formula:
$$M_{\text{Q4}} = M_{\text{Full Year}} - \sum_{q=1}^3 M_{\text{Q}q}$$

Example, not market data:
Full-year audited revenue = 1,000 INR.
Q1 revenue = 220 INR, Q2 revenue = 240 INR, Q3 revenue = 250 INR.
Nine-month sum = $220 + 240 + 250 = 710$ INR.
Calculation:
$$M_{\text{Q4}} = 1,000 - 710 = 290 \text{ INR}$$

## 16. Accounting Consistency Rules R0 to R7

FinInsight executes deterministic rule checks comparing management claims against official XBRL filings.

### 16.1 Deterministic Audit Rules Execution

| Rule ID | Rule Name | Description |
|---|---|---|
| **R0** | Stated Number Discrepancy | Verifies exact numeric disclosures against filing facts. |
| **R1** | Directional Contradiction | Verifies qualitative directional growth claims. |
| **R2** | Margin Expansion Contradiction | Verifies claims asserting margin expansion. |
| **R3** | Low Cash Conversion Flag | Audits operating cash flow conversion ratio. |
| **R4** | Revenue vs Inventory Divergence | Detects inventory growth outpacing revenue growth. |
| **R5** | Receivables Growth Outpacing Revenue | Detects receivables growth expanding days sales outstanding. |
| **R6** | Growth Adjective Understatement | Compares promotional growth claims against sector floors. |
| **R7** | Unverifiable Material Metric | Flags non-GAAP operational claims absent from XBRL tags. |

Cases per rule:
- **Rule R0:**
  - *Pass:* Claim states revenue grew 12%, filing shows 12.4% (difference $0.4\% \le 1.0\%$).
  - *Flag:* Claim states revenue grew 12%, filing shows 8.0% (difference $4.0\% > 1.0\%$).
  - *Not-Applicable:* Filing lacks comparable prior period revenue.
- **Rule R1:**
  - *Pass:* Claim states profit increased, filing shows profit rose +1.2%.
  - *Flag:* Claim states profit increased, filing shows profit dropped -0.8%.
  - *Not-Applicable:* Zero profit in both comparison periods.
- **Rule R2:**
  - *Pass:* Claim asserts margin expansion, filing shows margin widened +35 bps.
  - *Flag:* Claim asserts margin expansion, filing shows margin contracted -10 bps.
  - *Not-Applicable:* Company reports negative gross margin.
- **Rule R3:**
  - *Pass:* Operating cash flow conversion equals 82% ($> 70\%$).
  - *Flag:* Operating cash flow conversion equals 45% ($< 70\%$).
  - *Not-Applicable:* Quarterly filing lacks standalone cash flow statement.
- **Rule R4:**
  - *Pass:* Inventory grew 8%, revenue grew 10% (gap negative).
  - *Flag:* Inventory grew 28%, revenue grew 10% (gap 18 pp exceeds 15 pp).
  - *Not-Applicable:* Service company holding no inventory.
- **Rule R5:**
  - *Pass:* DSO increased 5 days ($< 15$ days).
  - *Flag:* DSO increased 22 days ($> 15$ days).
  - *Not-Applicable:* Annualized revenue unavailable.
- **Rule R6:**
  - *Pass:* Claim states strong growth and actual growth is 14% (above FMCG 6% floor).
  - *Flag:* Claim states strong growth and actual growth is 2% (below FMCG 6% floor).
  - *Not-Applicable:* No promotional growth adjectives present in disclosure.
- **Rule R7:**
  - *Pass:* Mentioned metric exists in official XBRL taxonomy.
  - *Flag:* Management cites non-GAAP order book absent from XBRL tags.
  - *Not-Applicable:* Standard Ind AS financial line item.

### 16.2 Annual-Only Audit Rule Restriction

SEBI Ind AS reporting regulations mandate comprehensive statement of cash flows and complete balance sheet schedules primarily for annual reports. Quarterly disclosures frequently omit standalone cash flow statements and granular working capital notes.

Inspection of the consistency rule code (`rules.py` and `derived_metrics.py`) reveals that exactly Rules R5 (operating cash flow quality), R6 (working capital divergence), and metric DSO (days sales outstanding) require cash flow or receivables/inventory balance sheet items. Rule R7 evaluates understatements against growth and sector thresholds and does not require cash flow data.

Therefore, only Rules R5, R6, and metric DSO are restricted to annual filings. On quarterly filings, Rules R5 and R6 evaluate as `not_applicable` with an explanatory reason.

## 17. Sector Thresholds

FinInsight defines sector-specific baseline growth floors in `config/thresholds.yaml`.
Promotional claims asserting "strong growth" evaluate against these baseline floors:

| Sector | Baseline Floor | Provisional Status |
|---|---|---|
| Autos | 10.0% | Provisional, no advisor review |
| Capital_Goods | 12.0% | Provisional, no advisor review |
| Consumer_Durables | 10.0% | Provisional, no advisor review |
| Energy | 8.0% | Provisional, no advisor review |
| Fmcg | 6.0% | Provisional, no advisor review |
| It_Services | 8.0% | Provisional, no advisor review |
| Metals | 10.0% | Provisional, no advisor review |
| Other | 8.0% | Provisional, no advisor review |
| Telecom | 8.0% | Provisional, no advisor review |
| Default (other) | 8.0% | Provisional, no advisor review |

Audit tolerance thresholds from `config/thresholds.yaml`:

| Threshold Parameter | Value | Provisional Status |
|---|---|---|
| `direction_tolerance` | 0.005 | Provisional, no advisor review |
| `dso_increase_days` | 10 | Provisional, no advisor review |
| `inventory_vs_revenue_gap_pp` | 15.0 | Provisional, no advisor review |
| `margin_tolerance_bps` | 20 | Provisional, no advisor review |
| `max_flags_per_document` | 5 | Provisional, no advisor review |
| `ocf_conversion_floor` | 0.5 | Provisional, no advisor review |
| `precision_target` | 0.8 | Provisional, no advisor review |
| `stated_number_tolerance_pp` | 0.5 | Provisional, no advisor review |
| `strong_growth_yoy_default` | 0.08 | Provisional, no advisor review |
| `strong_growth_yoy_sectors` | {'fmcg': 0.06, 'it_services': 0.08, 'autos': 0.1, 'capital_goods': 0.12, 'metals': 0.1, 'energy': 0.08, 'telecom': 0.08, 'consumer_durables': 0.1, 'other': 0.08} | Provisional, no advisor review |
| `understatement_gap_pp` | 10.0 | Provisional, no advisor review |

## 18. Risk-Free Rate

The risk-free rate is configured as **5.7281 percent**.
Source: Reserve Bank of India (RBI) press release 2026-2027/1326.
The old null value is out of date.
Calculations requiring sovereign risk-free yields reference this rate.
This rate represents the 91-day Government of India Treasury Bill yield.
All rate values remain provisional, no advisor review.

## 19. Full Parameter Register

The tables below list every parameter loaded from `config/parameters.yaml`.
All parameters operate as active values in code and configuration.
All parameters remain provisional, no advisor review.

| Parameter Name | Value | Unit | Override Allowed | Provisional Status |
|---|---|---|---|---|
| `AR_long` | None | trading days | Yes | Provisional, no advisor review |
| `AR_short` | None | trading days | Yes | Provisional, no advisor review |
| `B` | None | trading days | Yes | Provisional, no advisor review |
| `C` | None | trading days | Yes | Provisional, no advisor review |
| `G` | None | trading days | Yes | Provisional, no advisor review |
| `T` | None | trading days | Yes | Provisional, no advisor review |
| `W` | None | trading days | Yes | Provisional, no advisor review |
| `agent_budget_usd` | None | USD | Yes | Provisional, no advisor review |
| `agent_max_steps` | None | steps | Yes | Provisional, no advisor review |
| `agent_timeout_seconds` | None | seconds | Yes | Provisional, no advisor review |
| `alpha` | None | significance level | Yes | Provisional, no advisor review |
| `annualisation_factor` | None | periods per year | Yes | Provisional, no advisor review |
| `block_len` | None | trading days | Yes | Provisional, no advisor review |
| `chunk_overlap` | None | characters | Yes | Provisional, no advisor review |
| `chunk_size` | None | characters | Yes | Provisional, no advisor review |
| `cors_origins` | None | comma_separated_origins | Yes | Provisional, no advisor review |
| `disposition_min_sales` | None | sale count | Yes | Provisional, no advisor review |
| `f1_news_searches_per_run` | None | count | Yes | Provisional, no advisor review |
| `f2_lookup_cache_ttl_seconds` | None | seconds | Yes | Provisional, no advisor review |
| `f2_lookup_daily_limit` | None | count | Yes | Provisional, no advisor review |
| `f2_search_result_limit` | None | count | Yes | Provisional, no advisor review |
| `f2_top50_cache_ttl_seconds` | None | seconds | Yes | Provisional, no advisor review |
| `f2_financial_keywords` | None | comma_separated_keywords | Yes | Provisional, no advisor review |
| `f2_financial_sectors` | None | comma_separated_sectors | Yes | Provisional, no advisor review |
| `f3_hosted_upload_enabled` | None | mode | Yes | Provisional, no advisor review |
| `fdr_q` | None | false discovery rate | Yes | Provisional, no advisor review |
| `file_extract_max_bytes` | None | bytes | Yes | Provisional, no advisor review |
| `file_extract_max_chars` | None | characters | Yes | Provisional, no advisor review |
| `file_extract_max_pages` | None | pages | Yes | Provisional, no advisor review |
| `file_extract_max_rows` | None | rows | Yes | Provisional, no advisor review |
| `file_extract_max_uncompressed_bytes` | None | bytes | Yes | Provisional, no advisor review |
| `file_extract_max_zip_entries` | None | count | Yes | Provisional, no advisor review |
| `file_extract_timeout_seconds` | None | seconds | Yes | Provisional, no advisor review |
| `filings_first_fiscal_year` | None | fiscal_year | No | Provisional, no advisor review |
| `fiscal_year_max` | None | year | Yes | Provisional, no advisor review |
| `fiscal_year_min` | None | year | Yes | Provisional, no advisor review |
| `hosted_demo_mode` | None | mode | Yes | Provisional, no advisor review |
| `k_fraction` | None | fraction of N | Yes | Provisional, no advisor review |
| `lambda` | None | decay factor | Yes | Provisional, no advisor review |
| `llm_per_call_max_tokens` | None | count | Yes | Provisional, no advisor review |
| `llm_per_call_max_tokens_judge_all` | None | count | Yes | Provisional, no advisor review |
| `llm_per_user_daily_token_limit` | None | count | Yes | Provisional, no advisor review |
| `llm_per_user_daily_token_limit_judge_all` | None | count | Yes | Provisional, no advisor review |
| `llm_placeholder_price_per_1m` | None | usd_placeholder_only | No | Provisional, no advisor review |
| `min_trades_for_stats` | None | trade count | Yes | Provisional, no advisor review |
| `n_boot` | None | iterations | Yes | Provisional, no advisor review |
| `non_prose_max_code_density` | None | ratio | Yes | Provisional, no advisor review |
| `nse_global_rate_limit_per_second` | None | rate | Yes | Provisional, no advisor review |
| `return_frequency` | None | cadence | No | Provisional, no advisor review |
| `risk_free_series` | None | series identifier | No | Provisional, no advisor review |
| `runup_percentile` | None | percentile | Yes | Provisional, no advisor review |
| `runup_window_days` | None | trading days | Yes | Provisional, no advisor review |
| `s1_share` | None | fraction of peers | Yes | Provisional, no advisor review |
| `s2_z` | None | z-score threshold | Yes | Provisional, no advisor review |
| `s3_shift` | None | probability mass shift | Yes | Provisional, no advisor review |
| `signals_required` | None | count of signals | Yes | Provisional, no advisor review |
| `synthetic_log_qty_max` | None | shares | Yes | Provisional, no advisor review |
| `synthetic_log_qty_min` | None | shares | Yes | Provisional, no advisor review |
| `synthetic_log_seed` | None | seed | Yes | Provisional, no advisor review |
| `synthetic_log_trades` | None | trades | Yes | Provisional, no advisor review |
| `us_series_lag_days` | None | calendar days | No | Provisional, no advisor review |
| `xirr_bracket_high` | None | rate upper bound | Yes | Provisional, no advisor review |
| `xirr_bracket_low` | None | rate lower bound | Yes | Provisional, no advisor review |
| `xirr_grid_points` | None | grid points | Yes | Provisional, no advisor review |
| `xirr_max_iter` | None | iterations | Yes | Provisional, no advisor review |
| `xirr_tol` | None | solver tolerance | Yes | Provisional, no advisor review |
| `yfinance_cache_ttl_seconds` | None | seconds | Yes | Provisional, no advisor review |
| `yfinance_max_tickers_per_request` | None | count | Yes | Provisional, no advisor review |



| Parameter Name | Bounds | Source |
|---|---|---|
| `AR_long` | [None, None] | System default |
| `AR_short` | [None, None] | System default |
| `B` | [None, None] | System default |
| `C` | [None, None] | System default |
| `G` | [None, None] | System default |
| `T` | [None, None] | System default |
| `W` | [None, None] | System default |
| `agent_budget_usd` | [None, None] | System default |
| `agent_max_steps` | [None, None] | System default |
| `agent_timeout_seconds` | [None, None] | System default |
| `alpha` | [None, None] | System default |
| `annualisation_factor` | [None, None] | System default |
| `block_len` | [None, None] | System default |
| `chunk_overlap` | [None, None] | System default |
| `chunk_size` | [None, None] | System default |
| `cors_origins` | [None, None] | System default |
| `disposition_min_sales` | [None, None] | System default |
| `f1_news_searches_per_run` | [None, None] | System default |
| `f2_lookup_cache_ttl_seconds` | [None, None] | System default |
| `f2_lookup_daily_limit` | [None, None] | System default |
| `f2_search_result_limit` | [None, None] | System default |
| `f2_top50_cache_ttl_seconds` | [None, None] | System default |
| `f2_financial_keywords` | [None, None] | System default |
| `f2_financial_sectors` | [None, None] | System default |
| `f3_hosted_upload_enabled` | [None, None] | System default |
| `fdr_q` | [None, None] | System default |
| `file_extract_max_bytes` | [None, None] | System default |
| `file_extract_max_chars` | [None, None] | System default |
| `file_extract_max_pages` | [None, None] | System default |
| `file_extract_max_rows` | [None, None] | System default |
| `file_extract_max_uncompressed_bytes` | [None, None] | System default |
| `file_extract_max_zip_entries` | [None, None] | System default |
| `file_extract_timeout_seconds` | [None, None] | System default |
| `filings_first_fiscal_year` | [None, None] | System default |
| `fiscal_year_max` | [None, None] | System default |
| `fiscal_year_min` | [None, None] | System default |
| `hosted_demo_mode` | [None, None] | System default |
| `k_fraction` | [None, None] | System default |
| `lambda` | [None, None] | System default |
| `llm_per_call_max_tokens` | [None, None] | System default |
| `llm_per_call_max_tokens_judge_all` | [None, None] | System default |
| `llm_per_user_daily_token_limit` | [None, None] | System default |
| `llm_per_user_daily_token_limit_judge_all` | [None, None] | System default |
| `llm_placeholder_price_per_1m` | [None, None] | System default |
| `min_trades_for_stats` | [None, None] | System default |
| `n_boot` | [None, None] | System default |
| `non_prose_max_code_density` | [None, None] | System default |
| `nse_global_rate_limit_per_second` | [None, None] | System default |
| `return_frequency` | [None, None] | System default |
| `risk_free_series` | [None, None] | System default |
| `runup_percentile` | [None, None] | System default |
| `runup_window_days` | [None, None] | System default |
| `s1_share` | [None, None] | System default |
| `s2_z` | [None, None] | System default |
| `s3_shift` | [None, None] | System default |
| `signals_required` | [None, None] | System default |
| `synthetic_log_qty_max` | [None, None] | System default |
| `synthetic_log_qty_min` | [None, None] | System default |
| `synthetic_log_seed` | [None, None] | System default |
| `synthetic_log_trades` | [None, None] | System default |
| `us_series_lag_days` | [None, None] | System default |
| `xirr_bracket_high` | [None, None] | System default |
| `xirr_bracket_low` | [None, None] | System default |
| `xirr_grid_points` | [None, None] | System default |
| `xirr_max_iter` | [None, None] | System default |
| `xirr_tol` | [None, None] | System default |
| `yfinance_cache_ttl_seconds` | [None, None] | System default |
| `yfinance_max_tickers_per_request` | [None, None] | System default |

## 20. What Each Metric Cannot Tell You

Quantitative metrics provide structured indicators but cannot reveal complete market truth:

1. **Absorption Ratio:**
Measures variance concentration across historical daily returns.
Cannot predict exact shock timing or catalyst events.
High absorption ratio indicates structural fragility, not immediate price collapse.

2. **Forbes-Rigobon Shift:**
Isolates correlation increases exceeding volatility expansion.
Cannot distinguish between fundamental economic coupling and temporary liquidity distress.

3. **Moving-Block Bootstrap:**
Estimates sample significance over selected historical periods.
Cannot protect against unprecedented macroeconomic structural breaks.

4. **XIRR Solver:**
Calculates money-weighted rate of return on invested capital.
Cannot separate manager skill from market beta or lucky timing.
Sensitive to timing of extreme intermediate cash injections.

5. **XBRL Consistency Rules:**
Verifies arithmetic alignment between executive statements and published numbers.
Cannot detect fraud if fraudulent figures exist inside the official filing itself.
Limited to reported Ind AS quarterly statement disclosures.

## 21. Educational-Only Wording

FinInsight enforces strict lexical filters prohibiting financial advice.
The system automatically suppresses or rejects prompt responses containing advisory terms:
- Prohibited terms: "buy", "sell", "hold", "target price", "portfolio recommendation".
- System outputs describe observations, discrepancies, and statistical shifts.
- Outputs never direct user trading decisions.
- Every report displays the educational and research disclaimer.

## 22. Financial Glossary

- **Absorption Ratio (AR):** Fraction of asset variance explained by top principal components.
- **Basis Points (bps):** One-hundredth of a percentage point ($0.01\%$).
- **Block Bootstrap:** Resampling method preserving time dependency by sampling continuous blocks.
- **Days Sales Outstanding (DSO):** Average days required to collect trade receivables.
- **Disposition Effect:** Behavioral bias of selling winning investments while retaining losing investments.
- **EWMA:** Exponentially Weighted Moving Average applying higher weight to recent returns.
- **Forbes-Rigobon Adjustment:** Mathematical adjustment correcting correlation upward bias during volatile episodes.
- **Herfindahl-Hirschman Index (HHI):** Statistical metric of portfolio concentration.
- **Ind AS:** Indian Accounting Standards converged with International Financial Reporting Standards.
- **Ledoit-Wolf Shrinkage:** Covariance estimator pulling sample covariance toward a structured target.
- **Log Return:** Continuously compounded rate of return calculated as natural logarithm of price ratio.
- **Operating Cash Flow (OCF):** Cash generated from primary operational business activities.
- **Proportion of Gains Realized (PGR):** Ratio of realized gains to total potential gains.
- **Proportion of Losses Realized (PLR):** Ratio of realized losses to total potential losses.
- **Provisional:** Working value adopted in code and configuration without human financial advisor review.
- **Q4 Derivation:** Deriving fourth quarter numbers by subtracting nine-month totals from annual reports.
- **Sharpe Ratio:** Measure of risk-adjusted excess return per unit total standard deviation.
- **Sortino Ratio:** Measure of risk-adjusted excess return per unit downside deviation.
- **Spearman Rank Correlation:** Monotonic correlation computed on ordinal ranks of values.
- **XBRL:** Extensible Business Reporting Language used for electronic regulatory filings in India.
- **XIRR:** Extended Internal Rate of Return solving for discount rate of irregular cash flows.

