import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { X, Table2, Radar as RadarIcon } from 'lucide-react';
import { useJson, useJsonMany } from '@/lib/api';
import { useCapabilities } from '@/lib/capabilities';
import type { ModelDetail, ModelsIndex } from '@/types/data';
import { providerColor } from '@/types/data';
import { ModelRadar, type RadarSeries } from '@/charts/ModelRadar';
import { TrendLine } from '@/charts/TrendLine';
import { fmtContext, fmtDate, fmtScore } from '@/lib/format';
import { Skeleton, EmptyState } from '@/components/StateViews';

const MAX_COMPARE = 6;

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const selected = (params.get('models') || '').split(',').filter(Boolean).slice(0, MAX_COMPARE);
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');
  const { capabilities, groups } = useCapabilities();

  const [query, setQuery] = useState('');
  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!index) return [];
    return index.models
      .filter((m) => !selected.includes(m.model_id))
      .filter((m) => !q || m.model_id.includes(q) || m.display_name.toLowerCase().includes(q) || (m.provider ?? '').toLowerCase().includes(q))
      .slice(0, 12);
  }, [index, query, selected]);

  const add = (id: string) => {
    if (selected.length >= MAX_COMPARE) return;
    setParams({ models: [...selected, id].join(',') });
    setQuery('');
  };
  const remove = (id: string) => {
    setParams({ models: selected.filter((s) => s !== id).join(',') });
  };

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">模型对比</h1>
        <p className="mt-1 text-sm text-slate-400">
          选择 2~{MAX_COMPARE} 个模型。主视图为能力矩阵热力图（来源原始分），雷达图为可选项。
          对比结果可通过 URL 分享。
        </p>
      </header>

      <div className="panel px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          {selected.map((id) => {
            const m = index?.models.find((x) => x.model_id === id);
            return (
              <span key={id} className="badge border-slate-500/40 text-slate-200">
                <span className="h-2 w-2 rounded-full" style={{ background: providerColor(m?.provider) }} aria-hidden />
                {m?.display_name || id}
                <button onClick={() => remove(id)} aria-label={`移除 ${id}`} className="ml-0.5 text-slate-500 hover:text-rose-300">
                  <X size={12} />
                </button>
              </span>
            );
          })}
          {selected.length === 0 && <span className="text-sm text-slate-500">尚未选择模型</span>}
          {selected.length >= MAX_COMPARE && <span className="text-xs text-amber-300">已达 {MAX_COMPARE} 个上限</span>}
        </div>
        <div className="relative mt-3 max-w-md">
          <input
            className="w-full rounded-lg border border-slate-500/25 bg-slate-900/60 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索模型后点击添加…"
            aria-label="搜索要对比的模型"
          />
          {query && candidates.length > 0 && (
            <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-xl border border-slate-500/30 bg-[#0b111f] p-1 shadow-xl">
              {candidates.map((m) => (
                <li key={m.model_id}>
                  <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-500/10" onClick={() => add(m.model_id)}>
                    <span className="h-2 w-2 rounded-full" style={{ background: providerColor(m.provider) }} aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{m.display_name}</span>
                    <span className="text-xs text-slate-500">{m.provider ?? '未知厂商'}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {selected.length === 0 ? (
        <EmptyState title="先选择至少 2 个模型" hint="例如：gpt-5.2-2025-12-11-high、glm-5.3、kimi-k3…" />
      ) : (
        <ComparePanels ids={selected} capabilities={capabilities} groups={groups} />
      )}
    </div>
  );
}

interface Group {
  group_id: string;
  name: string;
}

function ComparePanels({
  ids,
  capabilities,
  groups,
}: {
  ids: string[];
  capabilities: ReturnType<typeof useCapabilities>['capabilities'];
  groups: Group[];
}) {
  const [view, setView] = useState<'matrix' | 'radar'>('matrix');
  const urls = ids.map((id) => `/data/models/${id}.json`);
  const { data: detailsMap, loading } = useJsonMany<ModelDetail>(urls);
  if (loading) return <Skeleton rows={8} />;

  const loaded = urls.map((u) => detailsMap.get(u)).filter(Boolean) as ModelDetail[];
  if (loaded.length === 0) return <EmptyState title="未找到所选模型的数据" />;

  return (
    <div className="space-y-6">
      <div className="flex rounded-xl border border-slate-500/25 p-0.5" role="tablist" aria-label="对比视图">
        <button
          role="tab"
          aria-selected={view === 'matrix'}
          onClick={() => setView('matrix')}
          className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm ${view === 'matrix' ? 'bg-cyan-400/15 text-cyan-300' : 'text-slate-400'}`}
        >
          <Table2 size={14} aria-hidden /> 能力矩阵（主视图）
        </button>
        <button
          role="tab"
          aria-selected={view === 'radar'}
          onClick={() => setView('radar')}
          className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-sm ${view === 'radar' ? 'bg-cyan-400/15 text-cyan-300' : 'text-slate-400'}`}
        >
          <RadarIcon size={14} aria-hidden /> 雷达图（可选）
        </button>
      </div>

      {view === 'matrix' ? (
        <MatrixView details={loaded} capabilities={capabilities} groups={groups} />
      ) : (
        <RadarView details={loaded} capabilities={capabilities} />
      )}

      <section className="panel overflow-x-auto px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">基础信息与价格</h2>
        <table className="data-table mt-3 w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-slate-500/15 text-slate-400">
              <th className="px-3 py-2 text-left">项目</th>
              {loaded.map((d) => (
                <th key={d.meta.model_id} className="px-3 py-2 text-left font-medium" style={{ color: providerColor(d.meta.provider) }}>
                  {d.meta.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-slate-300">
            <Row label="厂商" cells={loaded.map((d) => d.meta.provider ?? '未知厂商')} />
            <Row label="发布日期" cells={loaded.map((d) => fmtDate(d.meta.release_date))} />
            <Row label="上下文窗口" cells={loaded.map((d) => fmtContext(d.meta.context_window))} />
            <Row label="开放权重" cells={loaded.map((d) => (d.meta.open_weights === null ? '—' : d.meta.open_weights ? '是' : '否'))} />
            <Row label="输入价格 /1M tok" cells={loaded.map((d) => fmtScore(d.meta.price_input_usd_per_mtok, 'usd_per_mtok'))} />
            <Row label="输出价格 /1M tok" cells={loaded.map((d) => fmtScore(d.meta.price_output_usd_per_mtok, 'usd_per_mtok'))} />
            <Row label="输出速度" cells={loaded.map((d) => fmtScore(d.meta.output_speed_tps, 'tokens_per_second'))} />
            <Row label="模态" cells={loaded.map((d) => d.meta.modalities.join(' / '))} />
            <Row label="数据来源数" cells={loaded.map((d) => String(d.meta.source_count))} />
          </tbody>
        </table>
      </section>

      <AdvantagePanel details={loaded} capabilities={capabilities} />
      <HistoryPanel details={loaded} capabilities={capabilities} />
    </div>
  );
}

/** 主视图：能力 × 模型热力矩阵（来源原始分），按能力域分组，缺失显示 —。 */
function MatrixView({
  details,
  capabilities,
  groups,
}: {
  details: ModelDetail[];
  capabilities: ReturnType<typeof useCapabilities>['capabilities'];
  groups: Group[];
}) {
  // 每个模型按真实运行日优先、榜单快照兜底选择最新证据。
  const cellOf = (d: ModelDetail, capId: string) => {
    const rows = d.records.filter((r) => r.capability === capId);
    if (!rows.length) return null;
    rows.sort((a, b) => (
      b.evaluation_date || b.upstream_updated_at || ''
    ).localeCompare(a.evaluation_date || a.upstream_updated_at || ''));
    const r = rows[0];
    return {
      score: r.score,
      unit: r.score_unit,
      date: r.evaluation_date || r.upstream_updated_at,
      bench: r.benchmark_name,
      type: r.evaluation_target_type,
    };
  };
  const activeCaps = capabilities.filter((c) => c.status === 'active');
  const cellColor = (v: number, min: number, max: number) => {
    if (max === min) return 'rgba(34,211,238,0.12)';
    const t = (v - min) / (max - min);
    return `rgba(34,211,238,${0.06 + t * 0.26})`;
  };

  return (
    <section className="space-y-4">
      <p className="text-xs text-slate-500">
        单元格为<b>来源原始分</b>（非本站百分位），同行内颜色深浅表示相对高低；— 表示该模型无此能力数据（不按 0 分处理）。
        悬停可查看基准与最新证据日期。软件工程与终端 Agent 行为「模型 + Agent 系统」成绩。
      </p>
      {groups.map((g) => {
        const caps = activeCaps.filter((c) => c.group === g.group_id);
        const capsWithData = caps.filter((c) => details.some((d) => cellOf(d, c.capability_id)));
        if (!capsWithData.length) return null;
        return (
          <div key={g.group_id} className="panel overflow-x-auto px-4 py-4">
            <h3 className="mb-2 text-sm font-bold text-slate-100">{g.name}</h3>
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="text-slate-400">
                  <th className="px-3 py-2 text-left font-medium">能力</th>
                  {details.map((d) => (
                    <th key={d.meta.model_id} className="px-3 py-2 text-left font-medium" style={{ color: providerColor(d.meta.provider) }}>
                      {d.meta.display_name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {capsWithData.map((c) => {
                  const vals = details.map((d) => cellOf(d, c.capability_id)).filter(Boolean) as NonNullable<ReturnType<typeof cellOf>>[];
                  const numeric = vals.filter((v) => ['percent', 'index_0_100'].includes(v.unit) || !v.unit.startsWith('absolute'));
                  const min = Math.min(...numeric.map((v) => v.score));
                  const max = Math.max(...numeric.map((v) => v.score));
                  return (
                    <tr key={c.capability_id} className="border-t border-slate-500/10">
                      <td className="px-3 py-2 text-slate-300">{c.name}</td>
                      {details.map((d) => {
                        const v = cellOf(d, c.capability_id);
                        if (!v) {
                          return (
                            <td key={d.meta.model_id} className="px-3 py-2 text-slate-600" title="无数据（不计为 0）">
                              —
                            </td>
                          );
                        }
                        return (
                          <td
                            key={d.meta.model_id}
                            className="px-3 py-2"
                            style={{ background: cellColor(v.score, min, max) }}
                            title={`${v.bench} · ${fmtDate(v.date)}${v.type === 'model_plus_agent' ? ' · 模型+Agent 系统' : ''}`}
                          >
                            <span className="num">{fmtScore(v.score, v.unit)}</span>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}
    </section>
  );
}

/** 可选视图：雷达图，用户勾选 ≤8 个维度，缺失断开不按 0 分。 */
function RadarView({ details, capabilities }: { details: ModelDetail[]; capabilities: ReturnType<typeof useCapabilities>['capabilities'] }) {
  const capSet = new Set<string>();
  details.forEach((d) => d.radar.forEach((r) => capSet.add(r.capability_id)));
  const available = capabilities.filter((c) => capSet.has(c.capability_id));
  const [picked, setPicked] = useState<string[]>(available.slice(0, 6).map((c) => c.capability_id));

  const toggle = (id: string) => {
    setPicked((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length >= 8 ? prev : [...prev, id],
    );
  };
  const indicators = picked.map((id) => ({
    name: capabilities.find((c) => c.capability_id === id)?.short ?? id,
    max: 100,
  }));
  const series: RadarSeries[] = details.map((d) => ({
    name: d.meta.display_name,
    color: providerColor(d.meta.provider),
    values: picked.map((id) => d.radar.find((r) => r.capability_id === id)?.index ?? null),
  }));

  return (
    <section className="panel px-5 py-6">
      <h2 className="text-lg font-bold text-slate-100">雷达图（可选视图）</h2>
      <p className="mt-1 text-xs text-slate-500">
        勾选最多 8 个维度（仅限有通过门槛数据的能力）；缺失维度断开显示，不按 0 分。
        数值为本站相对百分位（相对位置，非能力满分）。
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {available.map((c) => (
          <button
            key={c.capability_id}
            onClick={() => toggle(c.capability_id)}
            className={`rounded-lg px-2.5 py-1 text-xs ${
              picked.includes(c.capability_id)
                ? 'bg-cyan-400/15 text-cyan-300'
                : 'border border-slate-500/25 text-slate-500 hover:text-slate-300'
            } ${!picked.includes(c.capability_id) && picked.length >= 8 ? 'opacity-40' : ''}`}
            disabled={!picked.includes(c.capability_id) && picked.length >= 8}
          >
            {c.short}
          </button>
        ))}
      </div>
      {picked.length >= 2 ? (
        <div className="mt-3">
          <ModelRadar indicators={indicators} series={series} height={400} />
        </div>
      ) : (
        <p className="py-8 text-center text-sm text-slate-500">请至少勾选 2 个维度</p>
      )}
    </section>
  );
}

function Row({ label, cells }: { label: string; cells: string[] }) {
  return (
    <tr className="border-b border-slate-500/10">
      <td className="px-3 py-2 text-slate-400">{label}</td>
      {cells.map((c, i) => (
        <td key={i} className="num px-3 py-2">{c}</td>
      ))}
    </tr>
  );
}

/** 优势与短板：确定性规则生成（不使用任何 LLM）。 */
function AdvantagePanel({ details, capabilities }: { details: ModelDetail[]; capabilities: ReturnType<typeof useCapabilities>['capabilities'] }) {
  const entries = details.map((d) => ({
    d,
    values: d.radar.map((r) => r.index).filter((v): v is number => v !== null),
  }));
  const allValues = entries.flatMap((e) => e.values);
  const median = allValues.length ? [...allValues].sort((a, b) => a - b)[Math.floor(allValues.length / 2)] : 0;

  return (
    <section className="panel px-5 py-6">
      <h2 className="text-lg font-bold text-slate-100">优势与短板</h2>
      <p className="mt-1 text-xs text-slate-500">
        由确定性规则生成：某能力进入前 10% 记为优势，低于对比组中位数记为短板，价格位于最低 25% 记为性价比优势。不使用任何大模型生成评价。
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {entries.map(({ d }) => {
          const strengths: string[] = [];
          const weaknesses: string[] = [];
          for (const r of d.radar) {
            if (r.index === null) continue;
            const rankPct = r.rank && d.radar.length ? r.rank / d.radar.length : 1;
            const nm = capabilities.find((c) => c.capability_id === r.capability_id)?.short ?? r.name;
            if (rankPct <= 0.1) strengths.push(`${nm}（相对百分位 ${r.index.toFixed(1)}，前 10%）`);
            else if (r.index < median) weaknesses.push(`${nm}（相对百分位 ${r.index.toFixed(1)}，低于中位数 ${median.toFixed(1)}）`);
          }
          const prices = details.map((x) => x.meta.price_input_usd_per_mtok).filter((p): p is number => p !== null && p > 0);
          if (prices.length >= 2 && d.meta.price_input_usd_per_mtok !== null && d.meta.price_input_usd_per_mtok > 0) {
            const sorted = [...prices].sort((a, b) => a - b);
            const q1 = sorted[Math.floor(sorted.length * 0.25)];
            if (d.meta.price_input_usd_per_mtok <= q1) strengths.push(`输入价格位于最低 25%（$${d.meta.price_input_usd_per_mtok}/1M）`);
          }
          return (
            <div key={d.meta.model_id} className="panel-2 px-4 py-4">
              <p className="font-semibold" style={{ color: providerColor(d.meta.provider) }}>{d.meta.display_name}</p>
              <p className="mt-2 text-xs font-medium text-emerald-300">优势</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-slate-300">
                {strengths.length ? strengths.map((s) => <li key={s}>{s}</li>) : <li className="list-none text-slate-500">对比范围内无明显优势项</li>}
              </ul>
              <p className="mt-3 text-xs font-medium text-rose-300">短板</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-slate-300">
                {weaknesses.length ? weaknesses.map((s) => <li key={s}>{s}</li>) : <li className="list-none text-slate-500">对比范围内无明显短板</li>}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function HistoryPanel({ details, capabilities }: { details: ModelDetail[]; capabilities: ReturnType<typeof useCapabilities>['capabilities'] }) {
  const capSet = new Set<string>();
  details.forEach((d) => Object.keys(d.history).forEach((c) => capSet.add(c)));
  const caps = Array.from(capSet).slice(0, 4);
  if (caps.length === 0) {
    return (
      <section className="panel px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">排名历史</h2>
        <p className="mt-2 text-sm text-slate-500">历史快照积累中（每日更新一次，约 7 天后可查看趋势）。</p>
      </section>
    );
  }
  return (
    <section className="panel px-5 py-6">
      <h2 className="text-lg font-bold text-slate-100">排名历史</h2>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {caps.map((cap) => (
          <div key={cap} className="panel-2 px-3 py-3">
            <p className="text-xs text-slate-400">
              {capabilities.find((c) => c.capability_id === cap)?.name ?? cap} · 相对百分位
            </p>
            <TrendLine
              series={details
                .filter((d) => d.history[cap]?.length)
                .map((d) => ({
                  name: d.meta.display_name,
                  color: providerColor(d.meta.provider),
                  points: d.history[cap].map((p) => ({ date: p.date, value: p.index })),
                }))}
              height={220}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
