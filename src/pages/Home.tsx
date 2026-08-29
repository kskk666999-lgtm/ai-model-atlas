import { Link } from 'react-router-dom';
import { ArrowDownRight, ArrowUpRight, Boxes, FlaskConical, Layers, TrendingUp } from 'lucide-react';
import { useJson, useMeta } from '@/lib/api';
import { CAPABILITIES, recomputeOverall, type WeightPreset } from '@/lib/capabilities';
import { fmtDate, fmtDateTime } from '@/lib/format';
import { providerColor } from '@/types/data';
import { EmptyState, NoDataState } from '@/components/StateViews';
import { UpdateStatusPanel } from '@/components/UpdateStatusPanel';
import type { Homepage, Meta, ModelsIndex } from '@/types/data';
import { useState } from 'react';

const TOP3_CAPS = ['reasoning', 'coding', 'math', 'chinese', 'multimodal', 'swe'];
const TOP3_NAMES: Record<string, string> = {
  reasoning: '逻辑推理',
  coding: '编程',
  math: '数学',
  chinese: '中文',
  multimodal: '多模态',
  swe: '软件工程',
};

export function HomePage() {
  const { meta: rawMeta, loading: metaLoading, error } = useMeta();
  const { data: home } = useJson<Homepage>('/data/homepage.json');
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');
  const [presetId, setPresetId] = useState('general');

  if (error && !rawMeta) {
    return <NoDataState detail={`meta.json 加载失败：${error}`} />;
  }

  const meta: Meta | null = rawMeta;
  const presets = (meta?.weight_presets ?? []) as unknown as WeightPreset[];
  const preset = presets.find((p) => p.preset_id === presetId) ?? presets[0];
  // 综合榜只收录通过服务端准入门槛（≥4 能力 / ≥5 基准 / ≥2 来源）的模型，
  // 即 models/index.json 中 overall_index 非空的模型；权重预设切换仍在浏览器本地重算。
  const gatedModels = (index?.models ?? []).filter((m) => m.overall_index !== null);
  const overallRows = preset ? recomputeOverall(gatedModels, preset.weights).slice(0, 10) : [];
  const ranks = assignRanksLocal(overallRows.map((r) => r.index));

  return (
    <div className="flex flex-col gap-6 lg:flex-row-reverse">
      <UpdateStatusPanel meta={meta} />

      <div className="min-w-0 flex-1 space-y-8">
        {/* Hero */}
        <section className="panel relative overflow-hidden px-6 py-8 sm:px-10 sm:py-12">
          <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" aria-hidden />
          <p className="text-xs font-medium uppercase tracking-[0.3em] text-cyan-300/80">AI Model Atlas</p>
          <h1 className="mt-3 text-3xl font-black leading-tight text-slate-50 sm:text-4xl">
            全球 AI 模型能力
            <span className="bg-gradient-to-r from-cyan-300 to-violet-400 bg-clip-text text-transparent">可视化天梯</span>
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 sm:text-[15px]">
            汇集 LiveBench、SWE-bench、BigCodeBench、VLMEvalKit/OpenVLM、MTEB 等官方结构化评测结果，
            按推理、编程、数学、中文、多模态等能力独立成榜。每一条分数都可以点开查看原始出处；
            综合指数是本站基于官方原始分的确定性计算，不调用任何大模型。
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/leaderboard" className="rounded-xl bg-gradient-to-r from-cyan-400 to-cyan-500 px-5 py-2.5 text-sm font-semibold text-[#05070d] hover:from-cyan-300 hover:to-cyan-400">
              浏览能力榜单
            </Link>
            <Link to="/compare" className="rounded-xl border border-slate-500/40 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:border-slate-300">
              对比 2~6 个模型
            </Link>
            <Link to="/methodology" className="rounded-xl border border-slate-500/40 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:border-slate-300">
              排名是怎么算的
            </Link>
          </div>

          <dl className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat icon={<Boxes size={16} className="text-cyan-300" />} label="收录模型" value={meta?.counts.models} loading={metaLoading} />
            <Stat icon={<Layers size={16} className="text-violet-300" />} label="接入基准" value={meta?.counts.benchmarks} loading={metaLoading} />
            <Stat icon={<FlaskConical size={16} className="text-emerald-300" />} label="有效数据源" value={meta?.counts.sources_active} loading={metaLoading} />
            <Stat icon={<TrendingUp size={16} className="text-amber-300" />} label="最近更新" value={fmtDate(meta?.update.last_success)} loading={metaLoading} />
          </dl>
        </section>

        {/* 综合榜 + 权重预设 */}
        <section className="panel px-5 py-6 sm:px-7">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-bold text-slate-100">综合指数榜</h2>
            <span className="badge border-violet-400/40 bg-violet-400/10 text-violet-200">本站计算 · 非官方榜单</span>
            <div className="ml-auto flex flex-wrap gap-1.5">
              {presets.map((p) => (
                <button
                  key={p.preset_id}
                  onClick={() => setPresetId(p.preset_id)}
                  className={`rounded-lg px-2.5 py-1 text-xs ${
                    p.preset_id === presetId
                      ? 'bg-cyan-400/15 text-cyan-300'
                      : 'border border-slate-500/30 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            加权平均各能力指数（0~100）。切换预设即在浏览器本地重算，权重公式见方法论页。
            综合榜仅收录覆盖 ≥4 能力、≥5 基准、≥2 数据来源的模型；Agent 系统成绩不参与。
          </p>
          {overallRows.length === 0 ? (
            <div className="mt-4"><EmptyState title="暂无满足多源覆盖要求的模型" hint="综合榜要求模型在多个独立数据来源都有成绩；请先查看单项能力榜单。" /></div>
          ) : (
            <ol className="mt-4 divide-y divide-slate-500/10">
              {overallRows.map((row, i) => (
                <li key={row.model.model_id} className="flex items-center gap-3 py-2.5">
                  <span className={`num w-8 text-center text-sm font-bold ${ranks[i] === 1 ? 'rank-medal-1' : ranks[i] === 2 ? 'rank-medal-2' : ranks[i] === 3 ? 'rank-medal-3' : 'text-slate-400'}`}>
                    {ranks[i]}
                  </span>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: providerColor(row.model.provider) }} aria-hidden />
                  <Link to={`/model/${row.model.model_id}`} className="min-w-0 flex-1 truncate text-sm font-medium text-slate-100 hover:text-cyan-300">
                    {row.model.display_name}
                  </Link>
                  <span className="hidden text-xs text-slate-500 sm:inline">{row.model.provider ?? '未知厂商'}</span>
                  <span className="num w-14 text-right text-sm font-semibold text-cyan-300">{row.index.toFixed(1)}</span>
                </li>
              ))}
            </ol>
          )}
        </section>

        {/* 各能力前三 */}
        <section>
          <h2 className="mb-3 text-lg font-bold text-slate-100">单项能力 · 前三名</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {TOP3_CAPS.map((cap) => {
              const top3 = home?.top3?.[cap] ?? [];
              return (
                <Link key={cap} to={`/leaderboard?cap=${cap}`} className="panel block px-5 py-4 transition-colors hover:border-cyan-400/40">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-100">{TOP3_NAMES[cap]}</h3>
                    <span className="text-xs text-slate-500">指数 · 本站计算</span>
                  </div>
                  {top3.length === 0 ? (
                    <p className="mt-3 text-sm text-slate-500">数据接入中</p>
                  ) : (
                    <ol className="mt-3 space-y-2">
                      {top3.map((m, i) => (
                        <li key={m.model_id} className="flex items-center gap-2 text-sm">
                          <span className={`num w-5 font-bold ${i === 0 ? 'rank-medal-1' : i === 1 ? 'rank-medal-2' : 'rank-medal-3'}`}>{i + 1}</span>
                          <span className="h-2 w-2 rounded-full" style={{ background: providerColor(m.provider) }} aria-hidden />
                          <span className="min-w-0 flex-1 truncate text-slate-200">{m.display_name}</span>
                          <span className="num text-xs text-cyan-300">{m.index.toFixed(1)}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </Link>
              );
            })}
          </div>
        </section>

        {/* 7 天上升最快 */}
        {home && home.movers_7d.length > 0 && (
          <section className="panel px-5 py-6 sm:px-7">
            <h2 className="text-lg font-bold text-slate-100">最近 7 天排名上升最快</h2>
            <ul className="mt-4 space-y-2.5">
              {home.movers_7d.map((m, i) => (
                <li key={`${m.model_id}-${m.capability}`} className="flex items-center gap-3 text-sm">
                  <span className="num w-6 text-slate-500">{i + 1}</span>
                  <Link to={`/model/${m.model_id}`} className="min-w-0 flex-1 truncate font-medium text-slate-100 hover:text-cyan-300">
                    {m.display_name}
                  </Link>
                  <span className="badge">{capName(m.capability)}</span>
                  <span className="num flex items-center gap-1 text-emerald-300">
                    <ArrowUpRight size={14} aria-hidden /> {m.delta}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* 暂待接入能力 */}
        <section className="panel px-5 py-6 sm:px-7">
          <h2 className="text-lg font-bold text-slate-100">数据接入中的能力</h2>
          <p className="mt-1.5 text-xs text-slate-500">
            以下能力暂无满足本站可信标准的公开结构化数据源。宁可显示"接入中"，也不生成模拟排名。
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {CAPABILITIES.filter((c) => !c.active).map((c) => (
              <span key={c.id} className="badge opacity-70">{c.name} · 接入中</span>
            ))}
          </div>
          <p className="mt-4 flex items-center gap-1.5 text-xs text-slate-500">
            <ArrowDownRight size={13} className="text-slate-600" aria-hidden />
            上次数据更新：{fmtDateTime(home?.update.last_success ?? meta?.update.last_success)}（UTC）
          </p>
        </section>
      </div>
    </div>
  );
}

function Stat({ icon, label, value, loading }: { icon: React.ReactNode; label: string; value: number | string | null | undefined; loading: boolean }) {
  return (
    <div className="panel-2 px-4 py-3">
      <dt className="flex items-center gap-1.5 text-xs text-slate-400">{icon} {label}</dt>
      <dd className="num mt-1 text-xl font-bold text-slate-100">
        {loading ? <span className="skeleton inline-block h-6 w-16 align-middle" /> : (value ?? '—')}
      </dd>
    </div>
  );
}

function capName(id: string): string {
  return TOP3_NAMES[id] ?? CAPABILITIES.find((c) => c.id === id)?.short ?? id;
}

function assignRanksLocal(values: number[]): number[] {
  const ranks: number[] = [];
  let current = 0;
  for (let i = 0; i < values.length; i++) {
    if (i === 0 || values[i] !== values[i - 1]) current = i + 1;
    ranks.push(current);
  }
  return ranks;
}
