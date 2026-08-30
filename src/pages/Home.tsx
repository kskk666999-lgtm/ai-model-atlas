import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { useJson, useMeta } from '@/lib/api';
import { useCapabilities, capShort } from '@/lib/capabilities';
import { fmtDate, fmtScore } from '@/lib/format';
import { providerColor } from '@/types/data';
import type { CapabilityFile, Homepage, ModelsIndex, OfficialRow } from '@/types/data';
import { EmptyState, NoDataState } from '@/components/StateViews';
import { AbilityScatter } from '@/charts/TrendLine';

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
  { id: 'coding', label: '编程', note: 'LiveBench 编程 + Agentic Coding 官方综合（相对百分位，已通过映射门槛）' },
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

  if (error && !rawMeta) {
    return <NoDataState detail={`meta.json 加载失败：${error}`} />;
  }
  const meta = rawMeta;

  const activeTab = TABS.find((t) => t.id === tab)!;
  const officialCap = tab === 'agent' ? 'swe' : tab;

  return (
    <div className="space-y-8">
      {/* 紧凑头部信息（状态圆点在全局导航栏） */}
      <section className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-500/15 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-slate-50 sm:text-3xl">
            全球 AI 模型能力
            <span className="bg-gradient-to-r from-cyan-300 to-violet-400 bg-clip-text text-transparent">对照榜</span>
          </h1>
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-400">
            官方原始分为主，本站计算一律标注为相对百分位。每条分数可点开溯源。
          </p>
        </div>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          <InlineStat label="模型" value={meta?.counts.models} />
          <InlineStat label="基准" value={meta?.counts.benchmarks} />
          <InlineStat label="数据源" value={meta?.counts.sources_active} />
          <InlineStat label="数据更新" value={fmtDate(meta?.update.last_success)} />
        </dl>
      </section>

      {/* 第一屏：核心榜（官方原始分为主） */}
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

      {/* 第二屏：能力 × 模型热力图（官方原始分） */}
      {heatmap && heatmap.capabilities.length > 0 && (
        <section className="panel px-5 py-6">
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="text-lg font-bold text-slate-100">能力 × 模型热力图</h2>
            <span className="badge">官方原始分 · 每行取该能力主基准 Top 12</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            颜色深浅为同一能力内的相对高低；— 表示无数据（不计为 0）。Agent 行为「模型 + Agent 系统」成绩。
          </p>
          <HeatmapGrid data={heatmap} capabilities={capabilities} />
        </section>
      )}

      {/* 第三屏：价格-编程散点 */}
      <PriceAbilityScatter index={index} />

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
        <Link to="/methodology" className="ml-auto text-cyan-400 hover:text-cyan-300">排名是怎么算的 →</Link>
      </section>
    </div>
  );
}

/** 官方原始榜 Top 10（来自对应能力文件，客户端截取）。 */
function OfficialBoard({ capId, highlightAgent, index }: { capId: string; highlightAgent?: boolean; index: ModelsIndex | null }) {
  const { data, loading } = useJson<CapabilityFile>(`/data/capabilities/${capId}.json`);
  if (loading) return <div className="skeleton h-72 w-full" />;
  if (!data || data.official.length === 0) {
    return <EmptyState title="该能力暂无数据" hint="数据接入中，不生成模拟排名。" />;
  }
  // 选记录数最多的单一基准（与后端热力图口径一致），避免混用量纲
  const counts = new Map<string, number>();
  data.official.forEach((r) => counts.set(r.benchmark_id, (counts.get(r.benchmark_id) ?? 0) + 1));
  const topBench = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0][0];
  const rows = data.official.filter((r) => r.benchmark_id === topBench).slice(0, 10);
  const benchName = data.benchmarks.find((b) => b.benchmark_id === topBench)?.benchmark_name ?? topBench;

  return (
    <div className="panel overflow-x-auto">
      <table className="data-table w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-slate-500/15 text-slate-400">
            <th className="px-3 py-2.5 text-left">#</th>
            <th className="px-3 py-2.5 text-left">模型</th>
            <th className="px-3 py-2.5 text-left">厂商</th>
            {highlightAgent && <th className="px-3 py-2.5 text-left">Agent 框架</th>}
            <th className="px-3 py-2.5 text-left">官方原始分</th>
            <th className="px-3 py-2.5 text-left">评测日期</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <BoardRow key={`${r.model_id}-${r.agent_scaffold ?? ''}`} r={r} highlightAgent={highlightAgent}
              provider={index?.models.find((m) => m.model_id === r.model_id)?.provider ?? null} />
          ))}
        </tbody>
      </table>
      <p className="px-4 py-2.5 text-[11px] text-slate-500">
        基准：{benchName} · 每条分数可点击查看溯源 · 共 {counts.get(topBench)} 条官方记录
      </p>
    </div>
  );
}

