import { useJson } from '@/lib/api';
import type { SourceHealth } from '@/types/data';
import { fmtDateTime } from '@/lib/format';
import { LevelBadge } from '@/components/Badges';
import { EmptyState, Skeleton } from '@/components/StateViews';

export function SourcesPage() {
  const { data, loading } = useJson<SourceHealth>('/data/source-health.json');
  if (loading) return <Skeleton rows={8} />;
  if (!data) return <EmptyState title="暂无数据来源信息" hint="数据流水线运行一次后，这里会显示每个来源的健康状态。" />;

  const statusBadge = (s: SourceHealth['sources'][number]) => {
    switch (s.run_status) {
      case 'ok':
        return <span className="badge border-emerald-400/40 bg-emerald-400/10 text-emerald-300">正常</span>;
      case 'degraded':
        return <span className="badge border-amber-400/40 bg-amber-400/10 text-amber-300">降级（使用上次数据）</span>;
      case 'failed':
        return <span className="badge border-rose-400/40 bg-rose-400/10 text-rose-300">失败</span>;
      case 'skipped':
        return <span className="badge border-slate-400/30 text-slate-400">未运行（可选）</span>;
      case 'disabled':
        return <span className="badge border-slate-400/30 text-slate-400">已停用</span>;
    }
  };

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">数据来源</h1>
        <p className="mt-1 text-sm text-slate-400">
          全部榜单数据均来自下列官方或第三方机构发布的结构化结果。每个来源按可靠性分级，
          并标注是否进入默认综合排名。更新于 {fmtDateTime(data.generated_at)}（UTC）。
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <span className="badge border-emerald-400/40 text-emerald-300">健康 {data.counts.healthy}</span>
          <span className="badge border-amber-400/40 text-amber-300">降级 {data.counts.degraded}</span>
          <span className="badge border-rose-400/40 text-rose-300">失败 {data.counts.failed}</span>
          <span className="badge">停用 {data.counts.disabled}</span>
        </div>
      </header>

      <div className="space-y-4">
        {data.sources.map((s) => (
          <article key={s.source_id} className="panel px-5 py-5">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-base font-bold text-slate-100">{s.source_name}</h2>
              <LevelBadge level={s.source_level} />
              {statusBadge(s)}
              {s.included_in_composite ? (
                <span className="badge border-cyan-400/30 text-cyan-300">进入综合排名</span>
              ) : (
                <span className="badge">不进入综合排名</span>
              )}
              {s.requires_api_key && <span className="badge border-amber-400/30 text-amber-300">需要 API Key（仅服务端）</span>}
            </div>

            {s.description && <p className="mt-2.5 text-sm leading-6 text-slate-400">{s.description}</p>}

            <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
              <Item label="数据条数" value={s.record_count > 0 ? String(s.record_count) : '—'} />
              <Item label="最近成功更新" value={fmtDateTime(s.last_success)} />
              <Item label="最新评测 / 上游快照" value={fmtDateTime(s.data_freshness)} />
            </dl>

            {s.error_message && (
              <p className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/5 px-3 py-2 text-xs leading-5 text-amber-200/90">
                {s.error_message}
              </p>
            )}

            <div className="mt-3 flex flex-wrap gap-4 text-xs">
              {s.homepage_url && (
                <a className="text-cyan-400 hover:text-cyan-300" href={s.homepage_url} target="_blank" rel="noreferrer">官方网站 ↗</a>
              )}
              {s.docs_url && (
                <a className="text-cyan-400 hover:text-cyan-300" href={s.docs_url} target="_blank" rel="noreferrer">官方仓库 / 文档 ↗</a>
              )}
              {s.attribution && <span className="text-slate-500">{s.attribution}</span>}
              {s.license && <span className="text-slate-500">许可：{s.license}</span>}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="num mt-0.5 text-slate-300">{value}</dd>
    </div>
  );
}
