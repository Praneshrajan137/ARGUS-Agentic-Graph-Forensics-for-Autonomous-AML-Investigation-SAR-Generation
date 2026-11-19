import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';
import { ToastProvider } from '@/contexts/ToastContext';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import ToastContainer from '@/components/shared/Toast';
import StaleStateGuard from '@/components/shared/StaleStateGuard';
import ScrollToTop from '@/components/shared/ScrollToTop';
import Layout from '@/components/layout/Layout';
import Dashboard from '@/pages/Dashboard';
import GraphExplorer from '@/pages/GraphExplorer';
import Investigation from '@/pages/Investigation';
import SARViewer from '@/pages/SARViewer';
import Evidence from '@/pages/Evidence';
import Assessment from '@/pages/Assessment';
import Benchmark from '@/pages/Benchmark';
import SettingsPage from '@/pages/Settings';
import Vision from '@/pages/Vision';
import ImportReconcile from '@/pages/ImportReconcile';
import CaseQueue from '@/pages/CaseQueue';
import CaseWorkspace from '@/pages/CaseWorkspace';
import NarrativeReview from '@/pages/NarrativeReview';

function AppRoutes() {
  const { mode, loading, user } = useAuth();

  if (mode === 'production') {
    if (loading) {
      return <div className="p-8 text-sm text-text-2">Checking session...</div>;
    }
    if (!user) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-surface-0 border border-surface-3 rounded-card p-8 shadow-md space-y-4">
            <h1 className="font-display text-3xl text-text-0">ARGUS Workbench</h1>
            <p className="text-sm text-text-2">
              Sign in through your institution&apos;s identity provider (OIDC Authorization Code + PKCE) to access
              imports, assigned cases, and review packages.
            </p>
            <a
              href="/api/auth/login"
              className="w-full inline-flex items-center justify-center px-4 py-2.5 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover"
            >
              Sign In with Institutional OIDC
            </a>
          </div>
        </div>
      );
    }

    return (
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/cases" replace />} />
          <Route path="/import" element={<ImportReconcile />} />
          <Route path="/cases" element={<CaseQueue />} />
          <Route path="/cases/:caseId" element={<CaseWorkspace />} />
          <Route path="/cases/:caseId/review" element={<NarrativeReview />} />
          <Route path="*" element={<Navigate to="/cases" replace />} />
        </Route>
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/graph" element={<GraphExplorer />} />
        <Route path="/investigate" element={<Investigation />} />
        <Route path="/sar" element={<SARViewer />} />
        <Route path="/evidence" element={<Evidence />} />
        <Route path="/assessment" element={<Assessment />} />
        <Route path="/benchmark" element={<Benchmark />} />
        <Route path="/vision" element={<Vision />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/import" element={<ImportReconcile />} />
        <Route path="/cases" element={<CaseQueue />} />
        <Route path="/cases/:caseId" element={<CaseWorkspace />} />
        <Route path="/cases/:caseId/review" element={<NarrativeReview />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <a href="#main-content" className="skip-link">Skip to main content</a>
            <ScrollToTop />
            <StaleStateGuard />
            <AppRoutes />
          </BrowserRouter>
          <ToastContainer />
        </AuthProvider>
      </ToastProvider>
    </MotionConfig>
  );
}
