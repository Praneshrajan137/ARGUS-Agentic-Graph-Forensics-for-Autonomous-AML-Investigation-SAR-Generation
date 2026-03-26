import { motion } from 'framer-motion';
import { Network, FileText, AlertTriangle, Shield, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import StatCard from '@/components/shared/StatCard';
import { StatCardSkeleton } from '@/components/shared/Skeleton';
import ErrorCard from '@/components/shared/ErrorCard';
import TypologyBadge from '@/components/shared/TypologyBadge';
import GlowCard from '@/components/shared/GlowCard';
import { useQuery } from '@/hooks/useQuery';
import { getGraphStats, getHealth, getAgentHealth } from '@/api/client';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

function HeroBanner() {
  return (
    <GlowCard className="p-6 border-l-4 border-accent mb-8">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center flex-shrink-0 shadow-md">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-display text-4xl text-text-0 tracking-tight leading-none">ARGUS</h1>
            <p className="font-mono text-[11px] tracking-widest uppercase text-accent/70 mt-1.5">
              Agentic Graph Forensics for Autonomous AML Investigation &amp; SAR Generation
            </p>
            <p className="text-sm text-text-2 mt-2">
              Autonomous financial crime detection powered by graph intelligence
            </p>
          </div>
        </div>
        <Link
          to="/graph"
          className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover transition-colors shadow-sm flex-shrink-0"
        >
          Explore Graph <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </GlowCard>
  );
}

export default function Dashboard() {
  const { data: health, loading: healthLoading } = useQuery('health', getHealth);
  const { data: agentHealth } = useQuery('agent-health', getAgentHealth);
  const { data: stats, loading: statsLoading, error, refetch } = useQuery(
    'graph-stats', getGraphStats, { enabled: health?.graph_loaded }
  );

  if (healthLoading || (health?.graph_loaded && statsLoading)) {
    return (
      <div>
        <HeroBanner />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <HeroBanner />
        <ErrorCard error={error} onRetry={refetch} />
      </div>
    );
  }

  if (!health?.graph_loaded) {
    return (
      <div>
        <HeroBanner />
        <GlowCard className="p-12 text-center">
          <div className="animate-pulse text-text-2">
            <p className="font-display text-xl text-text-1 mb-2">Generating Financial World...</p>
            <p className="text-sm">The backend is constructing a synthetic financial network.</p>
          </div>
        </GlowCard>
      </div>
    );
  }

  return (
    <div>
      <HeroBanner />

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-8">
        {/* Stat Cards Row */}
        <motion.div variants={fadeUp} className="grid grid-cols-4 gap-4">
          <StatCard label="Total Nodes" value={stats?.node_count || 0} icon={Network} color="accent" />
          <StatCard label="Total Edges" value={stats?.edge_count || 0} icon={Network} color="cyan" />
          <StatCard label="Graph Density" value={(stats?.density || 0) * 100} icon={Shield} color="emerald" decimals={2} suffix="%" />
          <StatCard label="Avg Degree" value={stats?.avg_degree || 0} icon={AlertTriangle} color="amber" decimals={2} />
        </motion.div>

        {/* Agent Status */}
        {agentHealth && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-4">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className={`w-2.5 h-2.5 rounded-full ${
                    agentHealth.status === 'healthy' ? 'bg-emerald-400' : 'bg-rose-400'
                  }`} />
                  <span className="text-sm font-semibold text-text-0">Purple Agent</span>
                </div>
                <span className="font-mono text-xs text-text-3">
                  Tracer v{agentHealth.version} | {agentHealth.mode} mode
                </span>
                {agentHealth.graph_loaded && (
                  <span className="font-mono text-xs text-text-3 ml-auto">
                    {agentHealth.node_count} nodes · {agentHealth.edge_count} edges
                  </span>
                )}
              </div>
            </GlowCard>
          </motion.div>
        )}

        {/* Crime Intelligence */}
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6">
            <h2 className="font-display text-xl text-text-0 mb-4">Crime Intelligence</h2>
            <div className="grid grid-cols-2 gap-4">
              {(stats?.crime_summary || []).map((crime, i) => (
                <div
                  key={i}
                  className="p-4 rounded-lg border border-surface-3 bg-surface-1"
                >
                  <div className="flex items-center justify-between mb-3">
                    <TypologyBadge typology={crime.crime_type?.toUpperCase()} />
                    <span className="font-mono text-xs text-text-3">
                      {crime.node_count} nodes · {crime.edge_count} edges
                    </span>
                  </div>
                  {crime.metadata?.mule_id != null && (
                    <p className="text-sm text-text-2">
                      Mule: <span className="font-mono font-medium" style={{ color: 'var(--rose-base)' }}>{crime.metadata.mule_id}</span>
                    </p>
                  )}
                  {crime.metadata?.total_amount != null && (
                    <p className="text-sm text-text-2">
                      Total: <span className="font-mono font-medium text-text-0">${crime.metadata.total_amount}</span>
                    </p>
                  )}
                  {crime.metadata?.source_node != null && (
                    <p className="text-sm text-text-2">
                      Source: <span className="font-mono font-medium" style={{ color: 'var(--rose-base)' }}>{crime.metadata.source_node}</span>
                      {crime.metadata?.dest_node != null && <> → <span className="font-mono font-medium" style={{ color: 'var(--rose-base)' }}>{crime.metadata.dest_node}</span></>}
                    </p>
                  )}
                  {crime.metadata?.initial_amount != null && (
                    <p className="text-sm text-text-2">
                      Amount: <span className="font-mono font-medium text-text-0">${crime.metadata.initial_amount}</span>
                    </p>
                  )}
                  {crime.metadata?.chain_length != null && (
                    <p className="text-sm text-text-2">
                      Chain: <span className="font-mono font-medium text-text-0">{crime.metadata.chain_length} hops</span>
                    </p>
                  )}
                </div>
              ))}
            </div>
          </GlowCard>
        </motion.div>

        {/* Quick Actions */}
        <motion.div variants={fadeUp} className="grid grid-cols-3 gap-4">
          {[
            { to: '/graph', icon: Network, label: 'Explore Graph', desc: 'Visualize financial network' },
            { to: '/investigate?subject_id=0', icon: AlertTriangle, label: 'Investigate Mule', desc: 'Run detection on node 0' },
            { to: '/evidence', icon: FileText, label: 'Browse Evidence', desc: 'Review documents and artifacts' },
          ].map(({ to, icon: Icon, label, desc }) => (
            <Link key={to} to={to}>
              <GlowCard accent className="p-5 group cursor-pointer">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-accent-tint flex items-center justify-center group-hover:bg-accent transition-all">
                    <Icon className="w-5 h-5 text-accent group-hover:text-white transition-colors" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-text-0 group-hover:text-accent transition-colors">{label}</p>
                    <p className="text-xs text-text-3">{desc}</p>
                  </div>
                </div>
              </GlowCard>
            </Link>
          ))}
        </motion.div>
      </motion.div>
    </div>
  );
}
