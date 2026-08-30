import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { useJson } from '@/lib/api';
import { fmtContextK } from '@/pages/Home';
import { Skeleton } from '@/components/StateViews';

interface DirectoryEntry {
  provider_id: string;
  model_id: string;
  name: string;
  family: string | null;
  release_date: string | null;
  last_updated: string | null;
  status: string | null;
  reasoning: boolean | null;
  tool_call: boolean | null;
  structured_output: boolean | null;
  open_weights: boolean | null;
  context_window: number | null;
  max_output: number | null;
  input_price: number | null;
  output_price: number | null;
  modalities: string[];
  freshness_days: number | null;
  freshness_bucket: string;
  lifecycle_status: string;
  is_current: boolean;
}

const PAGE_SIZE = 50;

const BUCKETS = ['NEW', 'FRESH', 'ACTIVE', 'AGING', 'LEGACY', 'UNKNOWN'] as const;

function bucketColor(b: string): string {
  switch (b) {
    case 'NEW': return 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300';
    case 'FRESH': return 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300';
    case 'ACTIVE': return 'border-sky-400/30 bg-sky-400/10 text-sky-300';
    case 'AGING': return 'border-amber-400/30 bg-amber-400/10 text-amber-300';
    case 'LEGACY': return 'border-slate-500/40 bg-slate-500/10 text-slate-400';
    default: return 'border-slate-500/30 text-slate-500';
  }
}

