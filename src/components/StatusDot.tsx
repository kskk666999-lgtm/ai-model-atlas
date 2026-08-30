import { useState } from 'react';
import { Activity } from 'lucide-react';
import { useJson, useMeta } from '@/lib/api';
import { fmtDateTime } from '@/lib/format';
import type { SourceHealth } from '@/types/data';

/** 顶部状态圆点：绿=全部健康，黄=有降级/失败，红=严重。点击展开详情。 */
export function StatusDot() {
  const { meta } = useMeta();
  const { data: health } = useJson<SourceHealth>('/data/source-health.json');
  const [open, setOpen] = useState(false);

  const counts = health?.counts ?? { healthy: 0, degraded: 0, failed: 0, disabled: 0 };
  const totalActive = counts.healthy + counts.degraded + counts.failed;
  const lastSuccess = meta?.update.last_success ?? null;
  const hoursAgo = lastSuccess
    ? Math.max(0, Math.round((Date.now() - new Date(lastSuccess).getTime()) / 3_600_000))
    : null;
  const stale = hoursAgo === null || hoursAgo > 26;
  const color = counts.failed > 0 || (stale && totalActive > 0)
    ? 'bg-rose-400'
    : counts.degraded > 0 || stale
      ? 'bg-amber-400'
      : 'bg-emerald-400';

  return (
    <span className="relative">
      <button
        className="flex items-center gap-1.5 rounded-full border border-slate-500/30 px-2.5 py-1 text-[11px] text-slate-300 hover:border-slate-400/50"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`数据状态：${counts.healthy}/${totalActive} 来源健康`}
      >
        <span className={`inline-block h-2 w-2 rounded-full ${color} ${stale ? '' : 'animate-pulse'}`} aria-hidden />
        <span className="num hidden sm:inline">
          {totalActive > 0 ? `${counts.healthy}/${totalActive}` : '—'}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72" role="dialog" aria-label="数据状态详情">
          <div className="panel p-4 text-sm">
            <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-slate-200">
              <Activity size={15} className="text-cyan-300" aria-hidden /> 数据状态
            </div>
            <dl className="space-y-2">
              <Row label="健康 / 降级 / 失败" value={`${counts.healthy} / ${counts.degraded} / ${counts.failed}`} />
              <Row label="上次更新成功" value={fmtDateTime(lastSuccess)} />
              <Row label="更新计划" value="每日约 09:00 / 21:00（北京时间，可能有调度延迟）" />
              <Row label="收录模型 / 基准" value={`${meta?.counts.models ?? '—'} / ${meta?.counts.benchmarks ?? '—'}`} />
              {stale && (
                <p className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                  数据超过 26 小时未更新。可到 GitHub Actions 手动触发 update-data。
                </p>
              )}
            </dl>
            <a href="#/sources" className="mt-3 block text-xs text-cyan-300 hover:text-cyan-200">
              查看全部数据源详情 →
            </a>
          </div>
        </div>
      )}
    </span>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="shrink-0 text-slate-400">{label}</dt>
      <dd className="num text-right text-slate-200">{value}</dd>
    </div>
  );
}
