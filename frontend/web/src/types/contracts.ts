export interface ShiftedPair {
  pair: string;
  baseline_corr: number;
  current_corr: number;
  fr_adjusted_corr: number;
  p_value: number;
  q_value: number;
}

export interface CorrelationScan {
  as_of?: string;
  source_label?: string;
  parameters_used?: Record<string, unknown>;
  regime_flag?: string;
  absorption_ratio?: number;
  ar_delta_std?: number;
  significant_pairs_count?: number;
  mean_correlation?: number;
  top_shifted_pairs?: ShiftedPair[];
  matrix_summary?: Record<string, unknown>;
  episodes_status?: string;
  seed?: number | string;
  code_version?: string;
  hypotheses?: Array<{ id: string; text: string; evidence_ids?: string[] }>;
  failed_tickers?: string[];
  scan_duration_seconds?: number;
  news?: {
    state: string;
    query?: string | null;
    results?: Array<{
      title: string;
      url: string;
      content: string;
      source?: string;
      evidence_id?: string;
    }> | null;
    not_run_reason?: string | null;
    error_status?: number | null;
    error_message?: string | null;
  } | null;
  institutional_flows?: {
    total_fpi_net_cr: number;
    total_dii_net_cr: number;
    net_institutional_liquidity_cr: number;
    fpi_dii_divergence_cr: number;
    primary_regime: string;
  } | null;
}

export interface AuditedCompany {
  symbol: string;
  periods_audited: string[];
}

export interface FilingCheck {
  symbol: string;
  period: string;
  rule_id: string;
  rule_name: string;
  claim_text: string;
  metric_name: string;
  metric_value: string | number;
  status: "PASS" | "FLAG" | "NOT_APPLICABLE" | string;
  evidence_summary?: string;
  rationale?: string;
}


export interface ColumnMapping {
  date: string;
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  fees?: string | null;
  charges?: string | null;
  exchange?: string | null;
  segment?: string | null;
}

export interface F3ReviewRequest {
  csv_text: string;
  mapping: ColumnMapping;
  consent_given: boolean;
  benchmark_symbol?: string;
  matched_index_symbol?: string | null;
}

export interface PortfolioPosition {
  symbol: string;
  quantity: number;
  average_cost: number;
  current_price?: number;
  current_value?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
}

export interface PortfolioSummary {
  positions?: Record<string, PortfolioPosition> | PortfolioPosition[];
  cash_balance?: number;
  total_cost: number;
  total_market_value: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
}

export interface BenchmarkReplay {
  benchmark_name: string;
  terminal_value: number;
  xirr: number | null;
  partial_shortfall: boolean;
}

export interface DispositionEffect {
  pgr?: number;
  plr?: number;
}

export interface ProcessMetrics {
  concentration_hhi: number;
  turnover: number;
  max_drawdown: number;
  disposition_effect?: DispositionEffect;
  process_label?: string | null;
}

export interface InstitutionalMetrics {
  beta: number;
  alpha: number;
  tracking_error: number;
  information_ratio: number;
}

export interface DecisionReview {
  portfolio: PortfolioSummary;
  portfolio_xirr: number | null;
  benchmark_replays: BenchmarkReplay[];
  process_metrics: ProcessMetrics;
  institutional_metrics?: InstitutionalMetrics | null;
  review_text: string;
  disclaimer: string;
  parameters_used?: Record<string, unknown>;
  is_synthetic?: boolean;
  synthetic_label?: string | null;
}
