import { Link, NavLink } from 'react-router-dom';
import { BarChart3, GitCompareArrows, Globe2, Home, Menu, ScrollText, Sparkles, X } from 'lucide-react';
import { useState } from 'react';
import { AppThemeProvider } from '@/lib/theme';
import { StatusDot } from '@/components/StatusDot';

const NAV = [
  { to: '/', label: '首页', icon: Home },
  { to: '/leaderboard', label: '能力榜单', icon: BarChart3 },
  { to: '/compare', label: '模型对比', icon: GitCompareArrows },
  { to: '/recommender', label: '场景推荐', icon: Sparkles },
  { to: '/sources', label: '数据来源', icon: Globe2 },
  { to: '/methodology', label: '方法论', icon: ScrollText },
];

export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-slate-500/15 bg-[#05070d]/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-3">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-violet-500 text-sm font-black text-[#05070d]">
            AT
          </span>
          <span className="text-[15px] font-bold tracking-wide text-slate-100">
            AI 模型天梯
            <span className="ml-2 hidden text-[11px] font-normal text-slate-500 sm:inline">AI Model Atlas</span>
          </span>
        </Link>
        <nav className="ml-auto hidden items-center gap-1 md:flex" aria-label="主导航">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  isActive ? 'bg-cyan-400/10 text-cyan-300' : 'text-slate-400 hover:text-slate-100'
                }`
              }
            >
              <n.icon size={15} aria-hidden />
              {n.label}
            </NavLink>
          ))}
        </nav>
        <span className="ml-auto flex items-center gap-2 md:ml-2">
          <StatusDot />
        </span>
        <button
          className="rounded-lg border border-slate-500/30 p-2 text-slate-300 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? '关闭菜单' : '打开菜单'}
        >
          {open ? <X size={17} /> : <Menu size={17} />}
        </button>
      </div>
      {open && (
        <nav className="border-t border-slate-500/15 px-4 py-2 md:hidden" aria-label="移动端导航">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm ${
                  isActive ? 'bg-cyan-400/10 text-cyan-300' : 'text-slate-300'
                }`
              }
            >
              <n.icon size={15} aria-hidden />
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-500/15 px-4 py-8">
      <div className="mx-auto max-w-[1400px] space-y-2 text-xs leading-6 text-slate-500">
        <p>
          AI 模型天梯（AI Model Atlas）—— 纯静态开源项目：数据来自各基准官方结构化结果，排名为确定性计算；
          网站运行与数据更新全程不调用任何生成式大模型 API，不消耗大模型 Token。
        </p>
        <p>
          各基准分数版权归其官方所有，展示时均注明来源与出处链接；综合指数为本站基于官方原始分的确定性计算结果，
          非任何官方榜单。详见 <Link className="text-cyan-400 hover:text-cyan-300" to="/methodology">方法论</Link> 与{' '}
          <Link className="text-cyan-400 hover:text-cyan-300" to="/sources">数据来源</Link>。
        </p>
      </div>
    </footer>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AppThemeProvider>
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6">{children}</main>
        <Footer />
      </div>
    </AppThemeProvider>
  );
}
