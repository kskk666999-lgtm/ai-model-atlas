import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Inbox, ServerCrash } from 'lucide-react';

export function Skeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="加载中">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-10 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="panel flex flex-col items-center gap-3 px-6 py-14 text-center">
      <Inbox size={36} className="text-slate-500" aria-hidden />
      <p className="text-lg font-medium text-slate-200">{title}</p>
      {hint && <p className="max-w-md text-sm text-slate-400">{hint}</p>}
    </div>
  );
}

export function ErrorState({ error, hint }: { error: string; hint?: string }) {
  return (
    <div className="panel flex flex-col items-center gap-3 px-6 py-14 text-center" role="alert">
      <ServerCrash size={36} className="text-rose-400" aria-hidden />
      <p className="text-lg font-medium text-slate-200">数据加载失败</p>
      <p className="num text-xs text-slate-400">{error}</p>
      {hint && <p className="max-w-md text-sm text-slate-400">{hint}</p>}
    </div>
  );
}

/** 生产环境无数据 / 数据未生成的明确提示（不展示任何模拟榜单）。 */
export function NoDataState({ detail }: { detail?: string }) {
  return (
    <div className="panel flex flex-col items-center gap-4 px-6 py-16 text-center" role="alert">
      <AlertTriangle size={40} className="text-amber-300" aria-hidden />
      <p className="text-xl font-semibold text-slate-100">暂无已验证数据</p>
      <p className="max-w-xl text-sm leading-6 text-slate-400">
        本站从不展示模拟分数。看起来数据流水线还没有成功运行过。
        {detail ? `（${detail}）` : ''}
      </p>
      <div className="panel-2 max-w-xl px-5 py-4 text-left text-sm leading-7 text-slate-300">
        <p className="font-semibold text-slate-200">重新更新数据的两种方式：</p>
        <p>1. 本地运行 PowerShell 脚本：</p>
        <pre className="num mt-1 overflow-x-auto rounded bg-black/40 p-2 text-xs text-cyan-200">{'powershell -ExecutionPolicy Bypass -File scripts/update-data.ps1'}</pre>
        <p>2. 到 GitHub 仓库的 Actions 页签，选择 <span className="num">update-data</span> 工作流，点击 <span className="num">Run workflow</span>。</p>
      </div>
      <Link to="/sources" className="text-sm text-cyan-300 hover:text-cyan-200">查看数据来源与健康状态 →</Link>
    </div>
  );
}

export function useToggle(initial = false) {
  const [on, setOn] = useState(initial);
  return [on, () => setOn((v) => !v), setOn] as const;
}
