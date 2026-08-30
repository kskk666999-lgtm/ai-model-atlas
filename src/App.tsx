import { useEffect } from 'react';
import { Routes, Route, useLocation, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/AppShell';
import { HomePage } from '@/pages/Home';
import { LeaderboardPage } from '@/pages/Leaderboard';
import { ComparePage } from '@/pages/Compare';
import { ModelDetailPage } from '@/pages/ModelDetail';
import { RecommenderPage } from '@/pages/Recommender';
import { SourcesPage } from '@/pages/Sources';
import { MethodologyPage } from '@/pages/Methodology';
import { ModelsPage } from '@/pages/ModelsCatalog';
import { EmptyState } from '@/components/StateViews';

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function NotFound() {
  return (
    <EmptyState
      title="页面不存在"
      hint="检查一下地址，或从导航菜单进入对应页面。"
    />
  );
}

export default function App() {
  return (
    <AppShell>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/leaderboard" element={<LeaderboardPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/model/:modelId" element={<ModelDetailPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/recommender" element={<RecommenderPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/methodology" element={<MethodologyPage />} />
        <Route path="/index.html" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}
