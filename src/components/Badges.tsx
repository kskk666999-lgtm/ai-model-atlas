import { Link } from 'react-router-dom';
import { ExternalLink, X } from 'lucide-react';
import { evalTargetLabel, fmtDate, fmtScore, sourceLevelBadge } from '@/lib/format';
import type { OfficialRow } from '@/types/data';

export function TypeBadge({ type }: { type: string }) {
  const { text, kind } = evalTargetLabel(type);
  const cls =
    kind === 'agent'
      ? 'border-violet-400/40 bg-violet-400/10 text-violet-200'
      : kind === 'base'
        ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-200'
        : 'border-slate-400/30 bg-slate-400/10 text-slate-300';
  return <span className={`badge ${cls}`}>{text}</span>;
}

export function LevelBadge({ level }: { level: string }) {
  const { text, cls } = sourceLevelBadge(level);
  return <span className={`badge ${cls}`}>{text}</span>;
}

export function OpenWeightBadge({ open }: { open: boolean | null }) {
  if (open === null) return null;
  return open ? (
    <span className="badge border-emerald-400/40 bg-emerald-400/10 text-emerald-200">开放权重</span>
  ) : (
    <span className="badge">闭源 API</span>
  );
}

export function RankCell({ rank, tie }: { rank: number | null | undefined; tie?: boolean }) {
  if (rank === null || rank === undefined) return <span className="text-faint">—</span>;
  const medal = rank === 1 ? 'rank-medal-1' : rank === 2 ? 'rank-medal-2' : rank === 3 ? 'rank-medal-3' : '';
  return (
    <span className={`num font-semibold ${medal}`}>
      {rank}
      {tie && <span className="ml-1 text-[10px] font-normal text-amber-300/80" title="与其他模型分数并列，差异可能不显著">并列</span>}
    </span>
  );
}

/** 数据溯源抽屉：点击任一分数后展示该成绩的完整来源信息。 */
export function SourceDrawer({ row, onClose }: { row: OfficialRow | null; onClose: () => void }) {
  if (!row) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="数据溯源">
      <button className="absolute inset-0 bg-black/60" onClick={onClose} aria-label="关闭溯源抽屉" />
      <div className="absolute inset-y-0 right-0 w-full max-w-md overflow-y-auto border-l border-slate-500/20 bg-[#0b111f] p-5 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs text-slate-400">数据溯源 · Data Provenance</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-100">{row.benchmark_name}</h3>
          </div>
          <button className="rounded-lg border border-slate-500/30 p-1.5 text-slate-400 hover:text-slate-100" onClick={onClose} aria-label="关闭">
            <X size={16} />
          </button>
        </div>

        <div className="panel-2 mb-4 px-4 py-3">
          <p className="num text-2xl font-bold text-cyan-300">
            {fmtScore(row.score, row.score_unit)}
            <span className="ml-2 text-xs font-normal text-slate-400">{row.score_unit}</span>
          </p>
          <p className="mt-1 text-sm text-slate-300">
            {row.model_is_unmapped ? (row.raw_model_name || row.model_id) : row.model_id}
            {' · '}排名 {row.rank ?? '—'}
          </p>
        </div>

        <dl className="space-y-2.5 text-sm">
          <Field label="数据来源">{row.source_name}</Field>
          <Field label="来源等级"><LevelBadge level={row.source_level} /></Field>
          <Field label="评测目标类型"><TypeBadge type={row.evaluation_target_type} /></Field>
          {row.agent_scaffold && <Field label="Agent 框架">{row.agent_scaffold}</Field>}
          {row.prompt_mode && <Field label="推理/提交模式">{row.prompt_mode}</Field>}
          {row.benchmark_version && <Field label="基准版本">{row.benchmark_version}</Field>}
          <Field label="评测日期">{fmtDate(row.evaluation_date)}</Field>
          {row.sample_size !== null && row.sample_size !== undefined && (
            <Field label="样本量">{row.sample_size}</Field>
          )}
          <Field label="抓取时间">{fmtDate(row.fetched_at)}</Field>
          <Field label="模型原始名称（来源侧）">{row.raw_model_name || row.model_id}</Field>
          {row.model_is_unmapped && (
            <Field label="映射状态">
              <span className="text-amber-300">未映射：尚未建立到注册表的别名，仅出现在官方原始榜</span>
            </Field>
          )}
          {row.notes && <Field label="备注">{row.notes}</Field>}
          {row.source_url && (
            <Field label="原始出处">
              <a
                className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200"
                href={row.source_url}
                target="_blank"
                rel="noreferrer"
              >
                查看原始数据 <ExternalLink size={13} />
              </a>
            </Field>
          )}
        </dl>

        <div className="mt-5 flex gap-3">
          {!row.model_is_unmapped && (
            <Link
              to={`/model/${row.model_id}`}
              className="rounded-lg border border-cyan-400/40 bg-cyan-400/10 px-3 py-1.5 text-sm text-cyan-200 hover:bg-cyan-400/20"
            >
              模型详情页
            </Link>
          )}
          <Link
            to="/methodology"
            className="rounded-lg border border-slate-500/30 px-3 py-1.5 text-sm text-slate-300 hover:text-slate-100"
          >
            数据来源等级说明
          </Link>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-slate-500/10 pb-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-slate-200">{children}</dd>
    </div>
  );
}
