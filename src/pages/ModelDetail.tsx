import { useParams, Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { useJson } from '@/lib/api';
import { useCapabilities, capName, capShort } from '@/lib/capabilities';
import type { ModelDetail, OfficialRow } from '@/types/data';
import { ModelRadar, type RadarSeries } from '@/charts/ModelRadar';
import { TrendLine } from '@/charts/TrendLine';
import { fmtContext, fmtDate, fmtScore } from '@/lib/format';
import { LevelBadge, TypeBadge, RankCell, SourceDrawer, OpenWeightBadge } from '@/components/Badges';
import { EmptyState, ErrorState, Skeleton } from '@/components/StateViews';
import { useState } from 'react';

export function ModelDetailPage() {
  const { modelId = '' } = useParams();
  const { capabilities } = useCapabilities();
  const { data, error, loading } = useJson<ModelDetail>(`/data/models/${modelId}.json`);
  const [picked, setPicked] = useState<OfficialRow | null>(null);

  if (loading) return <Skeleton rows={8} />;
  if (error) return <ErrorState error={error} hint="该模型可能尚未被任何数据源收录，或未映射到注册表。" />;
  if (!data) return <EmptyState title="未找到模型" />;

  const m = data.meta;
  const fresh = (data as unknown as {
    freshness?: {
      freshness_days: number | null; freshness_bucket: string | null;
      lifecycle_status: string; is_current: boolean | null;
      release_date: string | null; last_updated: string | null; matched_directory: boolean;
    };
    lineage?: {
      family: string | null;
      previous: { model_id: string; display_name: string; release_date: string | null } | null;
      next: { model_id: string; display_name: string; release_date: string | null } | null;
    };
  });
  const freshness = fresh.freshness;
  const lineage = fresh.lineage;
  const indicators = data.radar.map((r) => ({ name: r.name, max: 100 }));
  const series: RadarSeries[] = [
    { name: m.display_name, color: '#22d3ee', values: data.radar.map((r) => r.index) },
  ];

  return (
    <div className="space-y-6">
      <header className="panel px-6 py-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">{m.display_name}</h1>
            <p className="mt-1 text-sm text-slate-400">
              {m.provider ?? '未知厂商'} · {m.family}
              {m.variant ? ` · ${m.variant}` : ''}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {freshness && freshness.is_current !== null && freshness.is_current !== undefined && (
                freshness.is_current
                  ? <span className="badge border-emerald-400/40 bg-emerald-400/10 text-emerald-200">当前模型</span>
                  : <span className="badge border-slate-500/40 bg-slate-500/10 text-slate-400">
                      {freshness.lifecycle_status === 'deprecated' ? '已弃用' : '历史模型'}
                    </span>
              )}
              {freshness?.freshness_bucket && freshness.freshness_bucket !== 'UNKNOWN' && (
                <span className="badge border-cyan-400/30 bg-cyan-400/10 text-cyan-200">
                  {freshness.freshness_bucket}
                  {freshness.freshness_days !== null && (
                    <span className="ml-1 text-[10px] text-slate-400">
                      · 发布于 {freshness.freshness_days} 天前
                    </span>
                  )}
                </span>
              )}
              <OpenWeightBadge open={m.open_weights} />
              <span className="badge">上下文 {fmtContext(m.context_window)}</span>
              <span className="badge">发布 {fmtDate(m.release_date)}</span>
              <span className="badge">模态 {m.modalities.join('/')}</span>
              {m.region === 'cn' && <span className="badge border-red-400/40 bg-red-400/10 text-red-200">中国模型</span>}
              {m.license && <span className="badge">{m.license}</span>}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 text-sm">
            {m.overall_index !== null && (
              <span className="panel-2 px-4 py-2">
                本站相对百分位（综合，参考值）
                <span className="num ml-2 text-lg font-bold text-cyan-300">{m.overall_index.toFixed(1)}</span>
                <span className="ml-1 text-xs text-slate-400">第 {m.overall_rank} 名</span>
              </span>
            )}
            {m.official_model_page && (
              <a
                className="flex items-center gap-1 text-cyan-300 hover:text-cyan-200"
                href={m.official_model_page}
                target="_blank"
                rel="noreferrer"
              >
                官方页面 <ExternalLink size={13} />
              </a>
            )}
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="panel px-5 py-6">
          <h2 className="text-lg font-bold text-slate-100">能力雷达图</h2>
          <p className="mt-1 text-xs text-slate-500">
            数值为本站相对百分位（0~100，表示在当前参与计算的模型集合中的相对位置，不是能力满分），
            仅包含通过全部质量门槛的能力；缺失能力不绘制。
          </p>
          {data.radar.length ? (
            <ModelRadar indicators={indicators} series={series} height={360} />
          ) : (
            <p className="py-10 text-center text-sm text-slate-500">
              该模型暂无通过质量门槛的能力百分位（多数能力当前仅提供来源原始榜）。
            </p>
          )}
        </section>

        <section className="panel px-5 py-6">
          <h2 className="text-lg font-bold text-slate-100">各项相对排名</h2>
          <ul className="mt-3 divide-y divide-slate-500/10">
            {data.radar.map((r) => (
              <li key={r.capability_id} className="flex items-center gap-3 py-2.5 text-sm">
                <Link to={`/leaderboard?cap=${r.capability_id}`} className="min-w-0 flex-1 truncate text-slate-200 hover:text-cyan-300">
                  {capName(capabilities, r.capability_id)}
                </Link>
                <span className="num text-slate-400">{r.index.toFixed(1)}</span>
                <RankCell rank={r.rank} />
              </li>
            ))}
            {data.radar.length === 0 && <li className="py-6 text-sm text-slate-500">暂无通过门槛的能力百分位</li>}
          </ul>
        </section>
      </div>

      {Object.keys(data.history).length > 0 && (
        <section className="panel px-5 py-6">
          <h2 className="text-lg font-bold text-slate-100">历史趋势</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {Object.entries(data.history).slice(0, 4).map(([cap, pts]) => (
              <div key={cap} className="panel-2 px-3 py-3">
                <p className="text-xs text-slate-400">{capName(capabilities, cap)} · 相对百分位</p>
                <TrendLine
                  series={[{ name: m.display_name, color: '#22d3ee', points: pts.map((p) => ({ date: p.date, value: p.index })) }]}
                  height={200}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">全部基准成绩（来源原始分）</h2>
        <p className="mt-1 text-xs text-slate-500">点击任一分数查看完整溯源：来源、验证状态、文件内定位、数据年龄与原始出处。</p>
        <div className="mt-3 overflow-x-auto">
          <table className="data-table w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-slate-500/15 text-slate-400">
                <th className="px-3 py-2 text-left">能力</th>
                <th className="px-3 py-2 text-left">基准</th>
                <th className="px-3 py-2 text-left">来源原始榜排名</th>
                <th className="px-3 py-2 text-left">来源原始分</th>
                <th className="px-3 py-2 text-left">类型</th>
                <th className="px-3 py-2 text-left">来源</th>
                <th className="px-3 py-2 text-left">评测运行日</th>
                <th className="px-3 py-2 text-left">榜单快照</th>
              </tr>
            </thead>
            <tbody>
              {data.records.map((r, i) => (
                <tr key={`${r.benchmark_id}-${i}`} className="border-b border-slate-500/10 hover:bg-slate-500/5">
                  <td className="px-3 py-2 text-slate-300">{capShort(capabilities, r.capability)}</td>
                  <td className="px-3 py-2 text-slate-200">{r.benchmark_name}</td>
                  <td className="px-3 py-2"><RankCell rank={r.rank} tie={r.tie} /></td>
                  <td className="px-3 py-2">
                    <button className="num rounded px-2 py-0.5 font-semibold text-cyan-300 hover:bg-cyan-400/10" onClick={() => setPicked(r)}>
                      {fmtScore(r.score, r.score_unit)}
                    </button>
                  </td>
                  <td className="px-3 py-2"><TypeBadge type={r.evaluation_target_type} /></td>
                  <td className="px-3 py-2"><LevelBadge level={r.source_level} /></td>
                  <td className="px-3 py-2"><span className="num text-slate-400">{fmtDate(r.evaluation_date)}</span></td>
                  <td className="px-3 py-2"><span className="num text-slate-400">{fmtDate(r.upstream_updated_at)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.records.length === 0 && <p className="mt-4 text-sm text-slate-500">暂无成绩记录</p>}
      </section>

      {lineage && (lineage.previous || lineage.next) && (
        <section className="panel px-5 py-5">
          <h2 className="text-sm font-bold text-slate-100">
            家族演进{lineage.family ? ` · ${lineage.family}` : ''}
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
            {lineage.previous ? (
              <Link to={`/model/${lineage.previous.model_id}`} className="panel-2 px-3 py-2 text-slate-300 hover:text-cyan-300">
                ← 前代 {lineage.previous.display_name}
                <span className="num ml-1 text-[10px] text-slate-500">{lineage.previous.release_date}</span>
              </Link>
            ) : <span className="text-xs text-slate-600">（无更早的同族记录）</span>}
            {lineage.next ? (
              <Link to={`/model/${lineage.next.model_id}`} className="panel-2 px-3 py-2 text-slate-300 hover:text-cyan-300">
                后代 {lineage.next.display_name}
                <span className="num ml-1 text-[10px] text-slate-500">{lineage.next.release_date}</span> →
              </Link>
            ) : <span className="text-xs text-slate-600">（无更新的同族记录）</span>}
          </div>
        </section>
      )}

      <section className="panel px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">已知限制</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-400">
          {m.open_weights === false && <li>闭源 API 模型：评测结果依赖厂商端点的稳定性与版本管理。</li>}
          {m.open_weights === true && <li>开放权重模型：不同部署/量化方式可能产生与官方评测不同的结果。</li>}
          <li>雷达图中的百分位是"相对位置"：参与计算的模型集合变化时数值会变化，不代表能力绝对值。</li>
          {!data.radar.length && <li>当前该模型没有通过质量门槛的能力百分位；请以下方来源原始分为准。</li>}
          <li>软件工程成绩（如有）属于「模型 + Agent 框架」系统表现，不能当作基础模型纯能力。</li>
          <li>评测运行日、榜单快照与本站抓取时间含义不同；来源未公开运行日时显示 —，不会拿版本日期代替。</li>
        </ul>
      </section>

      <SourceDrawer row={picked} onClose={() => setPicked(null)} />
    </div>
  );
}
