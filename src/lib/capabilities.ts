import type { ModelIndexItem } from '@/types/data';

/** 能力维度定义（与 pipeline 的 capability-weights.yml 对应的前端子集）。 */
export const CAPABILITIES: { id: string; name: string; short: string; active: boolean }[] = [
  { id: 'overall', name: '综合能力', short: '综合', active: true },
  { id: 'reasoning', name: '逻辑推理', short: '推理', active: true },
  { id: 'math', name: '数学能力', short: '数学', active: true },
  { id: 'coding', name: '编程能力', short: '编程', active: true },
  { id: 'swe', name: '软件工程 / Issue 修复', short: '软件工程', active: true },
  { id: 'data_analysis', name: '数据分析', short: '数据分析', active: true },
  { id: 'instruction_following', name: '指令遵循', short: '指令遵循', active: true },
  { id: 'language', name: '英文语言能力', short: '语言', active: true },
  { id: 'creative_writing', name: '创意写作', short: '创意写作', active: true },
  { id: 'multimodal', name: '多模态视觉理解', short: '多模态', active: true },
  { id: 'chart', name: '图表与视觉数学理解', short: '图表理解', active: true },
  { id: 'ocr', name: 'OCR 与文档识别', short: 'OCR', active: true },
  { id: 'chinese', name: '中文能力（多模态中文基准）', short: '中文', active: true },
  { id: 'retrieval', name: '信息检索（Embedding）', short: '检索', active: true },
  { id: 'sts', name: '语义相似度（Embedding）', short: '语义相似度', active: true },
  { id: 'reranker', name: 'Reranker 重排序', short: '重排序', active: true },
  { id: 'chat_preference', name: '人类偏好与聊天体验', short: '人类偏好', active: false },
  { id: 'long_context', name: '长上下文', short: '长上下文', active: false },
  { id: 'agentic_general', name: 'Agent 自主执行', short: 'Agent', active: false },
  { id: 'tool_calling', name: '工具调用', short: '工具调用', active: false },
  { id: 'search_research', name: '搜索与深度研究', short: '深度研究', active: false },
  { id: 'image_gen', name: '图像生成', short: '图像生成', active: false },
  { id: 'video_gen', name: '视频生成', short: '视频生成', active: false },
  { id: 'speech', name: '语音识别 / 合成', short: '语音', active: false },
  { id: 'safety', name: '安全性', short: '安全', active: false },
  { id: 'robustness', name: '鲁棒性', short: '鲁棒性', active: false },
];

export const PENDING_CAPABILITIES = CAPABILITIES.filter((c) => !c.active).map((c) => c.name);

export interface WeightPreset {
  preset_id: string;
  name: string;
  weights: Record<string, number>;
}

/** 浏览器本地按权重重算综合指数（不调用服务器，与后端公式一致：加权平均能力指数）。 */
export function recomputeOverall(
  models: ModelIndexItem[],
  weights: Record<string, number>,
): { model: ModelIndexItem; index: number; capabilityCount: number }[] {
  const out: { model: ModelIndexItem; index: number; capabilityCount: number }[] = [];
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

/** 并列名次（competition ranking）。 */
export function assignRanks<T>(rows: T[], key: (row: T) => number): { rank: number; tie: boolean }[] {
  const sortedFlags = rows.map((r, i) => ({ v: key(r), i }));
  const ranks: { rank: number; tie: boolean }[] = new Array(rows.length);
  let currentRank = 0;
  for (let i = 0; i < sortedFlags.length; i++) {
    if (i === 0 || sortedFlags[i].v !== sortedFlags[i - 1].v) {
      currentRank = i + 1;
    }
    const tie = i > 0 && sortedFlags[i].v === sortedFlags[i - 1].v;
    ranks[sortedFlags[i].i] = { rank: currentRank, tie };
  }
  return ranks;
}
