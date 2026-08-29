import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowUpDown, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import type { ModelIndexItem, OfficialRow } from '@/types/data';
import { providerColor } from '@/types/data';
import { LevelBadge, RankCell, TypeBadge } from './Badges';
import { fmtContext, fmtDate, fmtScore } from '@/lib/format';

export interface OfficialFilters {
  query: string;
  provider: string;
  chinaOnly: boolean;
  openWeightsOnly: boolean;
  agentOnly: boolean | null; // null=全部, true=仅Agent, false=仅基础模型
  level: string; // '', 'A','B','C'
}

export const emptyOfficialFilters: OfficialFilters = {
  query: '',
  provider: '',
  chinaOnly: false,
  openWeightsOnly: false,
  agentOnly: null,
  level: '',
};

export interface JoinedRow extends OfficialRow {
  provider: string | null;
  region: string | null;
  open_weights: boolean | null;
}

/** 把官方原始榜与模型注册表信息拼在一起（未映射模型保留原始名称）。 */
export function joinRows(rows: OfficialRow[], models: ModelIndexItem[]): JoinedRow[] {
  const byId = new Map(models.map((m) => [m.model_id, m]));
  return rows.map((r) => {
    const m = byId.get(r.model_id);
    return {
      ...r,
      provider: m?.provider ?? null,
      region: m?.region ?? null,
      open_weights: m?.open_weights ?? null,
    };
  });
}

export function applyOfficialFilters(rows: JoinedRow[], f: OfficialFilters): JoinedRow[] {
  return rows.filter((r) => {
    const q = f.query.trim().toLowerCase();
    if (q && !(r.model_id.toLowerCase().includes(q) || (r.raw_model_name || '').toLowerCase().includes(q)
      || (r.provider || '').toLowerCase().includes(q))) return false;
    if (f.provider && (r.provider || '未知厂商') !== f.provider) return false;
    if (f.chinaOnly && r.region !== 'cn') return false;
    if (f.openWeightsOnly && r.open_weights !== true) return false;
    if (f.agentOnly === true && r.evaluation_target_type !== 'model_plus_agent' && r.evaluation_target_type !== 'complete_agent_system') return false;
    if (f.agentOnly === false && (r.evaluation_target_type === 'model_plus_agent' || r.evaluation_target_type === 'complete_agent_system')) return false;
    if (f.level && r.source_level !== f.level) return false;
    return true;
  });
}

