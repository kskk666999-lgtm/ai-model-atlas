/** 与 pipeline 生成的静态 JSON 对应的前端类型（关键字段用 zod 校验）。 */
import { z } from 'zod';

export const MetaSchema = z.object({
  generated_at: z.string(),
  pipeline_version: z.string(),
  demo_mode: z.boolean(),
  site_name: z.string(),
  latest_commit: z.string().nullable().optional(),
  counts: z.object({
    models: z.number(),
    unmapped_models: z.number(),
    benchmarks: z.number(),
    capabilities_active: z.number(),
    records: z.number(),
    sources_active: z.number(),
    history_snapshots: z.number(),
  }),
  update: z.object({
    interval_hours: z.number(),
    last_success: z.string().nullable(),
    failed_sources: z.array(z.string()),
    degraded_sources: z.array(z.string()),
  }),
  weight_presets: z
    .array(z.object({ preset_id: z.string(), name: z.string(), weights: z.record(z.number()) }))
    .optional(),
});

export type Meta = z.infer<typeof MetaSchema>;

export interface CapIndexEntry {
  index: number;
  rank: number;
}

export interface ModelIndexItem {
  model_id: string;
  display_name: string;
  provider: string;
  family: string;
  variant: string | null;
  region: string | null;
  open_weights: boolean | null;
  license: string | null;
  modalities: string[];
  context_window: number | null;
  release_date: string | null;
  official_model_page: string | null;
  capability_indices: Record<string, number>;
  overall_index: number | null;
  overall_rank: number | null;
  overall_benchmark_count: number | null;
  overall_source_count: number | null;
  price_input_usd_per_mtok: number | null;
  price_output_usd_per_mtok: number | null;
  output_speed_tps: number | null;
  latency_seconds: number | null;
  benchmark_count: number;
  benchmark_total?: number;
  coverage?: number;
  source_count: number;
  rank_changes: Record<string, { d7?: number; d30?: number }>;
}

export interface ModelsIndex {
  generated_at: string;
  models: ModelIndexItem[];
}

export interface OfficialRow {
  benchmark_id: string;
  benchmark_name: string;
  capability: string;
  source_id: string;
  source_name: string;
  source_level: 'A' | 'B' | 'C' | 'D';
  source_url: string;
  model_id: string;
  raw_model_name: string | null;
  model_is_unmapped: boolean;
  score: number;
  score_unit: string;
  higher_is_better: boolean;
  rank: number;
  tie?: boolean;
  evaluation_date: string | null;
  evaluation_target_type: string;
  agent_scaffold: string | null;
  prompt_mode: string | null;
  benchmark_version: string | null;
  sample_size: number | null;
  notes?: string | null;
  fetched_at: string;
  record_verification_status?: 'maintainer_verified' | 'third_party_submitted' | 'unknown';
  data_file_url?: string | null;
  data_json_path?: string | null;
  data_sha256?: string | null;
  upstream_updated_at?: string | null;
}

export interface CompositeModel {
  model_id: string;
  index: number;
  rank: number;
  tie: boolean;
  benchmark_count: number;
  benchmark_total?: number;
  coverage?: number;
  source_count: number;
  single_source: boolean;
  confidence: 'high' | 'medium' | 'low';
  per_benchmark: { benchmark_id: string; percentile: number }[];
}

export interface CapabilityFile {
  capability_id: string;
  name: string;
  short: string;
  status: 'active' | 'pending';
  description: string | null;
  generated_at: string;
  benchmarks: {
    benchmark_id: string;
    benchmark_name: string;
    source_id: string;
    higher_is_better: boolean;
    score_unit: string;
    record_count: number;
  }[];
  official: OfficialRow[];
  composite: {
    method: string;
    benchmark_count: number;
    source_count: number;
    models: CompositeModel[];
  } | null;
}

export interface SourceHealthItem {
  source_id: string;
  source_name: string;
  source_level: 'A' | 'B' | 'C' | 'D';
  homepage_url: string | null;
  docs_url: string | null;
  description: string | null;
  license: string | null;
  attribution: string | null;
  requires_api_key: boolean;
  included_in_composite: boolean;
  registry_status: 'active' | 'disabled' | 'optional';
  run_status: 'ok' | 'degraded' | 'failed' | 'skipped' | 'disabled';
  record_count: number;
  last_success: string | null;
  error_message: string | null;
  response_time_ms?: number | null;
  data_freshness: string | null;
}

export interface SourceHealth {
  generated_at: string;
  counts: { healthy: number; degraded: number; failed: number; disabled: number };
  sources: SourceHealthItem[];
}

export interface Homepage {
  generated_at: string;
  stats: Meta['counts'];
  update: Meta['update'];
  top3: Record<string, { model_id: string; display_name: string; provider: string | null; index: number; rank: number }[]>;
  movers_7d: { model_id: string; display_name: string; provider: string; capability: string; delta: number }[];
  trend_30d: { date: string; models: number; capabilities: number }[];
}

export interface ModelDetail {
  generated_at: string;
  meta: ModelIndexItem;
  radar: { capability_id: string; name: string; index: number; rank: number }[];
  records: OfficialRow[];
  history: Record<string, { date: string; rank: number | null; index: number | null }[]>;
}

export const PROVIDER_COLORS: Record<string, string> = {
  OpenAI: '#10a37f',
  Anthropic: '#d97757',
  Google: '#4285f4',
  DeepSeek: '#4d6bfe',
  Alibaba: '#615ced',
  'Zhipu AI': '#3859ff',
  'Moonshot AI': '#00b96b',
  xAI: '#c8cdd8',
  Meta: '#0866ff',
  'Mistral AI': '#fa500f',
  Amazon: '#ff9900',
  Cohere: '#d18ee2',
  'Shanghai AI Lab': '#00c2a8',
  StepFun: '#7c5cff',
  ByteDance: '#325ab4',
  BAAI: '#2d7ff9',
  intfloat: '#8b5cf6',
  'Alibaba-NLP': '#615ced',
  'Voyage AI': '#f43f5e',
  'Jina AI': '#f59e0b',
  'Nomic AI': '#22d3ee',
  OpenGVLab: '#00c2a8',
};

export function providerColor(provider: string | null | undefined): string {
  if (!provider) return '#64748b';
  if (PROVIDER_COLORS[provider]) return PROVIDER_COLORS[provider];
  let h = 0;
  for (let i = 0; i < provider.length; i++) h = (h * 31 + provider.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360} 60% 60%)`;
}
