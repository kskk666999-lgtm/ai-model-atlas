/** 能力定义：唯一来源是流水线生成的 /data/capabilities/index.json
 * （由 data/registry/capabilities.yml 生成）。本文件只提供加载与兜底，
 * 禁止再手写独立的能力数组。 */
import { useJson } from '@/lib/api';

export interface CapabilityDef {
  capability_id: string;
  name: string;
  short: string;
  group: string;
  status: 'active' | 'pending';
  description?: string | null;
  planned_source?: string | null;
  benchmark_count: number;
  official_record_count?: number;
  current_model_count?: number;
  primary_benchmark_id?: string | null;
  primary_benchmark_name?: string | null;
  latest_evaluation_date?: string | null;
  latest_snapshot_date?: string | null;
  latest_evidence_date?: string | null;
  coverage_status?: 'current' | 'history_only' | 'pending' | 'unavailable';
  has_composite: boolean;
}

export interface CapabilityGroup {
  group_id: string;
  name: string;
}

export interface CapabilitiesIndex {
  generated_at: string;
  groups: CapabilityGroup[];
  capabilities: CapabilityDef[];
  weight_presets: { preset_id: string; name: string; weights: Record<string, number> }[];
}

/** 首屏兜底：仅 id/名称/分组（完整数据以 index.json 为准）。 */
export const FALLBACK_CAPABILITIES: CapabilityDef[] = [
  { capability_id: 'reasoning', name: '逻辑推理', short: '推理', group: 'text_reasoning', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'math', name: '数学能力', short: '数学', group: 'text_reasoning', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'coding', name: '编程能力', short: '编程', group: 'coding_agent', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'swe', name: '软件工程（模型 + Agent 系统）', short: '软件工程', group: 'coding_agent', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'agentic_general', name: 'Agent 自主执行（电脑/终端）', short: 'Agent 通用', group: 'safety', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'tool_calling', name: '工具调用', short: '工具调用', group: 'safety', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'multimodal', name: '多模态视觉理解', short: '多模态', group: 'multimodal', status: 'active', benchmark_count: 0, has_composite: false },
  { capability_id: 'chinese_mm', name: '中文多模态理解', short: '中文多模态', group: 'multimodal', status: 'active', benchmark_count: 0, has_composite: false },
];

export const FALLBACK_GROUPS: CapabilityGroup[] = [
  { group_id: 'text_reasoning', name: '文本与推理' },
  { group_id: 'coding_agent', name: '编程与 Agent' },
  { group_id: 'multimodal', name: '多模态' },
  { group_id: 'cost_efficiency', name: '成本与效率' },
  { group_id: 'safety', name: '安全与可靠性' },
];

export function useCapabilities(): {
  capabilities: CapabilityDef[];
  groups: CapabilityGroup[];
  presets: CapabilitiesIndex['weight_presets'];
  loaded: boolean;
} {
  const { data } = useJson<CapabilitiesIndex>('/data/capabilities/index.json');
  return {
    capabilities: data?.capabilities ?? FALLBACK_CAPABILITIES,
    groups: data?.groups ?? FALLBACK_GROUPS,
    presets: data?.weight_presets ?? [],
    loaded: Boolean(data),
  };
}

export function capName(caps: CapabilityDef[], id: string): string {
  const c = caps.find((x) => x.capability_id === id);
  return c?.name ?? c?.short ?? id;
}

export function capShort(caps: CapabilityDef[], id: string): string {
  const c = caps.find((x) => x.capability_id === id);
  return c?.short ?? id;
}

/** 浏览器本地按权重重算"单源参考综合榜"（不调用服务器）。
 * 注意：结果为相对百分位的加权，仅作浏览参考，不可视为多源共识。 */
export function recomputeOverall(
  models: ModelLike[],
  weights: Record<string, number>,
): { model: ModelLike; index: number; capabilityCount: number }[] {
  const out: { model: ModelLike; index: number; capabilityCount: number }[] = [];
  for (const m of models) {
    let weighted = 0;
    let total = 0;
    let count = 0;
    for (const [cap, w] of Object.entries(weights)) {
      if (w <= 0) continue;
      const v = m.capability_indices[cap];
      if (v === undefined) continue;
      weighted += v * w;
      total += w;
      count += 1;
    }
    if (total > 0) out.push({ model: m, index: weighted / total, capabilityCount: count });
  }
  out.sort((a, b) => b.index - a.index || a.model.model_id.localeCompare(b.model.model_id));
  return out;
}

export interface ModelLike {
  model_id: string;
  capability_indices: Record<string, number>;
  overall_index?: number | null;
  source_count?: number;
  overall_source_count?: number | null;
}

/** 并列名次（competition ranking）。 */
export function assignRanksLocal(values: number[]): number[] {
  const ranks: number[] = [];
  let current = 0;
  for (let i = 0; i < values.length; i++) {
    if (i === 0 || values[i] !== values[i - 1]) current = i + 1;
    ranks.push(current);
  }
  return ranks;
}
