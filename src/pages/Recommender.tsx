import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useJson } from '@/lib/api';
import { useCapabilities, capName } from '@/lib/capabilities';
import type { CapabilityFile, ModelsIndex } from '@/types/data';
import { providerColor } from '@/types/data';
import { fmtScore } from '@/lib/format';
import { EmptyState, Skeleton } from '@/components/StateViews';

const TASK_OPTIONS = [
  { id: 'reasoning', label: '逻辑推理' },
  { id: 'coding', label: '编程开发' },
  { id: 'math', label: '数学' },
  { id: 'chinese_mm', label: '中文多模态理解' },
  { id: 'data_analysis', label: '数据分析' },
  { id: 'creative_writing', label: '创意写作' },
  { id: 'multimodal', label: '看图理解' },
];

interface TaskStat {
  benchmark_id: string;
  best: number;
  poolTop: number;
  poolSize: number;
}

/** 从官方原始榜计算某模型在某能力的相对位置（客户端计算，含未映射模型池，诚实口径）。 */
function officialPosition(file: CapabilityFile, modelId: string): TaskStat | null {
  // 选该能力下"模型自己有成绩且池子最大"的基准
  const benches = file.benchmarks.slice().sort((a, b) => b.record_count - a.record_count);
  for (const b of benches) {
    const rows = file.official.filter((r) => r.benchmark_id === b.benchmark_id);
    if (!rows.length) continue;
    const hib = rows[0].higher_is_better;
    const mine = rows.find((r) => r.model_id === modelId);
    if (!mine) continue;
    const sorted = rows.slice().sort((a2, b2) => (hib ? b2.score - a2.score : a2.score - b2.score));
    const rank = sorted.findIndex((r) => r.model_id === modelId) + 1;
    const poolTop = sorted[0].score;
    const best = mine.score;
    return { benchmark_id: b.benchmark_id, best, poolTop, poolSize: sorted.length || rank };
  }
  return null;
}

