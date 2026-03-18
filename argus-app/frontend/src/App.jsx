import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ToastProvider } from '@/contexts/ToastContext';
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

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <ScrollToTop />
        <StaleStateGuard />
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/graph" element={<GraphExplorer />} />
            <Route path="/investigate" element={<Investigation />} />
            <Route path="/sar" element={<SARViewer />} />
            <Route path="/evidence" element={<Evidence />} />
            <Route path="/assessment" element={<Assessment />} />
            <Route path="/benchmark" element={<Benchmark />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <ToastContainer />
    </ToastProvider>
  );
}
