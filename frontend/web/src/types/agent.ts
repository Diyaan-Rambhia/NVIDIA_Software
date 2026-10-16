export interface AgentStep {
  step_number: number;
  tool_name: string;
  input_summary: string;
  output_summary: string;
  status: "success" | "denied" | "error" | string;
  est_cost_usd: number;
  duration_ms: number;
}

export interface AgentAskRequest {
  query: string;
  budget_usd?: number | null;
  max_steps?: number | null;
}

export interface AgentAskResponse {
  query: string;
  answer: string;
  steps: AgentStep[];
  total_cost_usd: number;
  duration_ms: number;
  disclaimer?: string;
  is_placeholder?: boolean;
}

export interface NemotronCallRequest {
  prompt: string;
  alias?: string;
}

export interface NemotronCallResponse {
  status: string;
  alias: string;
  model_id: string;
  response: string;
  unverified_note?: string;
}

export interface OpsStatus {
  app_env: string;
  code_version: string;
  python_version: string;
  uptime_seconds: number;
  enabled_groups: string[];
}

export interface OpsConfigVar {
  name: string;
  present: boolean;
  required_when_enabled: boolean;
  group_enabled: boolean;
}

export interface OpsConfig {
  enabled_groups: string[];
  groups: Record<string, OpsConfigVar[]>;
}

export interface OpsParameter {
  type: string;
  default: unknown;
  min?: number | null;
  max?: number | null;
  override_allowed: boolean;
  unit?: string | null;
}

export interface OpsParameters {
  parameters: Record<string, OpsParameter>;
}

export interface OpsEvent {
  id: string;
  ts: string | null;
  kind: string;
  subject: string;
  status: string;
  duration_ms: number | null;
}

export interface OpsLlmRow {
  id: string;
  ts: string | null;
  route: string;
  alias: string;
  model_id: string;
  input_tokens: number;
  output_tokens: number;
  est_cost_usd: number;
  cache_hit: boolean;
}
