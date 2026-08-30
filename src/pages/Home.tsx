import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Sparkles } from 'lucide-react';
import { useJson, useMeta } from '@/lib/api';
import { useCapabilities, capShort } from '@/lib/capabilities';
import { fmtDate, fmtScore } from '@/lib/format';
import { providerColor } from '@/types/data';
import type { CapabilityFile, Homepage, Meta, ModelsIndex } from '@/types/data';
import { EmptyState, NoDataState } from '@/components/StateViews';
import { PricePerformanceMatrix } from '@/components/PricePerformanceMatrix';
import { filterCurrent, joinRows, type JoinedRow } from '@/components/OfficialTable';

interface HeatmapData {
  generated_at: string;
  capabilities: {
    capability_id: string;
    benchmark_id: string;
    higher_is_better: boolean;
    score_unit: string;
    cells: {
      model_id: string;
      display_name: string;
      provider: string | null;
      score: number;
      rank: number;
      tie: boolean;
      agent_scaffold: string | null;
      evaluation_date: string | null;
    }[];
  }[];
  models: string[];
}

type TabId = 'reasoning' | 'coding' | 'agent' | 'multimodal' | 'chinese_mm' | 'value';

const TABS: { id: TabId; label: string; note: string }[] = [
  { id: 'reasoning', label: '文本推理', note: 'LiveBench 官方推理类别平均（原始分）' },
  { id: 'coding', label: '编程', note: 'LiveBench 编程官方综合（相对百分位，已通过映射门槛）' },
  { id: 'agent', label: 'Agent 软件工程', note: 'SWE-bench Verified 官方榜 · 模型 + Agent 框架系统成绩' },
  { id: 'multimodal', label: '多模态', note: 'MMBench v1.1 英文（官方 Overall，原始分）' },
  { id: 'chinese_mm', label: '中文多模态', note: 'MMBench v1.1 中文（官方 Overall，原始分）· 不代表综合中文能力' },
  { id: 'value', label: '性价比', note: '编程官方相对位置 ÷ 输入价格（客户端计算，公开公式）' },
];

