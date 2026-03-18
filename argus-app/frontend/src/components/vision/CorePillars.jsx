import { motion } from 'framer-motion';
import { ShieldCheck, RefreshCw, Globe, Eye, Network } from 'lucide-react';
import GlowCard from '@/components/shared/GlowCard';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const pillars = [
  {
    icon: ShieldCheck,
    title: 'Zero Hallucination',
    description: 'Every SAR citation validated against the graph. No fabricated entities, amounts, or timestamps.',
    color: 'var(--rose-base)',
    tint: 'var(--rose-tint)',
  },
  {
    icon: RefreshCw,
    title: 'Deterministic Reproducibility',
    description: 'Same seed, same result. PYTHONHASHSEED=0, sorted iteration, seeded LLM — audit-ready output.',
    color: 'var(--accent-base)',
    tint: 'var(--accent-tint)',
  },
  {
    icon: Globe,
    title: 'Dual Jurisdiction',
    description: 'FinCEN (US) and FIU-IND (India) regulatory frameworks. USD and INR, SWIFT and IFSC.',
    color: 'var(--cyan-base)',
    tint: 'var(--cyan-tint)',
  },
  {
    icon: Eye,
    title: 'Transparent Algorithms',
    description: 'Rule-based BFS/DFS detection — not black-box ML. Every decision fully auditable by regulators.',
    color: 'var(--emerald-base)',
    tint: 'var(--emerald-tint)',
  },
  {
    icon: Network,
    title: 'Graph-First Intelligence',
    description: 'Power-law network topology matching real financial systems. Forensic traversal at every scale.',
    color: 'var(--violet-base)',
    tint: 'var(--violet-tint)',
  },
];

export default function CorePillars() {
  return (
    <section className="space-y-6">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight"
      >
        Core Principles
      </motion.h2>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4"
      >
        {pillars.map((pillar) => {
          const Icon = pillar.icon;
          return (
            <motion.div key={pillar.title} variants={fadeUp}>
              <motion.div whileHover={{ y: -4 }} transition={{ type: 'spring', stiffness: 400, damping: 25 }}>
                <GlowCard
                  className="p-5 h-full border-t-4"
                  style={{ borderTopColor: pillar.color }}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                    style={{ backgroundColor: pillar.tint }}
                  >
                    <Icon className="w-5 h-5" style={{ color: pillar.color }} />
                  </div>
                  <h3 className="text-sm font-semibold text-text-0 mb-1.5">{pillar.title}</h3>
                  <p className="text-xs text-text-2 leading-relaxed">{pillar.description}</p>
                </GlowCard>
              </motion.div>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
