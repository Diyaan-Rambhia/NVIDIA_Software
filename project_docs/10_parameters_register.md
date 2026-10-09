# 10: Parameters Register

Every numeric parameter or threshold in the system. All values live in `config/` files (never hard-coded), and per-request overrides are allowed within bounds where marked. **Every value below is a starting point chosen by non-specialists** [PROPOSED] unless noted. For each row the advisor is asked to mark: **Accept**, **Change to ___**, or **Reject**.

> **Owner decision (D-44):** every default in this register is accepted as a working value. TBD cells that blocked implementation have been filled with proposals. The advisor can still change any value, and all changes go through `config/` only.

Legend: *Override* = may a user change it per request (within bounds). Source: **[K]** team knowledge to confirm; **[P]** our proposal with no external basis.

## 1. Feature 1: windows and estimators

| Parameter | Meaning | Default | Min-Max | Override | Rationale | Source | Decision |
|---|---|---|---|---|---|---|---|
| `W` | Estimation window (trading days) for a correlation matrix | 60 | 20-500 | Yes | About three months of trading days balances noise and responsiveness | [P] | |
| `lambda` | EWMA decay | 0.94 | 0.80-0.99 | Yes | Classic RiskMetrics daily value | [K] | |
| `B` | Baseline window | 250 | 60-1000 | Yes | About one trading year of "normal" | [P] | |
| `G` | Gap between baseline end and current start | 20 | 0-250 | Yes | Keeps the stress period out of the baseline | [P] | |
| `C` | Current window | 20 | 5-250 | Yes | About one month | [P] | |
| `T` | Absorption-ratio covariance window | 250 | 60-1000 | Yes | Follows literature's longer estimation window | [K] | |
| `AR_short` | Short AR averaging window | 15 | 5-60 | Yes | Literature convention | [K] | |
| `AR_long` | Long AR averaging window | 250 | 60-1000 | Yes | One year | [K] | |
| `k_fraction` | Share of components used in AR | 1/5 | 0.1-0.5 | Yes | Literature convention | [K] | |
| `block_len` | Bootstrap block length | 10 | 2-60 | Yes | Preserves short-term dependence | [P] | |
| `n_boot` | Bootstrap replicates | 1000 | 200-5000 | Yes | Balance of precision and speed | [P] | |
| `alpha` | Significance level | 0.05 | 0.001-0.2 | Yes | Convention | [K] | |
| multiple-testing method | Benjamini-Hochberg false-discovery-rate control across pairs | BH | n/a | No | Standard, less conservative than Bonferroni | [P] | Adopted (D-18) |
| `fdr_q` | FDR level | 0.10 | 0.01-0.25 | Yes | Exploratory monitoring tolerates 10% | [P] | Adopted |
| `us_series_lag_days` | Lag of US series vs Indian series | 1 | 0-2 | Yes | India closes before the US opens | [K] | Adopted (D-21) |

## 2. Feature 1: flag logic

| Parameter | Meaning | Default | Min-Max | Override | Rationale | Source | Decision |
|---|---|---|---|---|---|---|---|
| `s1_share` | Share of pairs with significant adjusted shift needed for signal S1 | 0.20 | 0.05-0.8 | Yes | To be calibrated on real episodes | [P] | |
| `s2_z` | ΔAR threshold for S2 | 1.0 | 0.5-4.0 | Yes | Literature uses about one standard deviation for warnings | [K] | |
| `s3_shift` | Mean rank-correlation shift for S3 | 0.15 | 0.05-0.5 | Yes | To be calibrated | [P] | |
| `signals_required` | Signals that must agree | 2 of 3 | 1-3 | Yes | Reduces false alarms | [P] | |
| severity tiers | Watch / elevated / severe cut-offs | by signals and ΔAR | n/a | No | To be calibrated | [P] | |
| `max_flag_frequency` | Acceptable share of all days flagged (a sanity check) | report only | n/a | n/a | A method flagging most days is useless | [P] | |

## 3. Feature 1: universe and episodes

| Item | Current proposal | Decision |
|---|---|---|
| Asset set | See `03` §3.1 (about 10-15 series) | |
| Macro-factor set | See `03` §3.2 | |
| Episodes | 2013, 2018, 2020, 2022, 2024 (`03` §4) | |
| Negative controls | Calm periods; one-group shocks | |
| Calibration split | Which episodes tune, which are held out | |

## 4. Feature 2: rules and thresholds

