import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useJson } from '@/lib/api';
import { useCapabilities } from '@/lib/capabilities';
import type { CapabilityFile, ModelsIndex, OfficialRow } from '@/types/data';
import { Skeleton, EmptyState, ErrorState } from '@/components/StateViews';
import {
  OfficialTable,
  SearchInput,
  FilterBar,
  applyOfficialFilters,
  emptyOfficialFilters,
  filterCurrent,
  joinRows,
  type OfficialFilters,
  type JoinedRow,
} from '@/components/OfficialTable';
import { SourceDrawer } from '@/components/Badges';

export function LeaderboardPage() {
  const [params, setParams] = useSearchParams();
  const capId = params.get('cap') || 'reasoning';
  const [mode, setMode] = useState<'official' | 'composite'>('official');
  const [benchmarkId, setBenchmarkId] = useState<string>('');
  const [filters, setFilters] = useState<OfficialFilters>(emptyOfficialFilters);
  const [picked, setPicked] = useState<OfficialRow | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const { capabilities, groups } = useCapabilities();
  const capMeta = capabilities.find((c) => c.capability_id === capId);
  const { data, error, loading } = useJson<CapabilityFile>(`/data/capabilities/${capId}.json`);
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');

  useEffect(() => {
    // 切换能力时恢复安全默认值，避免上一页开启的 HISTORY 状态带入 Agent 榜。
    setShowHistory(false);
    setBenchmarkId(capMeta?.primary_benchmark_id ?? '');
  }, [capId, capMeta?.primary_benchmark_id]);

  const { currentRows, legacyRows } = useMemo(() => {
    if (!data) return { currentRows: [] as JoinedRow[], legacyRows: [] as JoinedRow[] };
    const official =
      benchmarkId === ''
        ? data.official
        : data.official.filter((r) => r.benchmark_id === benchmarkId);
    const all = applyOfficialFilters(joinRows(official, index?.models ?? []), filters);
    const { current, legacy } = filterCurrent(all);
    return { currentRows: current, legacyRows: legacy };
  }, [data, index, filters, benchmarkId]);
  const rows = showHistory
    ? [...currentRows, ...legacyRows].sort((a, b) => a.rank - b.rank)
    : currentRows;
  const currentModelCount = new Set(currentRows.map((row) => row.model_id)).size;

  const providers = useMemo(() => {
    const set = new Set<string>();
    (data?.official ?? []).forEach((r) => {
      const m = (index?.models ?? []).find((x) => x.model_id === r.model_id);
      set.add(m?.provider || '未知厂商');
    });
    return Array.from(set).sort();
  }, [data, index]);

  if (loading) return <Skeleton rows={8} />;
  if (error) return <ErrorState error={error} />;
  if (!capMeta) return <EmptyState title="未知能力" />;

  const activeCaps = capabilities.filter((c) => c.status === 'active');
  const isAgentSystem = capId === 'swe' || capId === 'agentic_general' || capId === 'gpu_kernel';

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">能力榜单 · {capMeta.name}</h1>
        <p className="mt-1 text-sm text-slate-400">
          {isAgentSystem
            ? '该成绩来自「模型 + Agent 框架 + 推理档位」的完整系统，不设基础模型综合指数；请按基准与 Scaffold 阅读。'
            : '默认展示来源发布的原始成绩；"本站相对百分位"为次级参考，仅在数据质量门槛全部通过时提供。'}
        </p>
        {capMeta.description && (
          <p className="mt-2 rounded-xl border border-amber-400/25 bg-amber-400/5 px-4 py-2.5 text-xs leading-6 text-amber-200/90">
            口径说明：{capMeta.description}
          </p>
        )}
      </header>

      {/* 能力切换（按能力域分组） */}
      <nav className="space-y-1.5" aria-label="能力分类切换">
        {groups.map((g) => {
          const caps = activeCaps.filter((c) => c.group === g.group_id);
          if (!caps.length) return null;
          return (
            <div key={g.group_id} className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 w-24 shrink-0 text-[11px] text-slate-500">{g.name}</span>
              {caps.map((c) => (
                <button
                  key={c.capability_id}
                  onClick={() => {
                    setParams({ cap: c.capability_id });
                    setBenchmarkId('');
                    setFilters(emptyOfficialFilters);
                    setShowHistory(false);
                  }}
                  className={`rounded-lg px-3 py-1.5 text-sm ${
                    c.capability_id === capId
                      ? 'bg-cyan-400/15 font-medium text-cyan-300'
                      : 'border border-slate-500/25 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {c.short}
                </button>
              ))}
            </div>
          );
        })}
      </nav>

      {!data || data.status === 'pending' || data.official.length === 0 ? (
        <EmptyState
          title="该能力数据接入中"
          hint="暂无满足本站可信标准的结构化数据源。宁可显示「接入中」，也不生成模拟排名。"
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-xl border border-slate-500/25 p-0.5" role="tablist" aria-label="榜单模式">
              <button
                role="tab"
                aria-selected={mode === 'official'}
                className={`rounded-lg px-3.5 py-1.5 text-sm ${mode === 'official' ? 'bg-cyan-400/15 text-cyan-300' : 'text-slate-400'}`}
                onClick={() => setMode('official')}
              >
                来源原始榜
              </button>
              <button
                role="tab"
                aria-selected={mode === 'composite'}
                disabled={!data.composite}
                className={`rounded-lg px-3.5 py-1.5 text-sm disabled:opacity-40 ${mode === 'composite' ? 'bg-violet-400/15 text-violet-300' : 'text-slate-400'}`}
                onClick={() => setMode('composite')}
              >
                本站相对百分位（次级）
              </button>
            </div>
            <span className="badge">
              {data.composite
                ? `相对百分位 · ${data.composite.benchmark_count} 个合格基准 · 0~100 为相对位置而非能力满分`
                : '无相对百分位（门槛未通过，仅提供来源原始榜）'}
            </span>
          </div>

          {mode === 'official' ? (
            <>
              {/* CURRENT / HISTORY 分离 */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex rounded-xl border border-slate-500/25 p-0.5" role="tablist" aria-label="模型代际">
                  <button
                    role="tab"
                    aria-selected={!showHistory}
                    onClick={() => setShowHistory(false)}
                    className={`rounded-lg px-3 py-1.5 text-xs ${!showHistory ? 'bg-emerald-400/15 text-emerald-300' : 'text-slate-400'}`}
                  >
                    CURRENT · 当前模型
                  </button>
                  <button
                    role="tab"
                    aria-selected={showHistory}
                    onClick={() => setShowHistory(true)}
                    className={`rounded-lg px-3 py-1.5 text-xs ${showHistory ? 'bg-slate-500/25 text-slate-200' : 'text-slate-400'}`}
                  >
                    HISTORY · 含历史{legacyRows.length > 0 && `（${legacyRows.length}）`}
                  </button>
                </div>
                <span className="text-[11px] text-slate-500">
                  默认仅展示当前活跃模型；历史结果请手动展开
                </span>
                {(() => {
                  if (currentModelCount > 0 && currentModelCount < 5) {
                    return (
                      <span className="rounded-lg border border-amber-400/25 bg-amber-400/5 px-3 py-1.5 text-[11px] text-amber-200/90">
                        该基准当前仅覆盖 {currentModelCount} 个活跃模型（{currentRows.length} 条当前记录），不拿历史模型补位
                      </span>
                    );
                  }
                  return null;
                })()}
              </div>
              <div className="flex flex-col gap-3">
                <SearchInput value={filters.query} onChange={(v) => setFilters({ ...filters, query: v })} />
                <div className="flex flex-wrap items-center gap-3">
                  <select
                    className="rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-sm text-slate-200"
                    value={benchmarkId}
                    onChange={(e) => setBenchmarkId(e.target.value)}
                    aria-label="切换基准"
                  >
                    <option value="">全部基准（合并显示，需自行核对口径）</option>
                    {data.benchmarks.map((b) => (
                      <option key={b.benchmark_id} value={b.benchmark_id}>
                        {b.benchmark_name}（{b.record_count}）
                      </option>
                    ))}
                  </select>
                  <FilterBar filters={filters} setFilters={setFilters} providers={providers} showAgentToggle={!isAgentSystem} />
                </div>
              </div>
              <OfficialTable rows={rows} onPick={setPicked} showAgentColumn={isAgentSystem} showFreshness />
              {isAgentSystem && (
                <div className="rounded-xl border border-violet-400/25 bg-violet-400/5 px-4 py-3 text-xs leading-6 text-violet-200/90">
                  说明：该分数反映「模型 + Agent 框架 + 推理预算」的完整系统表现，不是基础模型的纯能力。
                  同一模型在不同 Agent 框架下的运行分别成行；跨 Scaffold 比较请先在"切换基准"中选定同一分区，
                  并核对 Agent 框架列是否一致。
                </div>
              )}
            </>
          ) : (
            data.composite && <CompositeTable file={data} index={index} />
          )}
        </>
      )}

      <SourceDrawer row={picked} onClose={() => setPicked(null)} />
    </div>
  );
}

function CompositeTable({ file, index }: { file: CapabilityFile; index: ModelsIndex | null }) {
  const comp = file.composite!;
  const currentIds = new Set((index?.models ?? []).filter((model) => model.is_current === true).map((model) => model.model_id));
  const currentModels = comp.models.filter((model) => currentIds.has(model.model_id));
  return (
    <div>
      <p className="mb-3 rounded-xl border border-violet-400/25 bg-violet-400/5 px-4 py-3 text-xs leading-6 text-violet-200/90">
        {comp.method}：先在每个合格基准内计算相对百分位（0~100，100 = 当前参与计算的模型集合中最高，
        <b>不是能力满分</b>），再按来源等级权重（A=1.0 / B=0.8 / C=0.6）加权平均。
        参与门槛：仅 maintainer_verified 记录；基准映射覆盖率 ≥95% 且已映射模型 ≥10；
        模型须覆盖 ≥2 个合格基准且 ≥60%。缺失数据不计为 0。
        当前默认只展示活跃模型（{currentModels.length}/{comp.models.length}）。
      </p>
      <div className="panel overflow-x-auto">
        <table className="data-table w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-slate-500/15 text-slate-400">
              <th className="px-3 py-2.5 text-left">相对排名</th>
              <th className="px-3 py-2.5 text-left">模型</th>
              <th className="px-3 py-2.5 text-left">本站相对百分位</th>
              <th className="px-3 py-2.5 text-left">基准覆盖</th>
              <th className="px-3 py-2.5 text-left">来源数</th>
              <th className="px-3 py-2.5 text-left">置信度</th>
            </tr>
          </thead>
          <tbody>
            {currentModels.map((m) => (
              <tr key={m.model_id} className="border-b border-slate-500/10 hover:bg-slate-500/5">
                <td className="px-3 py-2.5"><span className="num font-semibold text-slate-200">{m.rank}</span></td>
                <td className="px-3 py-2.5">
                  <a href={`#/model/${m.model_id}`} className="text-slate-100 hover:text-cyan-300">{m.model_id}</a>
                </td>
                <td className="px-3 py-2.5">
                  <span className="num font-semibold text-cyan-300">{m.index.toFixed(1)}</span>
                  {m.tie && <span className="ml-1.5 text-[10px] text-amber-300">并列</span>}
                </td>
                <td className="px-3 py-2.5">
                  <span className="num text-slate-300">
                    {m.benchmark_count}/{m.benchmark_total ?? '—'}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className="num text-slate-300">
                    {m.source_count}
                    {m.single_source && <span className="ml-1 text-[10px] text-amber-300">单一来源</span>}
                  </span>
                </td>
                <td className="px-3 py-2.5">{m.confidence === 'high' ? '高' : m.confidence === 'low' ? '低' : '中'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
