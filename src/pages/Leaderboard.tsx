import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useJson } from '@/lib/api';
import { CAPABILITIES } from '@/lib/capabilities';
import type { CapabilityFile, ModelsIndex, OfficialRow } from '@/types/data';
import { Skeleton, EmptyState, ErrorState } from '@/components/StateViews';
import {
  OfficialTable,
  SearchInput,
  FilterBar,
  applyOfficialFilters,
  emptyOfficialFilters,
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

  const capMeta = CAPABILITIES.find((c) => c.id === capId);
  const { data, error, loading } = useJson<CapabilityFile>(`/data/capabilities/${capId}.json`);
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');

  const rows: JoinedRow[] = useMemo(() => {
    if (!data) return [];
    const official =
      benchmarkId === ''
        ? data.official
        : data.official.filter((r) => r.benchmark_id === benchmarkId);
    return applyOfficialFilters(joinRows(official, index?.models ?? []), filters);
  }, [data, index, filters, benchmarkId]);

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

  const activeCaps = CAPABILITIES.filter((c) => c.active);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">能力榜单 · {capMeta.name}</h1>
        <p className="mt-1 text-sm text-slate-400">
          {capMeta.id === 'swe'
            ? 'SWE-bench 系列成绩来自“模型 + Agent 框架”的完整系统，与基础模型成绩分开呈现。'
            : '每一条官方分数都可点击查看数据溯源；综合指数为本站基于官方原始分的确定性计算。'}
        </p>
      </header>

      {/* 能力切换 */}
      <nav className="flex flex-wrap gap-1.5" aria-label="能力分类切换">
        {activeCaps.map((c) => (
          <button
            key={c.id}
            onClick={() => {
              setParams({ cap: c.id });
              setBenchmarkId('');
              setFilters(emptyOfficialFilters);
            }}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              c.id === capId ? 'bg-cyan-400/15 font-medium text-cyan-300' : 'border border-slate-500/25 text-slate-400 hover:text-slate-200'
            }`}
          >
            {c.short}
          </button>
        ))}
      </nav>

      {!data || data.status === 'pending' || data.official.length === 0 ? (
        <EmptyState
          title="该能力数据接入中"
          hint="暂无满足本站可信标准的结构化数据源。宁可显示“接入中”，也不生成模拟排名。"
        />
      ) : (
        <>
          {/* 模式切换 */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-xl border border-slate-500/25 p-0.5" role="tablist" aria-label="榜单模式">
              <button
                role="tab"
                aria-selected={mode === 'official'}
                className={`rounded-lg px-3.5 py-1.5 text-sm ${mode === 'official' ? 'bg-cyan-400/15 text-cyan-300' : 'text-slate-400'}`}
                onClick={() => setMode('official')}
              >
                官方原始榜
              </button>
              <button
                role="tab"
                aria-selected={mode === 'composite'}
                disabled={!data.composite}
                className={`rounded-lg px-3.5 py-1.5 text-sm disabled:opacity-40 ${mode === 'composite' ? 'bg-violet-400/15 text-violet-300' : 'text-slate-400'}`}
                onClick={() => setMode('composite')}
              >
                综合指数{data.composite?.source_count === 1 ? '（单一来源）' : ''}
              </button>
            </div>
            <span className="badge">
              {data.composite
                ? `${data.composite.benchmark_count} 个基准 · ${data.composite.source_count} 个来源`
                : '暂无综合指数'}
            </span>
          </div>

          {mode === 'official' ? (
            <>
              <div className="flex flex-col gap-3">
                <SearchInput value={filters.query} onChange={(v) => setFilters({ ...filters, query: v })} />
                <div className="flex flex-wrap items-center gap-3">
                  <select
                    className="rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-sm text-slate-200"
                    value={benchmarkId}
                    onChange={(e) => setBenchmarkId(e.target.value)}
                    aria-label="切换基准"
                  >
                    <option value="">全部基准（合并显示）</option>
                    {data.benchmarks.map((b) => (
                      <option key={b.benchmark_id} value={b.benchmark_id}>
                        {b.benchmark_name}（{b.record_count}）
                      </option>
                    ))}
                  </select>
                  <FilterBar filters={filters} setFilters={setFilters} providers={providers} showAgentToggle={capId !== 'swe'} />
                </div>
              </div>
              <OfficialTable rows={rows} onPick={setPicked} />
              {capId === 'swe' && (
                <p className="rounded-xl border border-violet-400/25 bg-violet-400/5 px-4 py-3 text-xs leading-6 text-violet-200/90">
                  说明：SWE-bench 分数反映的是「模型 + Agent 框架 + 推理预算」的完整系统表现，不能直接解读为基础模型的纯能力；
                  同一模型不同 Agent 框架的运行会分别列出。
                </p>
              )}
            </>
          ) : (
            data.composite && <CompositeTable file={data} />
          )}
        </>
      )}

      <SourceDrawer row={picked} onClose={() => setPicked(null)} />
    </div>
  );
}

function CompositeTable({ file }: { file: CapabilityFile }) {
  const comp = file.composite!;
  return (
    <div>
      <p className="mb-3 rounded-xl border border-violet-400/25 bg-violet-400/5 px-4 py-3 text-xs leading-6 text-violet-200/90">
        {comp.method}：先在每个基准内计算百分位（0~100），再按来源等级权重（A=1.0 / B=0.8 / C=0.6）加权平均。
        缺失数据不计为 0 分；置信区间或并列分数会造成并列排名。
      </p>
      <div className="panel overflow-x-auto">
        <table className="data-table w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-slate-500/15 text-slate-400">
              <th className="px-3 py-2.5 text-left">排名</th>
              <th className="px-3 py-2.5 text-left">模型</th>
              <th className="px-3 py-2.5 text-left">指数</th>
              <th className="px-3 py-2.5 text-left">基准覆盖</th>
              <th className="px-3 py-2.5 text-left">来源数</th>
              <th className="px-3 py-2.5 text-left">置信度</th>
            </tr>
          </thead>
          <tbody>
            {comp.models.map((m) => (
              <tr key={m.model_id} className="border-b border-slate-500/10 hover:bg-slate-500/5">
                <td className="px-3 py-2.5"><span className="num font-semibold text-slate-200">{m.rank}</span></td>
                <td className="px-3 py-2.5">
                  <a href={`#/model/${m.model_id}`} className="text-slate-100 hover:text-cyan-300">{m.model_id}</a>
                </td>
                <td className="px-3 py-2.5">
                  <span className="num font-semibold text-cyan-300">{m.index.toFixed(1)}</span>
                  {m.tie && <span className="ml-1.5 text-[10px] text-amber-300">并列</span>}
                </td>
                <td className="px-3 py-2.5"><span className="num text-slate-300">{m.benchmark_count}</span></td>
                <td className="px-3 py-2.5"><span className="num text-slate-300">{m.source_count}{m.single_source && <span className="ml-1 text-[10px] text-amber-300">单一来源</span>}</span></td>
                <td className="px-3 py-2.5">{m.confidence === 'high' ? '高' : m.confidence === 'low' ? '低' : '中'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
