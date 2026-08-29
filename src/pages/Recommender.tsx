import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useJson } from '@/lib/api';
import type { ModelsIndex } from '@/types/data';
import { providerColor } from '@/types/data';
import { CAPABILITIES } from '@/lib/capabilities';
import { recommend, type RecommendInput } from '@/lib/recommend';
import { EmptyState, Skeleton } from '@/components/StateViews';

const TASK_OPTIONS = [
  { id: 'reasoning', label: '逻辑推理' },
  { id: 'coding', label: '编程开发' },
  { id: 'math', label: '数学' },
  { id: 'chinese', label: '中文任务' },
  { id: 'data_analysis', label: '数据分析' },
  { id: 'creative_writing', label: '创意写作' },
  { id: 'multimodal', label: '看图理解' },
  { id: 'swe', label: 'Agent 编程自动化' },
];

export function RecommenderPage() {
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');
  const [input, setInput] = useState<RecommendInput>({
    task: 'reasoning',
    budget: 'any',
    needChinese: false,
    needVision: false,
    needAgent: false,
    mustOpenWeights: false,
    localRun: false,
    valueSpeed: false,
    minContextK: 0,
  });

  const results = useMemo(() => (index ? recommend(index.models, input) : []), [index, input]);
  const set = (patch: Partial<RecommendInput>) => setInput({ ...input, ...patch });

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">场景推荐</h1>
        <p className="mt-1 text-sm text-slate-400">
          纯规则推荐器：公开公式 + 确定性计算，不调用任何 AI 模型。勾选你的需求，立刻得到推荐与理由。
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
                  onClick={() => set({ budget: b.id as RecommendInput['budget'] })}
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
                ['needChinese', '需要中文能力'],
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
                    onChange={(e) => set({ [key]: e.target.checked } as Partial<RecommendInput>)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>
      </section>

      {!index ? (
        <Skeleton rows={5} />
      ) : results.length === 0 ? (
        <EmptyState title="没有满足全部硬性条件的模型" hint="试着放宽预算或上下文要求，或取消“必须开放权重”。" />
      ) : (
        <section className="space-y-4">
          <p className="text-xs text-slate-500">
            匹配度 = 0.6×任务能力指数 + 0.25×综合指数 + 加成项（中文/Agent/速度/免费），满分 100。
            价格未公开的模型不进入受限预算的推荐，避免误导。
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
                  <span className="badge">覆盖率 {r.coverage} 项能力</span>
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
            替代选择即列表第 2~5 名；若你对结果有疑问，可在
            <Link to="/methodology" className="mx-1 text-cyan-400 hover:text-cyan-300">方法论</Link>
            页查看完整公式。当前还缺 {CAPABILITIES.filter((c) => !c.active).length} 项能力的数据（显示为接入中），
            它们不参与本页计算。
          </p>
        </section>
      )}
    </div>
  );
}
