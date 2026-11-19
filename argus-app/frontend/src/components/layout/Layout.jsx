import { useState } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Network, Search, FileText,
  FolderOpen, BarChart3, Zap, Eye, Settings, ChevronLeft,
  ChevronRight, Shield, Upload, LogOut,
} from 'lucide-react';
import { useQuery } from '@/hooks/useQuery';
import { getHealth, getProdReady } from '@/api/client';
import { useHotkeys } from '@/hooks/useHotkeys';
import { useAuth } from '@/contexts/AuthContext';
import KeyboardShortcutsModal from '@/components/shared/KeyboardShortcutsModal';

const RESEARCH_NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/graph', label: 'Graph Explorer', icon: Network },
  { path: '/investigate', label: 'Investigate', icon: Search },
  { path: '/sar', label: 'Draft Viewer', icon: FileText },
  { path: '/evidence', label: 'Evidence', icon: FolderOpen },
  { path: '/assessment', label: 'Assessment', icon: BarChart3 },
  { path: '/benchmark', label: 'Benchmark', icon: Zap },
  { path: '/vision', label: 'Vision', icon: Eye },
  { path: '/settings', label: 'Settings', icon: Settings },
];

const PRODUCTION_NAV_ITEMS = [
  { path: '/import', label: 'Import & Reconcile', icon: Upload },
  { path: '/cases', label: 'Case Queue', icon: FolderOpen },
];

const MOBILE_RESEARCH_NAV = [
  { path: '/', label: 'Home', icon: LayoutDashboard },
  { path: '/graph', label: 'Graph', icon: Network },
  { path: '/investigate', label: 'Investigate', icon: Search },
  { path: '/sar', label: 'Drafts', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];

const MOBILE_PRODUCTION_NAV = [
  { path: '/import', label: 'Import', icon: Upload },
  { path: '/cases', label: 'Cases', icon: FolderOpen },
];

function Sidebar({ collapsed, onToggle }) {
  const { mode, user, signOut } = useAuth();
  const isProd = mode === 'production';
  const navItems = isProd ? PRODUCTION_NAV_ITEMS : RESEARCH_NAV_ITEMS;

  const { data: health } = useQuery('health', getHealth, { staleTime: 10000, enabled: !isProd });
  const { data: ready } = useQuery('prod-ready', getProdReady, { staleTime: 10000, enabled: isProd });

  return (
    <div data-sidebar="desktop" className="fixed top-0 left-0 h-screen z-40 transition-all duration-300 ease-out" style={{ width: collapsed ? 72 : 260 }}>
      <aside className="h-full bg-surface-0 border-r border-surface-3 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-surface-3">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center flex-shrink-0">
              <Shield className="w-4 h-4 text-white" aria-hidden="true" />
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="font-display text-lg text-text-0 tracking-tight leading-none">ARGUS</span>
                <span className="text-[10px] font-mono text-text-3 tracking-widest uppercase">
                  {isProd ? 'Investigation Workbench' : 'Research Runtime'}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav aria-label="Primary navigation" className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {navItems.map(({ path, label, icon: Icon }) => (
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
              <Icon className="w-[18px] h-[18px] flex-shrink-0" aria-hidden="true" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Footer — User identity / Health status */}
        <div className="p-4 border-t border-surface-3 space-y-2">
          {isProd && user && !collapsed && (
            <div className="flex items-center justify-between gap-2 pb-2 border-b border-surface-2">
              <div className="min-w-0">
                <div className="text-xs font-semibold text-text-0 truncate">{user.display_name}</div>
                <div className="text-[10px] font-mono text-text-3 truncate">{(user.roles || []).join(', ')}</div>
              </div>
              <button
                type="button"
                onClick={signOut}
                title="Sign out"
                aria-label="Sign out"
                className="p-1.5 rounded-btn border border-surface-3 hover:bg-surface-1 text-text-2"
              >
                <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            </div>
          )}
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                (isProd ? ready?.status === 'ready' : health?.graph_loaded)
                  ? 'bg-emerald-500'
                  : 'bg-amber-500'
              }`}
            />
            {!collapsed && (
              <span className="text-xs font-mono text-text-3">
                {isProd
                  ? `DB ${ready?.status || '...'} · ${ready?.schema_revision || ''}`
                  : `v${health?.unified_version || '...'} · ${health?.node_count || 0} nodes`}
              </span>
            )}
          </div>
        </div>
      </aside>

      <button
        type="button"
        onClick={onToggle}
        className="absolute -right-3.5 top-20 w-7 h-7 rounded-full bg-surface-0 border border-surface-3 shadow-sm flex items-center justify-center text-text-3 hover:text-text-1 hover:bg-surface-1 hover:shadow-md transition-all cursor-pointer z-50"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronLeft className="w-3.5 h-3.5" aria-hidden="true" />}
      </button>
    </div>
  );
}

function MobileBottomNav() {
  const { mode } = useAuth();
  const items = mode === 'production' ? MOBILE_PRODUCTION_NAV : MOBILE_RESEARCH_NAV;
  return (
    <nav aria-label="Mobile navigation" className="mobile-bottom-nav fixed bottom-0 left-0 right-0 bg-surface-0 border-t border-surface-3 z-40 items-center justify-around py-2 safe-area-bottom">
      {items.map(({ path, label, icon: Icon }) => (
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
          <Icon className="w-5 h-5" aria-hidden="true" />
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
  const { mode } = useAuth();

  useHotkeys(
    mode === 'production'
      ? [
          { key: '?', handler: () => setShortcutsOpen((v) => !v) },
          { key: 'Escape', handler: () => setShortcutsOpen(false) },
          { key: '1', handler: () => navigate('/import') },
          { key: '2', handler: () => navigate('/cases') },
        ]
      : [
          { key: '?', handler: () => setShortcutsOpen((v) => !v) },
          { key: 'Escape', handler: () => setShortcutsOpen(false) },
          { key: '1', handler: () => navigate('/') },
          { key: '2', handler: () => navigate('/graph') },
          { key: '3', handler: () => navigate('/investigate') },
          { key: '4', handler: () => navigate('/sar') },
          { key: '5', handler: () => navigate('/evidence') },
          { key: '6', handler: () => navigate('/assessment') },
          { key: '7', handler: () => navigate('/benchmark') },
          { key: '8', handler: () => navigate('/vision') },
          { key: '9', handler: () => navigate('/settings') },
        ]
  );

  return (
    <div className="min-h-screen">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main
        id="main-content"
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
              transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
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