export function RecommenderPage() {
  const { capabilities } = useCapabilities();
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');
  const [input, setInput] = useState({
    task: 'reasoning',
    budget: 'any' as 'free' | 'low' | 'mid' | 'high' | 'any',
    needVision: false,
    needAgent: false,
    mustOpenWeights: false,
    localRun: false,
    valueSpeed: false,
    minContextK: 0,
  });
  const { data: taskCapFile } = useJson<CapabilityFile>(`/data/capabilities/${input.task}.json`);

  const results = useMemo(() => {
    if (!index || !taskCapFile) return [];
    const scored = [];
    for (const m of index.models) {
      const reasons: string[] = [];
      // 硬过滤
      if (input.mustOpenWeights && m.open_weights !== true) continue;
      if (input.localRun && m.open_weights !== true) continue;
      if (input.needVision && !(m.modalities.includes('image') || m.modalities.includes('video'))) continue;
      const limit = { free: 0, low: 1, mid: 5, high: null, any: null }[input.budget];
      if (limit !== null) {
        const price = m.price_input_usd_per_mtok;
        if (price === null || price === undefined) continue;
        if (limit === 0 && price > 0) continue;
        if (limit > 0 && price > limit) continue;
      }
      if (input.minContextK > 0 && (m.context_window ?? 0) < input.minContextK * 1000) continue;

      // 软评分：主任务用"官方原始分在官方榜中的相对位置"（诚实口径）
      let score = 0;
      const pos = officialPosition(taskCapFile, m.model_id);
      if (pos) {
        const rel = pos.poolTop > 0 ? (pos.best / pos.poolTop) * 100 : 50;
        score += rel * 0.6;
        reasons.push(
          `官方原始分 ${fmtScore(pos.best)}（官方榜相对位置约 ${Math.round(rel)}/${100}，池 ${pos.poolSize} 个模型）`,
        );
      } else {
        score += 30 * 0.3;
        reasons.push('该模型无此能力的官方成绩，按保守分处理');
      }
      if (m.overall_index !== null && m.overall_index !== undefined) {
        score += m.overall_index * 0.25;
        reasons.push(`多源相对百分位（综合）${m.overall_index.toFixed(1)}`);
      }
      if (input.needAgent) {
        const swe = m.capability_indices['swe'];
        if (swe !== undefined) {
          score += swe * 0.1;
          reasons.push('软件工程（模型+Agent）相对百分位参与加分');
        }
      }
      if (input.valueSpeed && m.output_speed_tps) {
        score += Math.min(15, m.output_speed_tps / 20);
        reasons.push(`输出速度 ${m.output_speed_tps.toFixed(0)} tok/s`);
      }
      if (input.mustOpenWeights || input.localRun) reasons.push('开放权重，可本地部署');
      if (m.price_input_usd_per_mtok === 0) {
        score += 5;
        reasons.push('免费 API');
      }
      scored.push({
        model: m,
        matchScore: Math.round(Math.min(100, score) * 10) / 10,
        reasons: reasons.slice(0, 4),
        uncertainty: (m.overall_source_count ?? 0) >= 2 ? '低' : (m.source_count ?? 0) >= 2 ? '中' : '高',
      });
    }
    scored.sort((a, b) => b.matchScore - a.matchScore);
    return scored.slice(0, 5);
  }, [index, taskCapFile, input]);

  const set = (patch: Partial<typeof input>) => setInput({ ...input, ...patch });

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">场景推荐</h1>
        <p className="mt-1 text-sm text-slate-400">
          纯规则推荐器：公开公式 + 确定性计算，不调用任何 AI 模型。主任务维度使用
          <b>官方原始分的相对位置</b>（诚实口径），不使用本站聚合百分位。
        </p>
      </header>

      <section className="panel px-5 py-6">
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-300">主要任务</p>
            <div className="flex flex-wrap gap-1.5">
              {TASK_OPTIONS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => set({ task: t.id })}
                  className={`rounded-lg px-3 py-1.5 text-sm ${t.id === input.task ? 'bg-cyan-400/15 text-cyan-300' : 'border border-slate-500/25 text-slate-400 hover:text-slate-200'}`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <p className="mb-2 mt-5 text-sm font-medium text-slate-300">预算（输入价 / 1M tokens）</p>
            <div className="flex flex-wrap gap-1.5">
              {[
                { id: 'free', label: '仅免费' },
                { id: 'low', label: '≤ $1' },
                { id: 'mid', label: '≤ $5' },
                { id: 'high', label: '不限' },
                { id: 'any', label: '含未公开价格' },
              ].map((b) => (
                <button
                  key={b.id}
                  onClick={() => set({ budget: b.id as typeof input.budget })}
                  className={`rounded-lg px-3 py-1.5 text-sm ${b.id === input.budget ? 'bg-cyan-400/15 text-cyan-300' : 'border border-slate-500/25 text-slate-400 hover:text-slate-200'}`}
                >
                  {b.label}
                </button>
              ))}
            </div>

            <p className="mb-2 mt-5 text-sm font-medium text-slate-300">最低上下文（K tokens）</p>
            <input
              type="range"
              min={0}
              max={1000}
              step={32}
              value={input.minContextK}
              onChange={(e) => set({ minContextK: Number(e.target.value) })}
              className="w-full accent-cyan-400"
              aria-label="最低上下文长度"
            />
            <p className="num mt-1 text-xs text-slate-400">{input.minContextK === 0 ? '不限' : `≥ ${input.minContextK}K`}</p>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-300">需求开关</p>
            <div className="grid grid-cols-1 gap-2">
              {([
                ['needVision', '需要看图 / 视觉'],
                ['needAgent', '需要 Agent 自动化'],
                ['mustOpenWeights', '必须开放权重'],
                ['localRun', '要本地部署（仅开放权重）'],
                ['valueSpeed', '重视输出速度'],
              ] as const).map(([key, label]) => (
                <label key={key} className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-slate-500/20 px-3 py-2 text-sm text-slate-300 hover:border-slate-400/40">
                  <input
                    type="checkbox"
                    className="accent-cyan-400"
                    checked={input[key] as boolean}
                    onChange={(e) => set({ [key]: e.target.checked } as Partial<typeof input>)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>
      </section>

      {!index || !taskCapFile ? (
        <Skeleton rows={5} />
      ) : results.length === 0 ? (
        <EmptyState title="没有满足全部硬性条件的模型" hint="试着放宽预算或上下文要求，或取消「必须开放权重」。" />
      ) : (
        <section className="space-y-4">
          <p className="text-xs text-slate-500">
            匹配度 = 0.6×主任务官方相对位置 + 0.25×综合相对百分位 + 加成项（Agent/速度/免费），满分 100。
            价格未公开的模型不进入受限预算推荐。
          </p>
          {results.map((r, i) => (
            <article key={r.model.model_id} className="panel px-5 py-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`num text-xl font-black ${i === 0 ? 'rank-medal-1' : i === 1 ? 'rank-medal-2' : i === 2 ? 'rank-medal-3' : 'text-slate-500'}`}>
                  #{i + 1}
                </span>
                <span className="h-3 w-3 rounded-full" style={{ background: providerColor(r.model.provider) }} aria-hidden />
                <Link to={`/model/${r.model.model_id}`} className="text-base font-semibold text-slate-100 hover:text-cyan-300">
                  {r.model.display_name}
                </Link>
                <span className="text-xs text-slate-500">{r.model.provider ?? '未知厂商'}</span>
                <span className="ml-auto flex items-center gap-3 text-sm">
                  <span className="badge">不确定性 {r.uncertainty}</span>
                  <span className="num text-lg font-bold text-cyan-300">{r.matchScore.toFixed(1)}</span>
                </span>
              </div>
              <ul className="mt-2.5 flex flex-wrap gap-1.5">
                {r.reasons.map((reason, j) => (
                  <li key={j} className="badge border-cyan-400/20 bg-cyan-400/5 text-cyan-200/90">{reason}</li>
                ))}
              </ul>
            </article>
          ))}
          <p className="text-xs text-slate-500">
            替代选择即列表第 2~5 名；公式细节见
            <Link to="/methodology" className="mx-1 text-cyan-400 hover:text-cyan-300">方法论</Link>
            页。当前还缺 {capabilities.filter((c) => c.status === 'pending').length} 项能力的数据
            （{capabilities.filter((c) => c.status === 'pending').slice(0, 3).map((c) => capName(capabilities, c.capability_id)).join('、')}
            等），它们不参与本页计算。
          </p>
        </section>
      )}
    </div>
  );
}
