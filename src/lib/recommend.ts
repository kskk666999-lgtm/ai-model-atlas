import type { ModelIndexItem } from '@/types/data';
import { CAPABILITIES } from './capabilities';

export interface RecommendInput {
  task: string; // capability id
  budget: 'free' | 'low' | 'mid' | 'high' | 'any';
  needChinese: boolean;
  needVision: boolean;
  needAgent: boolean;
  mustOpenWeights: boolean;
  localRun: boolean;
  valueSpeed: boolean;
  minContextK: number;
}

export interface Recommendation {
  model: ModelIndexItem;
  matchScore: number; // 0~100
  reasons: string[];
  coverage: number; // 数据覆盖的能力数
  uncertainty: '低' | '中' | '高';
  matched: boolean[]; // 与 hardFilters 对应
}

const BUDGET_LIMITS: Record<RecommendInput['budget'], number | null> = {
  free: 0,
  low: 1,
  mid: 5,
  high: null,
  any: null,
};

/**
 * 纯规则推荐器（无任何模型调用）。
 * 硬过滤：开放权重 / 本地运行 / 最低上下文 / 免费预算。
 * 软评分：任务能力指数 + 中文/多模态加成 + 速度加成。
 */
export function recommend(models: ModelIndexItem[], input: RecommendInput): Recommendation[] {
  const results: Recommendation[] = [];
  const taskCap = CAPABILITIES.find((c) => c.id === input.task)?.id ?? 'reasoning';

  for (const m of models) {
    const reasons: string[] = [];

    // ---- 硬过滤 ----
    if (input.mustOpenWeights && m.open_weights !== true) continue;
    if (input.localRun && m.open_weights !== true) continue;
    if (input.needVision && !(m.modalities.includes('image') || m.modalities.includes('video'))) continue;
    const limit = BUDGET_LIMITS[input.budget];
    if (limit !== null) {
      const price = m.price_input_usd_per_mtok;
      if (price === null || price === undefined) continue; // 价格未知不进入价格受限推荐
      if (limit === 0 && price > 0) continue;
      if (limit > 0 && price > limit) continue;
    }
    if (input.minContextK > 0 && (m.context_window ?? 0) < input.minContextK * 1000) continue;

    // ---- 软评分 ----
    let score = 0;
    const taskIdx = m.capability_indices[taskCap];
    if (taskIdx !== undefined) {
      score += taskIdx * 0.6;
      reasons.push(`${capName(taskCap)}指数 ${taskIdx.toFixed(1)}`);
    } else {
      score += 40 * 0.3; // 缺数据时给保守中性分（不是 0）
      reasons.push('该能力暂无该模型数据，按保守分处理');
    }

    const overall = m.overall_index;
    if (overall !== null && overall !== undefined) {
      score += overall * 0.25;
      reasons.push(`综合指数 ${overall.toFixed(1)}（${m.overall_source_count ?? '—'} 个来源）`);
    }

    if (input.needChinese) {
      const zh = m.capability_indices['chinese'];
      if (zh !== undefined) {
        score += zh * 0.15;
        reasons.push(`中文（多模态中文基准）指数 ${zh.toFixed(1)}`);
      }
    }
    if (input.needAgent) {
      const swe = m.capability_indices['swe'];
      if (swe !== undefined) {
        score += swe * 0.1;
        reasons.push(`软件工程（模型+Agent）指数 ${swe.toFixed(1)}`);
      }
    }
    if (input.valueSpeed && m.output_speed_tps) {
      score += Math.min(15, m.output_speed_tps / 20);
      reasons.push(`输出速度 ${m.output_speed_tps.toFixed(0)} tok/s`);
    }
    if (input.mustOpenWeights || input.localRun) {
      reasons.push('开放权重，可本地部署');
    }
    if (m.price_input_usd_per_mtok === 0) {
      score += 5;
      reasons.push('免费 API');
    }

    const coverage = Object.keys(m.capability_indices).length;
    const uncertainty: '低' | '中' | '高' =
      (m.overall_source_count ?? 0) >= 2 ? '低' : (m.source_count ?? 0) >= 2 ? '中' : '高';

    results.push({
      model: m,
      matchScore: Math.round(Math.min(100, score) * 10) / 10,
      reasons: reasons.slice(0, 4),
      coverage,
      uncertainty,
      matched: [],
    });
  }

  results.sort((a, b) => b.matchScore - a.matchScore);
  return results.slice(0, 5);
}

function capName(id: string): string {
  return CAPABILITIES.find((c) => c.id === id)?.name ?? id;
}
