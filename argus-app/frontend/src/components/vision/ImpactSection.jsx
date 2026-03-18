import { motion } from 'framer-motion';
import { Users, Landmark, Building2, CheckCircle2 } from 'lucide-react';
import GlowCard from '@/components/shared/GlowCard';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const audiences = [
  {
    icon: Users,
    title: 'For Compliance Teams',
    color: 'var(--accent-base)',
    tint: 'var(--accent-tint)',
    points: [
      'Reduce manual investigation time by automating graph traversal and evidence synthesis',
      'Eliminate false positive fatigue with precision-targeted typology detection',
      'Generate audit-ready SARs with validated citations and Five Ws narratives',
      'Train on realistic synthetic data without PII exposure risk',
    ],
  },
  {
    icon: Landmark,
    title: 'For Regulators',
    color: 'var(--cyan-base)',
    tint: 'var(--cyan-tint)',
    points: [
      'Standardized SAR quality through deterministic, reproducible investigation',
      'Transparent rule-based algorithms that can be audited and understood',
      'Dual-jurisdiction support for cross-border regulatory coordination',
      'Zero-hallucination guarantee — every claim traceable to source data',
    ],
  },
  {
    icon: Building2,
    title: 'For Financial Institutions',
    color: 'var(--emerald-base)',
    tint: 'var(--emerald-tint)',
    points: [
      'Reduce compliance costs with autonomous investigation pipelines',
      'Scale AML operations without proportional headcount growth',
      'Achieve regulatory confidence through reproducible, defensible results',
      'Future-proof compliance with an extensible multi-typology platform',
    ],
  },
];

const metrics = [
  { value: '8-Step', label: 'Autonomous Decision Loop' },
  { value: '2', label: 'Regulatory Jurisdictions' },
  { value: 'Zero', label: 'Hallucination Tolerance' },
];

export default function ImpactSection() {
  return (
    <section className="space-y-6">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight"
      >
        Impact &amp; Value
      </motion.h2>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        {audiences.map((audience) => {
          const Icon = audience.icon;
          return (
            <motion.div key={audience.title} variants={fadeUp}>
              <GlowCard className="p-6 h-full">
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{ backgroundColor: audience.tint }}
                  >
                    <Icon className="w-5 h-5" style={{ color: audience.color }} />
                  </div>
                  <h3 className="text-sm font-semibold text-text-0">{audience.title}</h3>
                </div>
                <ul className="space-y-2.5">
                  {audience.points.map((point, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle2
                        className="w-4 h-4 flex-shrink-0 mt-0.5"
                        style={{ color: audience.color }}
                      />
                      <span className="text-xs text-text-2 leading-relaxed">{point}</span>
                    </li>
                  ))}
                </ul>
              </GlowCard>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Metric bar */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
      >
        <GlowCard className="p-5">
          <div className="flex flex-col sm:flex-row items-center justify-around gap-4 sm:gap-0 sm:divide-x divide-surface-3">
            {metrics.map((metric) => (
              <div key={metric.label} className="text-center px-6">
                <p className="font-display text-2xl text-text-0 tracking-tight">{metric.value}</p>
                <p className="text-xs text-text-3 mt-0.5 font-mono tracking-wider uppercase">{metric.label}</p>
              </div>
            ))}
          </div>
        </GlowCard>
      </motion.div>
    </section>
  );
}
