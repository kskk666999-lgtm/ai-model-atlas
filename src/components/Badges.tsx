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
  // 数据年龄：评测日期 → 抓取日期的天数差（"今天抓取"不等于"今天评测"）
  const dataAgeDays = (() => {
    if (!row.evaluation_date || !row.fetched_at) return null;
    const a = new Date(row.evaluation_date).getTime();
    const b = new Date(row.fetched_at).getTime();
    if (Number.isNaN(a) || Number.isNaN(b)) return null;
    return Math.max(0, Math.round((b - a) / 86_400_000));
  })();
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
          <Field label="记录验证状态"><VerificationBadge status={row.record_verification_status} /></Field>
          <Field label="评测目标类型"><TypeBadge type={row.evaluation_target_type} /></Field>
          {row.agent_scaffold && <Field label="Agent 框架">{row.agent_scaffold}</Field>}
          {row.prompt_mode && <Field label="推理/提交模式">{row.prompt_mode}</Field>}
          {row.benchmark_version && <Field label="基准版本">{row.benchmark_version}</Field>}
          <Field label="评测日期">
            {fmtDate(row.evaluation_date)}
            {dataAgeDays !== null && (
              <span className="ml-1.5 text-[10px] text-slate-500">（数据年龄约 {dataAgeDays} 天）</span>
            )}
          </Field>
          {row.sample_size !== null && row.sample_size !== undefined && (
            <Field label="样本量">{row.sample_size}</Field>
          )}
          <Field label="本站抓取时间">{fmtDate(row.fetched_at)}</Field>
          {row.upstream_updated_at && <Field label="上游数据更新时间">{row.upstream_updated_at}</Field>}
          <Field label="模型原始名称（来源侧）">{row.raw_model_name || row.model_id}</Field>
          {row.model_is_unmapped && (
            <Field label="映射状态">
              <span className="text-amber-300">未映射：尚未建立到注册表的别名，仅出现在官方原始榜</span>
            </Field>
          )}
          {row.data_file_url && (
            <Field label="精确数据文件">
              <a
                className="inline-flex items-center gap-1 break-all text-cyan-300 hover:text-cyan-200"
                href={row.data_file_url}
                target="_blank"
                rel="noreferrer"
              >
                {row.data_file_url.length > 60 ? row.data_file_url.slice(0, 60) + '…' : row.data_file_url}
                <ExternalLink size={13} />
              </a>
            </Field>
          )}
          {row.data_json_path && <Field label="文件内定位">{row.data_json_path}</Field>}
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

export function VerificationBadge({ status }: { status?: string }) {
  if (status === 'maintainer_verified') {
    return <span className="badge border-emerald-400/40 bg-emerald-400/10 text-emerald-200">官方核验</span>;
  }
  if (status === 'third_party_submitted') {
    return (
      <span className="badge border-amber-400/40 bg-amber-400/10 text-amber-200">
        第三方提交（不进入严格榜）
      </span>
    );
  }
  if (status === 'unknown') {
    return <span className="badge border-slate-400/30 text-slate-400">验证状态未知</span>;
  }
  return <span className="badge">官方核验</span>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-slate-500/10 pb-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-slate-200">{children}</dd>
    </div>
  );
}
