import { useParams, Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { useJson } from '@/lib/api';
import type { ModelDetail, OfficialRow } from '@/types/data';
import { ModelRadar, type RadarSeries } from '@/charts/ModelRadar';
import { TrendLine } from '@/charts/TrendLine';
import { CAPABILITIES } from '@/lib/capabilities';
import { fmtContext, fmtDate, fmtScore } from '@/lib/format';
import { LevelBadge, TypeBadge, RankCell, SourceDrawer, OpenWeightBadge } from '@/components/Badges';
import { EmptyState, ErrorState, Skeleton } from '@/components/StateViews';
import { useState } from 'react';

export function ModelDetailPage() {
  const { modelId = '' } = useParams();
  const { data, error, loading } = useJson<ModelDetail>(`/data/models/${modelId}.json`);
  const [picked, setPicked] = useState<OfficialRow | null>(null);

  if (loading) return <Skeleton rows={8} />;
  if (error) return <ErrorState error={error} hint="该模型可能尚未被任何数据源收录，或未映射到注册表。" />;
  if (!data) return <EmptyState title="未找到模型" />;

  const m = data.meta;
  const indicators = data.radar.map((r) => ({ name: r.name, max: 100 }));
  const series: RadarSeries[] = [
    {
      name: m.display_name,
      color: '#22d3ee',
      values: data.radar.map((r) => r.index),
    },
  ];
  const radarCaps = new Set(data.radar.map((r) => r.capability_id));

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
                综合指数 <span className="num text-lg font-bold text-cyan-300">{m.overall_index.toFixed(1)}</span>
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
          <p className="mt-1 text-xs text-slate-500">能力指数（0~100）为本站基于官方原始分的确定性计算。</p>
          {data.radar.length ? (
            <ModelRadar indicators={indicators} series={series} height={360} />
          ) : (
            <p className="py-10 text-center text-sm text-slate-500">该模型暂无足够数据绘制雷达图</p>
          )}
        </section>

        <section className="panel px-5 py-6">
          <h2 className="text-lg font-bold text-slate-100">各项排名</h2>
          <ul className="mt-3 divide-y divide-slate-500/10">
            {data.radar.map((r) => (
              <li key={r.capability_id} className="flex items-center gap-3 py-2.5 text-sm">
                <Link to={`/leaderboard?cap=${r.capability_id}`} className="min-w-0 flex-1 truncate text-slate-200 hover:text-cyan-300">
                  {CAPABILITIES.find((c) => c.id === r.capability_id)?.name ?? r.name}
                </Link>
                <span className="num text-slate-400">{r.index.toFixed(1)}</span>
                <RankCell rank={r.rank} />
              </li>
            ))}
            {data.radar.length === 0 && <li className="py-6 text-sm text-slate-500">暂无能力指数</li>}
          </ul>
        </section>
      </div>

      {/* 历史趋势 */}
      {Object.keys(data.history).length > 0 && (
        <section className="panel px-5 py-6">
          <h2 className="text-lg font-bold text-slate-100">历史趋势</h2>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            {Object.entries(data.history).slice(0, 4).map(([cap, pts]) => (
              <div key={cap} className="panel-2 px-3 py-3">
                <p className="text-xs text-slate-400">{CAPABILITIES.find((c) => c.id === cap)?.name ?? cap} · 指数</p>
                <TrendLine
                  series={[{ name: m.display_name, color: '#22d3ee', points: pts.map((p) => ({ date: p.date, value: p.index })) }]}
                  height={200}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 每条成绩 + 溯源 */}
      <section className="panel px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">全部基准成绩</h2>
        <p className="mt-1 text-xs text-slate-500">点击任一分数查看完整数据溯源（来源、版本、评测条件与原始出处链接）。</p>
        <div className="mt-3 overflow-x-auto">
          <table className="data-table w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-slate-500/15 text-slate-400">
                <th className="px-3 py-2 text-left">能力</th>
                <th className="px-3 py-2 text-left">基准</th>
                <th className="px-3 py-2 text-left">排名</th>
                <th className="px-3 py-2 text-left">分数</th>
                <th className="px-3 py-2 text-left">类型</th>
                <th className="px-3 py-2 text-left">来源</th>
                <th className="px-3 py-2 text-left">评测日期</th>
              </tr>
            </thead>
            <tbody>
              {data.records.map((r, i) => (
                <tr key={`${r.benchmark_id}-${i}`} className="border-b border-slate-500/10 hover:bg-slate-500/5">
                  <td className="px-3 py-2 text-slate-300">{CAPABILITIES.find((c) => c.id === r.capability)?.short ?? r.capability}</td>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!radarCaps.size && data.records.length === 0 && <p className="mt-4 text-sm text-slate-500">暂无成绩记录</p>}
      </section>

      {/* 已知限制 */}
      <section className="panel px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">已知限制</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-400">
          {m.open_weights === false && <li>闭源 API 模型：评测结果依赖厂商端点的稳定性与版本管理。</li>}
          {m.open_weights === true && <li>开放权重模型：不同部署/量化方式可能产生与官方评测不同的结果。</li>}
          <li>能力指数基于当前可用基准的百分位计算，基准覆盖不全时会低估真实能力差距。</li>
          {!radarCaps.has('chat_preference') && <li>人类偏好维度暂无可信公开数据源，本页雷达图未包含。</li>}
          <li>分数反映评测时点表现；模型端点可能已更新，请以来源页评测日期为准。</li>
        </ul>
      </section>

      <SourceDrawer row={picked} onClose={() => setPicked(null)} />
    </div>
  );
}
