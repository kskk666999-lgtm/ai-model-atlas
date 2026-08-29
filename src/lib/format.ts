import type { OfficialRow } from '@/types/data';

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${fmtDate(iso)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function fmtScore(score: number | null | undefined, unit?: string): string {
  if (score === null || score === undefined) return '—';
  if (unit === 'usd_per_mtok') {
    return score >= 1 ? `$${score.toFixed(2)}` : `$${score.toFixed(3)}`;
  }
  if (unit === 'ndcg_0_1' || unit === 'spearman_0_1' || unit === 'map_0_1') {
    return score.toFixed(4);
  }
  if (unit === 'tokens_per_second') return `${score.toFixed(1)} tok/s`;
  if (unit === 'seconds') return `${score.toFixed(2)} s`;
  if (Number.isInteger(score)) return String(score);
  return score.toFixed(1);
}

export function fmtContext(ctx: number | null | undefined): string {
  if (!ctx) return '—';
  if (ctx >= 1_000_000) return `${(ctx / 1_000_000).toFixed(ctx % 1_000_000 === 0 ? 0 : 1)}M`;
  if (ctx >= 1000) return `${Math.round(ctx / 1000)}K`;
  return String(ctx);
}

export function evalTargetLabel(t: string): { text: string; kind: 'base' | 'agent' | 'other' } {
  switch (t) {
    case 'base_model':
      return { text: '基础模型', kind: 'base' };
    case 'api_endpoint':
      return { text: 'API 端点', kind: 'base' };
    case 'model_variant':
      return { text: '模型变体', kind: 'base' };
    case 'model_plus_agent':
      return { text: '模型+Agent', kind: 'agent' };
    case 'complete_agent_system':
      return { text: 'Agent 系统', kind: 'agent' };
    case 'embedding_model':
      return { text: 'Embedding', kind: 'other' };
    case 'reranker':
      return { text: 'Reranker', kind: 'other' };
    default:
      return { text: '其他', kind: 'other' };
  }
}

export function confidenceLabel(c: 'high' | 'medium' | 'low' | undefined): string {
  return c === 'high' ? '高' : c === 'low' ? '低' : c === 'medium' ? '中' : '—';
}

export function sourceLevelBadge(level: string): { text: string; cls: string } {
  switch (level) {
    case 'A':
      return { text: 'A 级·官方结构化', cls: 'text-emerald-300 border-emerald-400/30 bg-emerald-400/10' };
    case 'B':
      return { text: 'B 级·官方导出', cls: 'text-sky-300 border-sky-400/30 bg-sky-400/10' };
    case 'C':
      return { text: 'C 级·第三方', cls: 'text-amber-300 border-amber-400/30 bg-amber-400/10' };
    case 'D':
      return { text: 'D 级·自报', cls: 'text-rose-300 border-rose-400/30 bg-rose-400/10' };
    default:
      return { text: level, cls: '' };
  }
}

export function isChineseModel(m: { region?: string | null; provider?: string | null }): boolean {
  return m.region === 'cn';
}

export function displayNameOf(row: OfficialRow): string {
  return row.raw_model_name || row.model_id;
}

export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number): (...args: A) => void {
  let t: ReturnType<typeof setTimeout> | undefined;
  return (...args: A) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