function BoardRow({ r, highlightAgent, provider }: { r: OfficialRow; highlightAgent?: boolean; provider: string | null }) {
  const isAgent = r.evaluation_target_type === 'model_plus_agent' || r.evaluation_target_type === 'complete_agent_system';
  return (
    <tr className="border-b border-slate-500/10 hover:bg-slate-500/5">
      <td className="px-3 py-2.5">
        <span className={`num font-semibold ${r.rank === 1 ? 'rank-medal-1' : r.rank === 2 ? 'rank-medal-2' : r.rank === 3 ? 'rank-medal-3' : 'text-slate-400'}`}>
          {r.rank}{r.tie && <span className="ml-1 text-[10px] font-normal text-amber-300">并列</span>}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: providerColor(provider) }} aria-hidden />
          <span className="truncate font-medium text-slate-100" title={r.raw_model_name || r.model_id}>
            {r.raw_model_name || r.model_id}
          </span>
          {isAgent && highlightAgent && (
            <span className="badge border-violet-400/40 bg-violet-400/10 text-violet-200">模型+Agent</span>
          )}
        </div>
      </td>
      <td className="px-3 py-2.5 text-slate-400">{provider ?? '未知厂商'}</td>
      {highlightAgent && <td className="px-3 py-2.5 text-xs text-slate-400">{r.agent_scaffold ?? '—'}</td>}
      <td className="px-3 py-2.5">
        <span className="num font-semibold text-cyan-300">{fmtScore(r.score, r.score_unit)}</span>
      </td>
      <td className="px-3 py-2.5"><span className="num text-slate-400">{fmtDate(r.evaluation_date)}</span></td>
    </tr>
  );
}

/** 性价比榜：编程官方相对位置 ÷ 输入价格（客户端计算，公式公开）。 */
function ValueBoard({ index }: { index: ModelsIndex | null }) {
  const { data: coding } = useJson<CapabilityFile>('/data/capabilities/coding.json');
  const rows = useMemo(() => {
    if (!index || !coding || !coding.composite) return null;
    // 编程相对百分位（已通过映射门槛的综合）÷ 输入价格
    const priceOf = new Map(index.models.map((m) => [m.model_id, m.price_input_usd_per_mtok]));
    const out = coding.composite.models
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

/** 价格-编程官方分散点。 */
function PriceAbilityScatter({ index }: { index: ModelsIndex | null }) {
  const { data: coding } = useJson<CapabilityFile>('/data/capabilities/coding.json');
  const points = useMemo(() => {
    if (!index || !coding) return [];
    const priceOf = new Map(index.models.map((m) => [m.model_id, m.price_input_usd_per_mtok]));
    if (!coding.composite) return [];
    return coding.composite.models
      .map((m) => ({ mid: m.model_id, price: priceOf.get(m.model_id) }))
      .filter((x): x is { mid: string; price: number } => typeof x.price === 'number' && x.price > 0)
      .map((x) => {
        const cell = coding.composite!.models.find((m) => m.model_id === x.mid)!;
        return { name: x.mid, x: x.price, y: cell.index, color: providerColor(null), modelId: x.mid };
      });
  }, [index, coding]);
  if (points.length < 3) return null;
  return (
    <section className="panel px-5 py-6">
      <h2 className="text-lg font-bold text-slate-100">价格 × 编程相对百分位</h2>
      <p className="mt-1 text-xs text-slate-500">
        横轴为 LiveBench 官方统计输入价（USD/1M，对数轴更直观，此处线性），纵轴为编程相对百分位（通过映射门槛的综合）。
      </p>
      <div className="mt-3">
        <AbilityScatter
          points={points}
          xName="输入价格 USD/1M"
          yName="编程相对百分位"
          logX
          height={320}
        />
      </div>
    </section>
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