export function HomePage() {
  const { meta: rawMeta, error } = useMeta();
  const { data: home } = useJson<Homepage>('/data/homepage.json');
  const { data: index } = useJson<ModelsIndex>('/data/models/index.json');
  const { data: heatmap } = useJson<HeatmapData>('/data/heatmap.json');
  const { capabilities } = useCapabilities();
  const [tab, setTab] = useState<TabId>('reasoning');
  const [releaseWindow, setReleaseWindow] = useState<'7d' | '30d' | '90d'>('30d');

  if (error && !rawMeta) {
    return <NoDataState detail={`meta.json 加载失败：${error}`} />;
  }
  const meta = rawMeta;

  const activeTab = TABS.find((t) => t.id === tab)!;
  const officialCap = tab === 'agent' ? 'swe' : tab;
  const releases = home?.latest_releases?.[releaseWindow] ?? [];

  return (
    <div className="space-y-8">
      {/* 紧凑头部 */}
      <section className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-500/15 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-slate-50 sm:text-3xl">
            全球 AI 模型能力
            <span className="bg-gradient-to-r from-cyan-300 to-violet-400 bg-clip-text text-transparent">对照榜</span>
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-400">
            官方原始分为主，本站计算一律标注为相对百分位。每条分数可点开溯源。
            首页默认只显示当前活跃模型。
          </p>
        </div>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <InlineStat
            label="当前模型"
            value={index?.models.filter((m) => m.is_current === true && (m.overall_index !== null || m.source_count)).length}
          />
          <InlineStat label="基准" value={meta?.counts.benchmarks} />
          <InlineStat label="数据源" value={meta?.counts.sources_active} />
          <InlineStat label="数据更新" value={fmtDate(meta?.update.last_success)} />
        </dl>
      </section>

      <DataFreshnessSummary meta={rawMeta} index={index} />

      {/* Current Picks：由当天数据动态计算，不硬编码 */}
      <CurrentPicks home={home} index={index} />

      {/* Latest Releases */}
      <section className="panel px-5 py-6">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="flex items-center gap-2 text-lg font-bold text-slate-100">
            <Sparkles size={17} className="text-amber-300" aria-hidden /> 最新发布
          </h2>
          <span className="badge">来源：models.dev 模型目录</span>
          <div className="ml-auto flex rounded-lg border border-slate-500/25 p-0.5" role="tablist" aria-label="发布时间窗口">
            {(['7d', '30d', '90d'] as const).map((w) => (
              <button
                key={w}
                role="tab"
                aria-selected={releaseWindow === w}
                onClick={() => setReleaseWindow(w)}
                className={`rounded-md px-2.5 py-1 text-xs ${releaseWindow === w ? 'bg-amber-400/15 text-amber-300' : 'text-slate-400'}`}
              >
                {{ '7d': '7 天', '30d': '30 天', '90d': '90 天' }[w]}
              </button>
            ))}
          </div>
        </div>
        {releases.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">该窗口内暂无目录收录的新发布。</p>
        ) : (
          <ul className="mt-4 grid gap-2.5 md:grid-cols-2">
            {releases.slice(0, 10).map((r: Homepage['latest_releases']['30d'][number]) => (
              <li key={`${r.provider_id}-${r.model_id}`} className="panel-2 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="num text-xs text-slate-500">{fmtDate(r.release_date || r.last_updated)}</span>
                  <span className="font-semibold text-slate-100">{r.name}</span>
                  <span className="text-xs text-slate-500">{r.provider_id}</span>
                  {r.reasoning && <span className="badge border-violet-400/30 text-violet-300">推理</span>}
                  {r.tool_call && <span className="badge border-cyan-400/30 text-cyan-300">工具调用</span>}
                  {r.open_weights && <span className="badge border-emerald-400/30 text-emerald-300">开放权重</span>}
                  <span className="ml-auto flex items-center gap-2 text-xs text-slate-400">
                    {r.context_window ? <span className="num">{fmtContextK(r.context_window)}</span> : null}
                    {r.input_price !== null && r.input_price !== undefined && (
                      <span className="num">${r.input_price >= 1 ? r.input_price.toFixed(2) : r.input_price.toFixed(3)}/1M</span>
                    )}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 第一屏：核心榜（官方原始分为主，默认仅当前模型） */}
      <section>
        <nav className="flex flex-wrap gap-1.5" aria-label="核心榜切换">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-pressed={tab === t.id}
              className={`rounded-lg px-3.5 py-1.5 text-sm ${
                tab === t.id ? 'bg-cyan-400/15 font-medium text-cyan-300' : 'border border-slate-500/25 text-slate-400 hover:text-slate-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <p className="mt-2 text-xs text-slate-500">{activeTab.note}</p>
        <div className="mt-3">
          {tab === 'value' ? (
            <ValueBoard index={index} />
          ) : (
            <OfficialBoard capId={officialCap} highlightAgent={tab === 'agent'} index={index} />
          )}
        </div>
      </section>

      {/* 第二屏：能力 × 模型热力图（当前模型） */}
      {heatmap && heatmap.capabilities.length > 0 && (
        <section className="panel px-5 py-6">
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="text-lg font-bold text-slate-100">能力 × 模型热力图</h2>
            <span className="badge">官方原始分 · 仅当前模型 · 每行取主基准 Top 12</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            颜色深浅为同一能力内的相对高低；— 表示无数据（不计为 0）。
            已从默认视图移除 legacy 模型（完整历史见模型详情页）。
          </p>
          <HeatmapGrid data={heatmap} capabilities={capabilities} />
        </section>
      )}

      {/* 第三屏：价格-编程散点 */}
      <PricePerformanceMatrix index={index} />

      {/* 最近上升 & 接入中 */}
      {home && home.movers_7d.length > 0 && (
        <section className="panel px-5 py-5">
          <h2 className="text-sm font-bold text-slate-100">最近 7 天相对排名上升</h2>
          <ul className="mt-3 space-y-2">
            {home.movers_7d.slice(0, 6).map((m, i) => (
              <li key={`${m.model_id}-${m.capability}`} className="flex items-center gap-3 text-sm">
                <span className="num w-5 text-slate-500">{i + 1}</span>
                <Link to={`/model/${m.model_id}`} className="min-w-0 flex-1 truncate text-slate-200 hover:text-cyan-300">
                  {m.display_name}
                </Link>
                <span className="badge">{capShort(capabilities, m.capability)}</span>
                <span className="num flex items-center gap-1 text-emerald-300">
                  <ArrowUpRight size={13} aria-hidden /> {m.delta}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>数据接入中的能力：</span>
        {capabilities.filter((c) => c.status === 'pending').slice(0, 8).map((c) => (
          <span key={c.capability_id} className="badge opacity-70">{c.short} · 接入中</span>
        ))}
        <Link to="/models" className="ml-auto text-cyan-400 hover:text-cyan-300">全部模型目录 →</Link>
        <Link to="/methodology" className="text-cyan-400 hover:text-cyan-300">排名是怎么算的 →</Link>
      </section>
    </div>
  );
}

/** Current Picks：由当天数据动态计算的快速入口（不硬编码获胜者）。 */
function CurrentPicks({ home, index }: { home: Homepage | null; index: ModelsIndex | null }) {
  const picks = useMemo(() => {
    if (!home) return [];
    const out: { label: string; pick: { display_name: string; model_id: string; provider: string | null }; note: string }[] = [];
    for (const [cap, blockRaw] of Object.entries(home.top3)) {
      const block = blockRaw as { rows?: { display_name: string; model_id: string; provider: string | null; score?: number; index?: number; kind: string; agent_scaffold?: string | null }[] };
      const first = block.rows?.[0];
      if (!first) continue;
      const label = { reasoning: '推理最强', coding: '编程最强', math: '数学最强', chinese_mm: '中文多模态最强', multimodal: '多模态最强', swe: 'Agent 软件工程（Verified）' }[cap];
      if (!label) continue;
      const agent = first.agent_scaffold ? `（${first.agent_scaffold}）` : '';
      out.push({
        label,
        pick: { display_name: first.display_name, model_id: first.model_id, provider: first.provider },
        note: first.kind === 'official' ? `官方原始分 ${fmtScore(first.score)}` : `相对百分位 ${fmtScore(first.index)}${agent}`,
      });
    }
    // 最低价（当前 + 有价格数据）
    if (index) {
      const currentModels = index.models.filter((m) => m.is_current === true);
      const priced = currentModels
        .filter((m) => (m.overall_index !== null || m.benchmark_count > 0) && m.price_input_usd_per_mtok !== null && m.price_input_usd_per_mtok > 0)
        .sort((a, b) => (a.price_input_usd_per_mtok ?? 9e9) - (b.price_input_usd_per_mtok ?? 9e9));
      if (priced[0]) {
        out.push({
          label: '最低输入价',
          pick: { display_name: priced[0].display_name, model_id: priced[0].model_id, provider: priced[0].provider },
          note: `$${priced[0].price_input_usd_per_mtok?.toFixed(3)}/1M tokens`,
        });
      }
      const openWeights = currentModels
        .filter((m) => m.open_weights === true && (m.capability_indices.coding !== undefined || m.capability_indices.reasoning !== undefined))
        .sort((a, b) => {
          const av = Math.max(a.capability_indices.coding ?? 0, a.capability_indices.reasoning ?? 0);
          const bv = Math.max(b.capability_indices.coding ?? 0, b.capability_indices.reasoning ?? 0);
          return bv - av;
        });
      if (openWeights[0]) {
        out.push({
          label: '最佳开放权重',
          pick: { display_name: openWeights[0].display_name, model_id: openWeights[0].model_id, provider: openWeights[0].provider },
          note: '当前模型中开放权重相对百分位最高',
        });
      }
      const longest = currentModels
        .filter((m) => m.context_window)
        .sort((a, b) => (b.context_window ?? 0) - (a.context_window ?? 0));
      if (longest[0]) {
        out.push({
          label: '最长上下文',
          pick: { display_name: longest[0].display_name, model_id: longest[0].model_id, provider: longest[0].provider },
          note: `${((longest[0].context_window ?? 0) / 1000).toFixed(0)}K tokens`,
        });
      }
    }
    return out;
  }, [home, index]);

  if (!picks.length) return null;
  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-bold tracking-wide text-slate-300">
        <Sparkles size={15} className="text-amber-300" aria-hidden /> 当前答案 · 由最新数据自动生成
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {picks.slice(0, 8).map((p) => (
          <Link key={p.label} to={`/model/${p.pick.model_id}`} className="panel block px-4 py-3.5 transition-colors hover:border-cyan-400/40">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">{p.label}</p>
            <p className="mt-1.5 truncate text-sm font-bold" style={{ color: providerColor(p.pick.provider) }}>
              {p.pick.display_name}
            </p>
            <p className="num mt-1 text-xs text-slate-400">{p.note}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

/** 官方原始榜 Top 10（默认仅当前模型；不足时明确说明而不是拿旧模型凑数）。 */
function OfficialBoard({ capId, highlightAgent, index }: { capId: string; highlightAgent?: boolean; index: ModelsIndex | null }) {
  const { data, loading } = useJson<CapabilityFile>(`/data/capabilities/${capId}.json`);
  const [showHistory, setShowHistory] = useState(false);
  if (loading) return <div className="skeleton h-72 w-full" />;
  if (!data || data.official.length === 0) {
    return <EmptyState title="该能力暂无数据" hint="数据接入中，不生成模拟排名。" />;
  }
  const counts = new Map<string, number>();
  data.official.forEach((r) => counts.set(r.benchmark_id, (counts.get(r.benchmark_id) ?? 0) + 1));
  const topBench = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0][0];
  const all = joinRows(
    data.official.filter((r) => r.benchmark_id === topBench),
    index?.models ?? [],
  );
  const { current: fresh, legacy } = filterCurrent(all);
  const rows = (showHistory ? all : fresh).slice(0, 10);
  const benchName = data.benchmarks.find((b) => b.benchmark_id === topBench)?.benchmark_name ?? topBench;

  return (
    <div>
      {fresh.length < 5 && (
        <p className="mb-2 rounded-xl border border-amber-400/25 bg-amber-400/5 px-4 py-2.5 text-xs text-amber-200/90">
          该基准当前仅覆盖 {fresh.length} 个活跃模型（共 {all.length} 条官方记录）。为诚实起见，不再拿历史模型补位；
          可打开下方"包含历史模型"查看完整记录。
        </p>
      )}
      <div className="panel overflow-x-auto">
        <table className="data-table w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-slate-500/15 text-slate-400">
              <th className="px-3 py-2.5 text-left">#</th>
              <th className="px-3 py-2.5 text-left">模型</th>
              <th className="px-3 py-2.5 text-left">厂商</th>
              {highlightAgent && <th className="px-3 py-2.5 text-left">Agent 框架</th>}
              <th className="px-3 py-2.5 text-left">官方原始分</th>
              <th className="px-3 py-2.5 text-left">发布日期</th>
              <th className="px-3 py-2.5 text-left">评测日期</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <BoardRow key={`${r.benchmark_id}-${r.model_id}-${r.agent_scaffold ?? ''}-${r.rank}`} r={r} highlightAgent={highlightAgent} />
            ))}
          </tbody>
        </table>
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-[11px] text-slate-500">
          <span>基准：{benchName} · 每条分数可点击查看溯源</span>
          {legacy.length > 0 && (
            <button className="text-cyan-400 hover:text-cyan-300" onClick={() => setShowHistory((v) => !v)}>
              {showHistory ? '仅看当前模型' : `包含历史模型（${legacy.length} 条）`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function BoardRow({ r, highlightAgent }: { r: JoinedRow; highlightAgent?: boolean }) {
  const isAgent = r.evaluation_target_type === 'model_plus_agent' || r.evaluation_target_type === 'complete_agent_system';
  return (
    <tr className={`border-b border-slate-500/10 ${r.is_current === false ? 'opacity-50' : ''} hover:bg-slate-500/5`}>
      <td className="px-3 py-2.5">
        <span className={`num font-semibold ${r.rank === 1 ? 'rank-medal-1' : r.rank === 2 ? 'rank-medal-2' : r.rank === 3 ? 'rank-medal-3' : 'text-slate-400'}`}>
          {r.rank}{r.tie && <span className="ml-1 text-[10px] font-normal text-amber-300">并列</span>}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: providerColor(r.provider) }} aria-hidden />
          <span className="truncate font-medium text-slate-100" title={r.raw_model_name || r.model_id}>
            {r.raw_model_name || r.model_id}
          </span>
          {r.is_current === false && <span className="badge border-slate-500/40 text-slate-500">历史</span>}
          {isAgent && highlightAgent && (
            <span className="badge border-violet-400/40 bg-violet-400/10 text-violet-200">模型+Agent</span>
          )}
        </div>
      </td>
      <td className="px-3 py-2.5 text-slate-400">{r.provider ?? '—'}</td>
      {highlightAgent && <td className="px-3 py-2.5 text-xs text-slate-400">{r.agent_scaffold ?? '—'}</td>}
      <td className="px-3 py-2.5">
        <span className="num font-semibold text-cyan-300">{fmtScore(r.score, r.score_unit)}</span>
      </td>
      <td className="px-3 py-2.5"><span className="num text-slate-400">{fmtDate(r.release_date)}</span></td>
      <td className="px-3 py-2.5"><span className="num text-slate-400">{fmtDate(r.evaluation_date)}</span></td>
    </tr>
  );
}

/** 性价比榜：编程官方相对位置 ÷ 输入价格（客户端计算，公式公开）。 */
function ValueBoard({ index }: { index: ModelsIndex | null }) {
  const { data: coding } = useJson<CapabilityFile>('/data/capabilities/coding.json');
  const rows = useMemo(() => {
    if (!index || !coding || !coding.composite) return null;
    const currentIds = new Set(index.models.filter((m) => m.is_current === true).map((m) => m.model_id));
    const priceOf = new Map(index.models.map((m) => [m.model_id, m.price_input_usd_per_mtok]));
    const out = coding.composite.models
      .filter((m) => currentIds.has(m.model_id))
      .map((m) => ({ m, price: priceOf.get(m.model_id) }))
      .filter((x): x is { m: typeof x.m; price: number } => x.price !== null && x.price !== undefined && x.price > 0)
      .map((x) => ({ ...x, value: x.m.index / x.price }))
      .sort((a, b) => b.value - a.value);
    return out.slice(0, 10);
  }, [index, coding]);

  if (rows === null) return <div className="skeleton h-72 w-full" />;
  if (!rows.length) {
    return <EmptyState title="暂无满足条件的模型" hint="性价比需要模型同时有编程相对百分位与公开价格。" />;
  }
  return (
    <div className="panel overflow-x-auto">
      <table className="data-table w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-slate-500/15 text-slate-400">
            <th className="px-3 py-2.5 text-left">#</th>
            <th className="px-3 py-2.5 text-left">模型</th>
            <th className="px-3 py-2.5 text-left">编程相对百分位</th>
            <th className="px-3 py-2.5 text-left">输入价 /1M</th>
            <th className="px-3 py-2.5 text-left">性价比（百分位 ÷ 价格）</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.m.model_id} className="border-b border-slate-500/10">
              <td className="px-3 py-2.5"><span className={`num font-semibold ${i === 0 ? 'rank-medal-1' : i === 1 ? 'rank-medal-2' : i === 2 ? 'rank-medal-3' : 'text-slate-400'}`}>{i + 1}</span></td>
              <td className="px-3 py-2.5">
                <a href={`#/model/${r.m.model_id}`} className="text-slate-100 hover:text-cyan-300">{r.m.model_id}</a>
              </td>
              <td className="px-3 py-2.5"><span className="num text-slate-300">{r.m.index.toFixed(1)}</span></td>
              <td className="px-3 py-2.5"><span className="num text-slate-300">${r.price.toFixed(2)}</span></td>
              <td className="px-3 py-2.5"><span className="num font-semibold text-cyan-300">{r.value.toFixed(1)}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-4 py-2.5 text-[11px] text-slate-500">
        价格来自 LiveBench 官方统计；百分位来自通过映射门槛的编程综合。公式公开、客户端计算。
      </p>
    </div>
  );
}

/** 热力图：行 = 能力（各自主基准），列 = 出现过的模型。 */
function HeatmapGrid({ data, capabilities }: { data: HeatmapData; capabilities: ReturnType<typeof useCapabilities>['capabilities'] }) {
  const columns: { model_id: string; display_name: string }[] = [];
  for (const cap of data.capabilities) {
    for (const cell of cap.cells) {
      if (!columns.some((c) => c.model_id === cell.model_id)) {
        columns.push({ model_id: cell.model_id, display_name: cell.display_name });
      }
    }
  }
  const cols = columns.slice(0, 14);
  const cellOf = (capId: string, mid: string) => {
    const cap = data.capabilities.find((c) => c.capability_id === capId);
    return cap?.cells.find((c) => c.model_id === mid) ?? null;
  };

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr>
            <th className="px-2 py-2 text-left font-medium text-slate-400">能力（基准）</th>
            {cols.map((c) => (
              <th key={c.model_id} className="px-1 py-2 text-center align-bottom">
                <span className="inline-block max-w-[64px] truncate align-bottom text-[10px] font-normal text-slate-400" title={c.display_name}>
                  {c.display_name}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.capabilities.map((cap) => {
            const scores = cap.cells.map((c) => c.score);
            const min = Math.min(...scores);
            const max = Math.max(...scores);
            return (
              <tr key={cap.capability_id}>
                <td className="whitespace-nowrap px-2 py-1.5 text-slate-300">
                  {capShort(capabilities, cap.capability_id)}
                  <span className="ml-1 text-[10px] text-slate-600">{cap.benchmark_id}</span>
                </td>
                {cols.map((c) => {
                  const cell = cellOf(cap.capability_id, c.model_id);
                  if (!cell) {
                    return <td key={c.model_id} className="px-1 py-1.5 text-center text-slate-700">—</td>;
                  }
                  const t = max === min ? 1 : (cell.score - min) / (max - min);
                  return (
                    <td
                      key={c.model_id}
                      className="px-1 py-1.5 text-center"
                      style={{ background: `rgba(34,211,238,${0.05 + t * 0.3})` }}
                      title={`${cell.display_name} · ${cell.score} · 官方第 ${cell.rank} 名${cell.agent_scaffold ? ` · ${cell.agent_scaffold}` : ''}`}
                    >
                      <span className="num text-slate-100">{cell.score}</span>
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
}


export function fmtContextK(ctx: number): string {
  if (ctx >= 1_000_000) return `${(ctx / 1_000_000).toFixed(ctx % 1_000_000 === 0 ? 0 : 1)}M`;
  return `${Math.round(ctx / 1000)}K`;
}

/** 数据可信度信息条。 */
function DataFreshnessSummary({ meta, index }: { meta: Meta | null; index: ModelsIndex | null }) {
  const currentCount = index?.models.filter((m) => m.is_current === true).length ?? null;
  const withCoding = index?.models.filter(
    (m) => m.is_current === true && m.capability_indices.coding !== undefined,
  ).length ?? null;
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 rounded-xl border border-slate-500/15 bg-slate-900/30 px-4 py-2.5 text-xs text-slate-400">
      <span>当前活跃模型：<b className="num text-slate-200">{currentCount ?? '—'}</b></span>
      <span>本页有编程证据：<b className="num text-slate-200">{withCoding ?? '—'}</b></span>
      <span>数据更新时间：<b className="num text-slate-200">{fmtDate(meta?.update.last_success)}</b></span>
      <Link to="/methodology" className="ml-auto text-cyan-400 hover:text-cyan-300">数据方法 →</Link>
    </div>
  );
}

function InlineStat({ label, value }: { label: string; value: number | string | null | undefined }) {
  return (
    <div>
      <dt className="inline text-slate-500">{label} </dt>
      <dd className="num inline font-semibold text-slate-200">{value ?? '—'}</dd>
    </div>
  );
}
