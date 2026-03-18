import { useState } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Network, Search, FileText,
  FolderOpen, BarChart3, Zap, Settings, ChevronLeft,
  ChevronRight, Shield
} from 'lucide-react';
import { useQuery } from '@/hooks/useQuery';
import { getHealth } from '@/api/client';
import { useHotkeys } from '@/hooks/useHotkeys';
import KeyboardShortcutsModal from '@/components/shared/KeyboardShortcutsModal';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/graph', label: 'Graph Explorer', icon: Network },
  { path: '/investigate', label: 'Investigate', icon: Search },
  { path: '/sar', label: 'SAR Viewer', icon: FileText },
  { path: '/evidence', label: 'Evidence', icon: FolderOpen },
  { path: '/assessment', label: 'Assessment', icon: BarChart3 },
  { path: '/benchmark', label: 'Benchmark', icon: Zap },
  { path: '/settings', label: 'Settings', icon: Settings },
];

const MOBILE_NAV_ITEMS = [
  { path: '/', label: 'Home', icon: LayoutDashboard },
  { path: '/graph', label: 'Graph', icon: Network },
  { path: '/investigate', label: 'Investigate', icon: Search },
  { path: '/sar', label: 'SAR', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];

function Sidebar({ collapsed, onToggle }) {
  const { data: health } = useQuery('health', getHealth, { staleTime: 10000 });

  return (
    <div data-sidebar="desktop" className="fixed top-0 left-0 h-screen z-40 transition-all duration-300 ease-out" style={{ width: collapsed ? 72 : 260 }}>
      <aside
        className="h-full bg-surface-0 border-r border-surface-3 flex flex-col"
      >
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-surface-3">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
              <Shield className="w-4 h-4 text-white" />
            </div>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex flex-col"
              >
                <span className="font-display text-lg text-text-0 tracking-tight leading-none">ARGUS</span>
                <span className="text-[10px] font-mono text-text-3 tracking-widest uppercase">AML Platform</span>
              </motion.div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3 py-2.5 rounded-btn text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-accent-tint text-accent'
                    : 'text-text-2 hover:text-text-0 hover:bg-surface-2'
                }`
              }
            >
              <Icon className="w-[18px] h-[18px] flex-shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Footer — Health status */}
        <div className="p-4 border-t border-surface-3">
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                health?.graph_loaded ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'
              }`}
            />
            {!collapsed && (
              <span className="text-xs font-mono text-text-3">
                v{health?.unified_version || '...'} · {health?.node_count || 0} nodes
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* Collapse toggle — outside aside so it's never clipped */}
      <button
        onClick={onToggle}
        className="absolute -right-3.5 top-20 w-7 h-7 rounded-full bg-surface-0 border border-surface-3 shadow-sm flex items-center justify-center text-text-3 hover:text-text-1 hover:bg-surface-1 hover:shadow-md transition-all cursor-pointer z-50"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}

function MobileBottomNav() {
  return (
    <nav className="mobile-bottom-nav fixed bottom-0 left-0 right-0 bg-surface-0 border-t border-surface-3 z-40 items-center justify-around py-2 safe-area-bottom">
      {MOBILE_NAV_ITEMS.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          end={path === '/'}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center gap-0.5 py-1 text-[10px] font-medium transition-colors ${
              isActive ? 'text-accent' : 'text-text-3'
            }`
          }
        >
          <Icon className="w-5 h-5" />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useHotkeys([
    { key: '?', handler: () => setShortcutsOpen((v) => !v) },
    { key: 'Escape', handler: () => setShortcutsOpen(false) },
    { key: '1', handler: () => navigate('/') },
    { key: '2', handler: () => navigate('/graph') },
    { key: '3', handler: () => navigate('/investigate') },
    { key: '4', handler: () => navigate('/sar') },
    { key: '5', handler: () => navigate('/evidence') },
    { key: '6', handler: () => navigate('/assessment') },
    { key: '7', handler: () => navigate('/benchmark') },
    { key: '8', handler: () => navigate('/settings') },
  ]);

  return (
    <div className="min-h-screen">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main
        data-main-content
        className="transition-all duration-300 ease-out min-h-screen"
        style={{ marginLeft: collapsed ? 72 : 260 }}
      >
        <div className="max-w-[1440px] mx-auto p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
      <MobileBottomNav />
      <KeyboardShortcutsModal isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}