/** 全部模型目录页（数据源：models.dev 模型目录，与 Benchmark 证据库分离）。 */
export function ModelsPage() {
  const { data, loading, error } = useJson<{ count: number; models: DirectoryEntry[]; source: string }>('/data/directory.json');
  const [query, setQuery] = useState('');
  const [provider, setProvider] = useState('');
  const [bucket, setBucket] = useState('');
  const [onlyCurrent, setOnlyCurrent] = useState(false);
  const [openWeights, setOpenWeights] = useState(false);
  const [sort, setSort] = useState<'release' | 'price' | 'context'>('release');
  const [page, setPage] = useState(0);

  const providers = useMemo(() => {
    if (!data) return [];
    const set = new Map<string, number>();
    data.models.forEach((m) => set.set(m.provider_id, (set.get(m.provider_id) ?? 0) + 1));
    return Array.from(set.entries()).sort((a, b) => b[1] - a[1]).slice(0, 40).map(([p]) => p);
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    let rows = data.models;
    if (q) rows = rows.filter((m) => m.model_id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q) || m.provider_id.includes(q));
    if (provider) rows = rows.filter((m) => m.provider_id === provider);
    if (bucket) rows = rows.filter((m) => m.freshness_bucket === bucket);
    if (onlyCurrent) rows = rows.filter((m) => m.is_current);
    if (openWeights) rows = rows.filter((m) => m.open_weights === true);
    const sorted = [...rows];
    if (sort === 'release') {
      sorted.sort((a, b) => (b.release_date || b.last_updated || '').localeCompare(a.release_date || a.last_updated || ''));
    } else if (sort === 'price') {
      sorted.sort((a, b) => (a.input_price ?? 9e9) - (b.input_price ?? 9e9));
    } else if (sort === 'context') {
      sorted.sort((a, b) => (b.context_window ?? 0) - (a.context_window ?? 0));
    }
    return sorted;
  }, [data, query, provider, bucket, onlyCurrent, openWeights, sort]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  if (error) {
    return (
      <div className="panel px-6 py-12 text-center text-sm text-slate-400">
        模型目录加载失败（{error}）。目录来自 models.dev，若上游不可用请稍后重试；
        Benchmark 榜单不受影响。
      </div>
    );
  }
  if (loading) return <Skeleton rows={8} />;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">全部模型目录</h1>
        <p className="mt-1 text-sm text-slate-400">
          {data?.count ?? 0} 个模型（来源：models.dev 模型目录，能力/价格/上下文元数据）。
          Benchmark 成绩见各能力榜单——目录负责「现在有哪些模型」，榜单负责「测出来怎么样」。
        </p>
      </header>

      <div className="panel px-4 py-4">
        <div className="flex flex-col gap-3">
          <label className="relative block">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden />
            <input
              className="w-full rounded-lg border border-slate-500/25 bg-slate-900/60 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder:text-slate-500"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setPage(0); }}
              placeholder="搜索模型名 / Provider…"
              aria-label="搜索模型目录"
            />
          </label>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <select
              className="rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-slate-200"
              value={provider}
              onChange={(e) => { setProvider(e.target.value); setPage(0); }}
              aria-label="按 Provider 筛选"
            >
              <option value="">全部 Provider（Top 40）</option>
              {providers.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select
              className="rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-slate-200"
              value={bucket}
              onChange={(e) => { setBucket(e.target.value); setPage(0); }}
              aria-label="按新鲜度筛选"
            >
              <option value="">全部新鲜度</option>
              {BUCKETS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <label className="badge cursor-pointer select-none">
              <input type="checkbox" checked={onlyCurrent} onChange={(e) => { setOnlyCurrent(e.target.checked); setPage(0); }} className="accent-cyan-400" />
              仅当前模型
            </label>
            <label className="badge cursor-pointer select-none">
              <input type="checkbox" checked={openWeights} onChange={(e) => { setOpenWeights(e.target.checked); setPage(0); }} className="accent-cyan-400" />
              开放权重
            </label>
            <select
              className="ml-auto rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-slate-200"
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
              aria-label="排序"
            >
              <option value="release">按发布日期（新→旧）</option>
              <option value="price">按输入价格（低→高）</option>
              <option value="context">按上下文（大→小）</option>
            </select>
          </div>
        </div>
      </div>

      {/* 桌面：高密度表格 */}
      <div className="panel hidden overflow-x-auto md:block">
        <table className="data-table w-full text-sm">
          <thead>
            <tr className="border-b border-slate-500/15 text-slate-400">
              <th className="px-3 py-2 text-left">模型</th>
              <th className="px-3 py-2 text-left">Provider</th>
              <th className="px-3 py-2 text-left">发布</th>
              <th className="px-3 py-2 text-left">状态</th>
              <th className="px-3 py-2 text-left">上下文</th>
              <th className="px-3 py-2 text-left">推理</th>
              <th className="px-3 py-2 text-left">工具</th>
              <th className="px-3 py-2 text-left">开放权重</th>
              <th className="px-3 py-2 text-left">输入价 /1M</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((m) => (
              <tr key={`${m.provider_id}/${m.model_id}`} className="border-b border-slate-500/10 hover:bg-slate-500/5">
                <td className="px-3 py-2">
                  <span className="font-medium text-slate-100">{m.name}</span>
                  <span className="ml-2 text-[10px] text-slate-600">{m.model_id}</span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-400">{m.provider_id}</td>
                <td className="num px-3 py-2 text-xs text-slate-400">{m.release_date || m.last_updated || '—'}</td>
                <td className="px-3 py-2"><span className={`badge ${bucketColor(m.freshness_bucket)}`}>{m.freshness_bucket}</span></td>
                <td className="num px-3 py-2 text-xs text-slate-300">{m.context_window ? fmtContextK(m.context_window) : '—'}</td>
                <td className="px-3 py-2 text-xs">{m.reasoning ? '✓' : '—'}</td>
                <td className="px-3 py-2 text-xs">{m.tool_call ? '✓' : '—'}</td>
                <td className="px-3 py-2 text-xs">{m.open_weights === null ? '—' : m.open_weights ? '✓' : '—'}</td>
                <td className="num px-3 py-2 text-xs text-slate-300">
                  {m.input_price !== null && m.input_price !== undefined ? `$${m.input_price >= 1 ? m.input_price.toFixed(2) : m.input_price.toFixed(3)}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 移动端：卡片 */}
      <div className="space-y-2 md:hidden">
        {pageRows.map((m) => (
          <div key={`${m.provider_id}/${m.model_id}`} className="panel px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold text-slate-100">{m.name}</span>
              <span className={`badge ${bucketColor(m.freshness_bucket)}`}>{m.freshness_bucket}</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">{m.provider_id} · {m.release_date || m.last_updated || '—'}</p>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
              {m.context_window ? <span className="num">上下文 {fmtContextK(m.context_window)}</span> : null}
              {m.reasoning && <span>推理</span>}
              {m.tool_call && <span>工具调用</span>}
              {m.open_weights && <span className="text-emerald-300">开放权重</span>}
              {m.input_price !== null && m.input_price !== undefined && (
                <span className="num">${m.input_price >= 1 ? m.input_price.toFixed(2) : m.input_price.toFixed(3)}/1M</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm text-slate-400">
        <span>共 {filtered.length} 个模型 · 第 {safePage + 1} / {pageCount} 页</span>
        <div className="flex gap-2">
          <button className="rounded-lg border border-slate-500/30 px-3 py-1 disabled:opacity-40" disabled={safePage === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}>上一页</button>
          <button className="rounded-lg border border-slate-500/30 px-3 py-1 disabled:opacity-40" disabled={safePage >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}>下一页</button>
        </div>
      </div>
    </div>
  );
}