export function OfficialTable({
  rows,
  onPick,
}: {
  rows: JoinedRow[];
  onPick: (row: OfficialRow) => void;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 25 });

  const columnHelper = createColumnHelper<JoinedRow>();
  const columns = useMemo(
    () => [
      columnHelper.accessor('rank', {
        header: '排名',
        cell: (info) => <RankCell rank={info.getValue()} tie={info.row.original.tie} />,
      }),
      columnHelper.accessor('model_id', {
        header: '模型',
        cell: (info) => {
          const r = info.row.original;
          return (
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: providerColor(r.provider) }}
                aria-hidden
              />
              <Link
                to={r.model_is_unmapped ? '#' : `/model/${r.model_id}`}
                className={`truncate font-medium ${r.model_is_unmapped ? 'text-slate-200' : 'text-slate-100 hover:text-cyan-300'}`}
                onClick={(e: React.MouseEvent) => r.model_is_unmapped && e.preventDefault()}
                title={r.model_is_unmapped ? (r.raw_model_name || r.model_id) : r.model_id}
              >
                {r.raw_model_name || r.model_id}
              </Link>
            </div>
          );
        },
      }),
      columnHelper.accessor('provider', {
        header: '厂商',
        cell: (info) => info.getValue() || <span className="text-faint">未知厂商</span>,
      }),
      columnHelper.accessor('evaluation_target_type', {
        header: '类型',
        cell: (info) => <TypeBadge type={info.getValue()} />,
      }),
      columnHelper.accessor('score', {
        header: '分数',
        cell: (info) => (
          <button
            className="num rounded px-2 py-0.5 font-semibold text-cyan-300 hover:bg-cyan-400/10"
            onClick={() => onPick(info.row.original)}
            title="点击查看数据来源"
          >
            {fmtScore(info.getValue(), info.row.original.score_unit)}
          </button>
        ),
      }),
      columnHelper.accessor('source_level', {
        header: '来源等级',
        cell: (info) => <LevelBadge level={info.getValue()} />,
      }),
      columnHelper.accessor('evaluation_date', {
        header: '评测日期',
        cell: (info) => <span className="num text-slate-400">{fmtDate(info.getValue())}</span>,
      }),
      columnHelper.accessor('agent_scaffold', {
        header: 'Agent 框架',
        cell: (info) => <span className="text-xs text-slate-400">{info.getValue() || '—'}</span>,
      }),
    ],
    [columnHelper, onPick],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, pagination },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  return (
    <div>
      <div className="panel overflow-x-auto">
        <table className="data-table w-full min-w-[720px] text-sm">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-slate-500/15">
                {hg.headers.map((h) => (
                  <th key={h.id} className="px-3 py-2.5 text-left font-medium text-slate-400">
                    <button
                      className="inline-flex items-center gap-1 hover:text-slate-200"
                      onClick={h.column.getToggleSortingHandler()}
                      disabled={!h.column.getCanSort()}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getCanSort() && <ArrowUpDown size={12} aria-hidden />}
                    </button>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-b border-slate-500/10 hover:bg-slate-500/5">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2.5">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="px-4 py-8 text-center text-sm text-slate-400">没有符合筛选条件的记录</p>}
      </div>
      <div className="mt-3 flex items-center justify-between text-sm text-slate-400">
        <span>
          共 {rows.length} 条 · 第 {table.getState().pagination.pageIndex + 1} / {Math.max(1, table.getPageCount())} 页
        </span>
        <div className="flex gap-2">
          <button
            className="rounded-lg border border-slate-500/30 p-1.5 disabled:opacity-40"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            aria-label="上一页"
          >
            <ChevronLeft size={15} />
          </button>
          <button
            className="rounded-lg border border-slate-500/30 p-1.5 disabled:opacity-40"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            aria-label="下一页"
          >
            <ChevronRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="relative block">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden />
      <input
        className="w-full rounded-lg border border-slate-500/25 bg-slate-900/60 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder:text-slate-500 focus:border-cyan-400/50"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || '搜索模型 / 厂商…'}
        aria-label="搜索模型"
      />
    </label>
  );
}

export function FilterBar({
  filters,
  setFilters,
  providers,
  showAgentToggle = true,
}: {
  filters: OfficialFilters;
  setFilters: (f: OfficialFilters) => void;
  providers: string[];
  showAgentToggle?: boolean;
}) {
  const toggle = (key: keyof OfficialFilters) => () =>
    setFilters({ ...filters, [key]: !filters[key] } as OfficialFilters);
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <select
        className="rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-slate-200"
        value={filters.provider}
        onChange={(e) => setFilters({ ...filters, provider: e.target.value })}
        aria-label="按厂商筛选"
      >
        <option value="">全部厂商</option>
        {providers.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
      <label className="badge cursor-pointer select-none">
        <input type="checkbox" checked={filters.chinaOnly} onChange={toggle('chinaOnly')} className="accent-cyan-400" /> 中国模型
      </label>
      <label className="badge cursor-pointer select-none">
        <input type="checkbox" checked={filters.openWeightsOnly} onChange={toggle('openWeightsOnly')} className="accent-cyan-400" /> 开放权重
      </label>
      {showAgentToggle && (
        <label className="badge cursor-pointer select-none">
          <input
            type="checkbox"
            checked={filters.agentOnly === true}
            onChange={() => setFilters({ ...filters, agentOnly: filters.agentOnly === true ? null : true })}
            className="accent-cyan-400"
          /> 仅 Agent 系统
        </label>
      )}
      <select
        className="rounded-lg border border-slate-500/25 bg-slate-900/60 px-2.5 py-1.5 text-slate-200"
        value={filters.level}
        onChange={(e) => setFilters({ ...filters, level: e.target.value })}
        aria-label="按来源等级筛选"
      >
        <option value="">全部来源等级</option>
        <option value="A">仅 A 级</option>
        <option value="B">仅 B 级</option>
        <option value="C">仅 C 级</option>
      </select>
      {(filters.query || filters.provider || filters.chinaOnly || filters.openWeightsOnly || filters.agentOnly !== null || filters.level) && (
        <button className="badge hover:text-slate-200" onClick={() => setFilters(emptyOfficialFilters)}>
          清除筛选
        </button>
      )}
    </div>
  );
}

export function ContextCell({ ctx }: { ctx: number | null }) {
  return <span className="num text-slate-300">{fmtContext(ctx)}</span>;
}
