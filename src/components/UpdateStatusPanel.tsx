import { useState } from 'react';
import { Activity, ChevronDown, Database, RefreshCw, ShieldCheck, X } from 'lucide-react';
import { useJson } from '@/lib/api';
import { fmtDateTime } from '@/lib/format';
import type { Meta, SourceHealth } from '@/types/data';

/** 首页右侧"自动更新状态面板"：桌面端固定，移动端折叠为抽屉。 */
export function UpdateStatusPanel({ meta }: { meta: Meta | null }) {
  const { data: health } = useJson<SourceHealth>('/data/source-health.json');
  const [open, setOpen] = useState(false);

  const counts = health?.counts ?? { healthy: 0, degraded: 0, failed: 0, disabled: 0 };
  const lastSuccess = meta?.update.last_success ?? null;
  const nextDue = lastSuccess
    ? fmtDateTime(new Date(new Date(lastSuccess).getTime() + (meta?.update.interval_hours ?? 12) * 3600_000).toISOString())
    : '—';
  const stale = lastSuccess
    ? Date.now() - new Date(lastSuccess).getTime() > 3 * 24 * 3600_000
    : true;

  const body = (
    <div className="panel p-4 text-sm">
      <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold tracking-wide text-slate-200">
        <Activity size={15} className="text-cyan-300" aria-hidden />
        自动更新状态
      </div>
      <dl className="space-y-2">
        <Row label="上次更新成功" value={fmtDateTime(lastSuccess)} />
        <Row label="下次计划更新" value={nextDue} sub={`GitHub Actions 调度 · 实际执行可能略有延迟`} />
        <Row
          label="健康数据源"
          value={<span className="text-emerald-300">{counts.healthy}</span>}
        />
        <Row
          label="降级 / 失败"
          value={
            <span className={(counts.degraded + counts.failed > 0) ? 'text-amber-300' : ''}>
              {counts.degraded} / {counts.failed}
            </span>
          }
        />
        <Row label="收录模型" value={meta?.counts.models ?? '—'} />
        <Row label="接入基准" value={meta?.counts.benchmarks ?? '—'} />
        <Row label="历史快照" value={meta?.counts.history_snapshots ?? '—'} />
        <Row label="最新数据提交" value={meta?.latest_commit ? meta.latest_commit.slice(0, 7) : '—'} />
      </dl>

      {stale && (
        <p className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
          数据已超过 3 天未更新，可能存在过期数据。可到 GitHub Actions 手动触发
          <span className="num"> update-data </span>工作流。
        </p>
      )}
      {(meta?.update.failed_sources.length ?? 0) > 0 && (
        <p className="mt-2 rounded-lg border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-xs text-rose-200">
          上次运行失败来源：{meta?.update.failed_sources.join('、')}（已保留其上次成功数据）
        </p>
      )}

      <p className="mt-3 flex items-start gap-1.5 text-xs text-slate-400">
        <ShieldCheck size={14} className="mt-0.5 shrink-0 text-emerald-300" aria-hidden />
        更新流水线为普通 Python 抓取 + 确定性计算，全程不调用任何大模型 API。
      </p>
      {health && (
        <a
          className="mt-3 flex items-center gap-1.5 text-xs text-cyan-300 hover:text-cyan-200"
          href="#/sources"
        >
          <Database size={13} aria-hidden /> 查看全部 {health.sources.length} 个数据源详情
        </a>
      )}
    </div>
  );

  return (
    <>
      {/* 桌面端：右侧固定 */}
      <aside className="panel-silent sticky top-20 hidden w-[300px] shrink-0 lg:block" aria-label="自动更新状态面板">
        {body}
      </aside>

      {/* 移动端：浮动按钮 + 抽屉 */}
      <button
        className="fixed bottom-5 right-4 z-40 flex items-center gap-2 rounded-full border border-slate-500/40 bg-slate-900/95 px-4 py-2.5 text-sm text-slate-100 shadow-lg lg:hidden"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-label="打开自动更新状态面板"
      >
        <RefreshCw size={15} className="text-cyan-300" aria-hidden /> 更新状态
      </button>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="自动更新状态面板">
          <button className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} aria-label="关闭" />
          <div className="absolute inset-x-3 bottom-3 max-h-[75vh] overflow-auto">
            <button
              className="mb-2 flex items-center gap-1 rounded-lg border border-slate-500/40 bg-slate-900 px-3 py-1.5 text-xs text-slate-300"
              onClick={() => setOpen(false)}
            >
              <X size={13} aria-hidden /> 收起 <ChevronDown size={13} aria-hidden />
            </button>
            {body}
          </div>
        </div>
      )}
    </>
  );
}

function Row({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-slate-400">{label}</dt>
      <dd className="num text-right text-slate-200">
        {value}
        {sub && <span className="block text-[10px] text-slate-500">{sub}</span>}
      </dd>
    </div>
  );
}
