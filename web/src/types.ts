export type Status =
  | "approved_baseline"
  | "baseline"
  | "commentary_only"
  | "current_context_only"
  | "disabled"
  | "quarantined"
  | "unavailable"
  | "baseline_only"
  | "shadow"
  | "commentary_shadow"
  | "registered_context_only";

export interface Stat {
  cagr: number;
  volatility: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  calmar: number;
  total_return: number;
  years: number;
  turnover: number;
  exposure: number;
}

export interface Study {
  as_of: string;
  start: string;
  settings: string;
  stats: Record<string, Stat>;
  curves: Record<string, number[] | string[]>;
  markets: Record<string, string>;
}

export interface Paper {
  start: string;
  capital: number;
  dates: string[];
  equity: number[];
  spy: number[];
  latest?: {
    date: string;
    equity: number;
    target: Record<string, number>;
    final: Record<string, number>;
    shadow_final?: Record<string, number>;
    review?: {
      status?: string;
      mode?: string;
      summary?: string;
      reports?: Record<string, string>;
      sources?: Array<{ title: string; url: string }>;
      models?: Record<string, string>;
      provider?: string;
      run_at?: string;
      input_hash?: string;
      errors?: string[];
    };
  };
  agents: {
    decisions: number;
    settled: number;
    shadow_cuts: number;
    shadow_effect_dates: string[];
    shadow_effect: number[];
  };
  trades: Array<Record<string, string | number | null>>;
}

export interface MacroPoint {
  date: string;
  value: number;
}

export interface MacroSeries {
  id: string;
  label: string;
  family: string;
  units: string;
  latest: number;
  previous: number | null;
  change: number | null;
  observation_date: string;
  eligibility: string;
  values: MacroPoint[];
}

export interface MacroContext {
  status: string;
  generated_at?: string;
  source?: { provider: string; url: string; vintage_policy: string };
  series: MacroSeries[];
  regimes: Array<{ name: string; state: string; rule: string }>;
  errors: Array<{ series_id: string; error: string }>;
  limitations: string[];
}

export interface IntradayContext {
  mode: string;
  status: string;
  feature_definition: {
    trend_horizons_hours: number[];
    volatility_windows_hours: number[];
    execution: string;
  };
  markets: Array<{ market: string; asset_class: string; status: string; session_rule: string; reason: string }>;
  records: unknown[];
  limitations: string[];
}

export interface ValidationContext {
  status: string;
  method: Record<string, string>;
  experiments: Array<{ id: string; state: string; description: string }>;
  required_evidence: string[];
}

export interface ProvenanceRecord {
  id: string;
  purpose: string;
  provider: string;
  status: string;
  rights_status: string;
  point_in_time_status: string;
  notes: string;
  market?: string;
  interval?: string;
}

export interface AppData {
  meta: { schema_version: string; generated_at: string; as_of: string | null; data_vintage: string; coverage_status: string };
  study: Study | null;
  paper: Paper | null;
  macro: MacroContext;
  intraday: IntradayContext;
  validation: ValidationContext;
  provenance: { policy: string; records: ProvenanceRecord[] };
  settings: { max_cut: number; target_vol: number; trend_floor: number; agent_mode: string };
}