| Parameter | Meaning | Default | Min-Max | Override | Rationale | Source | Decision |
|---|---|---|---|---|---|---|---|
| `strong_growth_yoy` | YoY revenue growth below which "strong" is suspect (R2) | 8% | 0%-30% | Config only | Sector-dependent; deliberately conservative | [P] | |
| `strong_growth_by_sector` | Sector overrides of the strong-growth threshold | FMCG 6%; IT services 8%; autos 10%; capital goods 12%; metals 10%; energy 8%; telecom 8%; consumer durables 10%; other 8% | 0%-30% | Config only | Starting guesses; calibrate on labelled data | [P] | Adopted (D-23) |
| `stated_number_tolerance_pp` | Percentage-point tolerance for rule R0 | 0.5 | 0.1-2.0 | Config only | Rounding noise | [P] | Adopted |
| `direction_tolerance` | Change treated as "flat" in R1 | ±0.5% | 0-3% | Config only | Avoid rounding noise | [P] | |
| `margin_tolerance_bps` | Margin move ignored in R4 | 20 bps | 0-100 | Config only | Avoid noise | [P] | |
| `ocf_conversion_floor` | Operating cash flow ÷ PAT below which R5 fires | 0.5 | 0.1-1.0 | Config only | Weak cash conversion | [P] | |
| `inventory_vs_revenue_gap` | Inventory growth minus revenue growth that triggers R6 | 15 percentage points | 5-50 | Config only | Working-capital build | [P] | |
| `dso_increase_days` | Rise in receivable days that triggers R6 | 10 days | 3-45 | Config only | Collections slipping | [P] | |
| `understatement_gap` | Growth above "strong" threshold that triggers R7 | +10 pp | 5-30 | Config only | Optional rule | [P] | |
| `min_confidence_display` | Adjudicated confidence needed to show a flag | high or medium-high | n/a | Config only | Precision-first | [P] | |
| `max_flags_per_document` | Cap on flags shown | 5 | 1-20 | Config only | Avoid noise | [P] | |
| Ambiguous words list | Words that never trigger rules alone | resilient, stable, steady, consistent, satisfactory, healthy (without a number), in line with expectations | n/a | Config only | Vague words | [P] | Adopted (D-26) |
| `precision_target` | Evaluation target for displayed flags | 0.80 | n/a | n/a | Quality bar | [P] | |

## 5. Feature 3: returns and process metrics

| Parameter | Meaning | Default | Min-Max | Override | Rationale | Source | Decision |
|---|---|---|---|---|---|---|---|
| Day-count basis in XIRR | Days per year | 365 | n/a | No | Spreadsheet convention | [K] | |
| Default benchmarks | Replay targets | Nifty 50 TRI, matched style index, risk-free proxy | n/a | Choice per log | See `05` §5 | [P] | |
| Risk-free proxy | Short-term rate source | 91-day Treasury-bill yield (RBI/FBIL/CCIL) | n/a | No | Standard short-term proxy | [K] | Adopted (D-33) |
| `runup_window_days` | Trailing window for entry-after-run-up | 20 | 5-120 | Yes | About one month | [P] | |
| `runup_percentile` | Percentile treated as a run-up | 90th | 75-99 | Yes | Top decile | [P] | |
| `min_trades_for_stats` | Trades needed before behavioral metrics are reported | 10 | 5-50 | Config only | Avoid over-reading tiny logs | [P] | |
| `disposition_min_sales` | Sale days needed to report PGR/PLR | 5 | 3-30 | Config only | Avoid noise | [P] | |
| Institutional metrics | Beta, alpha, tracking error, information ratio definitions | standard definitions | n/a | n/a | To be confirmed for Indian mandates | [?] | |
| Charges treatment | How supplied charges enter returns | include if supplied | n/a | n/a | No tax in MVP | [P] | |

## 6. Plans and quotas

| Parameter | Meaning | Default | Decision |
|---|---|---|---|
| `retail_free` F2 quota | Analyses per day | 3 | |
| `retail_free` F3 quota | Logs per day; trades per log | 1; 20 | |
| `retail_paid` quotas | F2 and F3 per day | F2 30 analyses; F3 10 logs, 500 trades per log | Adopted (D-45) |
| `institutional_paid` quotas | F1 and F3 per day; trades per log | F1 200 scans and 20 explanations; F3 50 logs, 5,000 trades per log; F2 at retail-free level | Adopted (D-45) |
| Prices | INR per month per plan | retail_paid ₹499; institutional_paid ₹24,999 (test-mode placeholders) | Provisional (D-09) |
| Rate limits | LLM-backed requests per minute per account | 10 | Adopted (D-45) |

## 7. Model and cost controls

| Parameter | Meaning | Default | Decision |
|---|---|---|---|
| `DAILY_LLM_BUDGET_USD` | Daily spend cap | 1.00 | Adopted; revise after the first cost report (D-45) |
| Tavily per-run credit cap | Searches per explanation | 3 | Adopted (D-45) |
| Agent step cap | Max tool steps per question | 8 | |
| LLM temperature | By call type | 0.0-0.3 | |

## 8. How changes are applied

An accepted or changed value is edited in `config/` (not in code) and logged in `DECISIONS.md` with the advisor's name and the reason. All results store the parameter values used, so earlier results remain interpretable after a change.
