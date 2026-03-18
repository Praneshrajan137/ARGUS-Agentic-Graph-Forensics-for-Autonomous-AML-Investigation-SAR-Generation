import { motion } from 'framer-motion';
import { Network, AlertTriangle, Search, Shield, FileText, ArrowRight, Cpu, Crosshair } from 'lucide-react';
import GlowCard from '@/components/shared/GlowCard';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const stages = [
  {
    icon: Network,
    label: 'Generate',
    desc: 'Scale-free graph with Barabási-Albert topology',
    color: 'var(--accent-base)',
    tint: 'var(--accent-tint)',
  },
  {
    icon: AlertTriangle,
    label: 'Inject',
    desc: 'Structuring & layering patterns with ground truth',
    color: 'var(--amber-base)',
    tint: 'var(--amber-tint)',
  },
  {
    icon: Search,
    label: 'Investigate',
    desc: '8-node LangGraph autonomous decision loop',
    color: 'var(--cyan-base)',
    tint: 'var(--cyan-tint)',
  },
  {
    icon: Crosshair,
    label: 'Detect',
    desc: 'BFS for structuring, DFS for layering chains',
    color: 'var(--emerald-base)',
    tint: 'var(--emerald-tint)',
  },
  {
    icon: FileText,
    label: 'Report',
    desc: 'Regulatory-compliant SAR with Five Ws narrative',
    color: 'var(--violet-base)',
    tint: 'var(--violet-tint)',
  },
];

function PipelineArrow() {
  return (
    <div className="hidden md:flex items-center justify-center flex-shrink-0 text-text-3">
      <ArrowRight className="w-4 h-4" />
    </div>
  );
}

export default function HowItWorks() {
  return (
    <section className="space-y-8">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight"
      >
        How ARGUS Works
      </motion.h2>

      {/* Pipeline */}
      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="flex flex-col md:flex-row items-stretch md:items-center gap-3"
      >
        {stages.map((stage, i) => {
          const Icon = stage.icon;
          return (
            <div key={stage.label} className="contents">
              <motion.div variants={fadeUp} className="flex-1">
                <GlowCard className="p-4 h-full text-center">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-2"
                    style={{ backgroundColor: stage.tint }}
                  >
                    <Icon className="w-5 h-5" style={{ color: stage.color }} />
                  </div>
                  <p className="text-sm font-semibold text-text-0">{stage.label}</p>
                  <p className="text-xs text-text-3 mt-1 leading-snug">{stage.desc}</p>
                </GlowCard>
              </motion.div>
              {i < stages.length - 1 && <PipelineArrow />}
            </div>
          );
        })}
      </motion.div>

      {/* Agent Cards */}
      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-2 gap-4"
      >
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6 h-full border-t-4" style={{ borderTopColor: 'var(--accent-base)' }}>
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: 'var(--accent-tint)' }}
              >
                <Cpu className="w-4.5 h-4.5" style={{ color: 'var(--accent-base)' }} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text-0">Forge Agent</h3>
                <span className="font-mono text-[10px] text-text-3 tracking-wider">WORLD SIMULATOR</span>
              </div>
            </div>
            <p className="text-sm text-text-2 leading-relaxed">
              Generates mathematically consistent financial networks with 1,000+ nodes
              using Barabási-Albert scale-free topology. Surgically injects structuring
              and layering crime patterns with ground-truth labels for evaluation.
            </p>
          </GlowCard>
        </motion.div>

        <motion.div variants={fadeUp}>
          <GlowCard className="p-6 h-full border-t-4" style={{ borderTopColor: 'var(--violet-base)' }}>
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: 'var(--violet-tint)' }}
              >
                <Shield className="w-4.5 h-4.5" style={{ color: 'var(--violet-base)' }} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text-0">Tracer Agent</h3>
                <span className="font-mono text-[10px] text-text-3 tracking-wider">AUTONOMOUS INVESTIGATOR</span>
              </div>
            </div>
            <p className="text-sm text-text-2 leading-relaxed">
              Autonomously investigates suspicious entities through an 8-node LangGraph
              decision loop. Performs BFS/DFS graph traversal, synthesizes evidence with
              spaCy NER, and drafts zero-hallucination SAR narratives.
            </p>
          </GlowCard>
        </motion.div>
      </motion.div>

      {/* A2A Protocol connector */}
      <motion.div
        initial={{ opacity: 0, scaleX: 0 }}
        whileInView={{ opacity: 1, scaleX: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="flex items-center justify-center"
      >
        <div className="px-4 py-2 rounded-full border border-surface-3 bg-surface-0 shadow-sm">
          <span className="font-mono text-xs text-text-2 tracking-wider">
            Connected via A2A Protocol &middot; Protocol Buffers
          </span>
        </div>
      </motion.div>
    </section>
  );
}
