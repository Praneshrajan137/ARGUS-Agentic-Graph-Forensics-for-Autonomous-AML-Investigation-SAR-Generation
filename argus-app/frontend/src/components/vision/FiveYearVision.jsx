import { motion } from 'framer-motion';
import GlowCard from '@/components/shared/GlowCard';

const timeline = [
  {
    year: '2025',
    title: 'Foundation',
    color: 'var(--accent-base)',
    tint: 'var(--accent-tint)',
    description: 'Dual-agent architecture with Forge and Tracer. Synthetic scale-free graph generation, autonomous SAR creation, and deterministic reproducibility across FinCEN and FIU-IND jurisdictions.',
    highlights: ['Dual-agent A2A protocol', 'Structuring + Layering detection', 'Zero-hallucination SAR validation'],
  },
  {
    year: '2026',
    title: 'Real-Time Monitoring',
    color: 'var(--cyan-base)',
    tint: 'var(--cyan-tint)',
    description: 'Live transaction stream processing with continuous graph updates. Real-time alerting as suspicious patterns emerge, not just batch-mode investigation after the fact.',
    highlights: ['Stream processing engine', 'Continuous graph updates', 'Instant alert generation'],
  },
  {
    year: '2027',
    title: 'Multi-Typology Expansion',
    color: 'var(--violet-base)',
    tint: 'var(--violet-tint)',
    description: 'Expand beyond structuring and layering to detect trade-based money laundering, cryptocurrency transaction flows, shell company networks, and beneficial ownership obfuscation.',
    highlights: ['Trade-based laundering', 'Cryptocurrency tracing', 'Shell company detection'],
  },
  {
    year: '2028',
    title: 'Cross-Border Intelligence',
    color: 'var(--amber-base)',
    tint: 'var(--amber-tint)',
    description: 'Multi-jurisdiction graph linking for cross-border investigation. Direct regulatory API integration for automated SAR filing. Correspondent banking network analysis.',
    highlights: ['Multi-jurisdiction linking', 'Regulatory API auto-filing', 'Correspondent banking analysis'],
  },
  {
    year: '2029',
    title: 'Global Compliance Platform',
    color: 'var(--emerald-base)',
    tint: 'var(--emerald-tint)',
    description: 'AI-augmented analyst workbench combining autonomous investigation with human oversight. Federated learning across institutions. The industry standard for synthetic AML data and compliance intelligence.',
    highlights: ['AI-augmented analyst workbench', 'Federated institutional learning', 'Industry-standard synthetic data'],
  },
];

export default function FiveYearVision() {
  return (
    <section className="space-y-6">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight"
      >
        Five-Year Vision
      </motion.h2>

      <div className="relative">
        {/* Vertical timeline line — desktop only */}
        <div className="hidden md:block absolute left-[39px] top-4 bottom-4 w-0.5 bg-surface-3" />

        <div className="space-y-6">
          {timeline.map((entry, i) => (
            <motion.div
              key={entry.year}
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{
                duration: 0.5,
                delay: i * 0.1,
                ease: [0.25, 0.46, 0.45, 0.94],
              }}
              className="relative flex gap-6"
            >
              {/* Timeline node — desktop */}
              <div className="hidden md:flex flex-col items-center flex-shrink-0 w-[80px]">
                <div
                  className="w-5 h-5 rounded-full border-[3px] bg-surface-0 z-10 flex-shrink-0"
                  style={{ borderColor: entry.color }}
                />
                <span
                  className="font-mono text-xs font-bold mt-1.5"
                  style={{ color: entry.color }}
                >
                  {entry.year}
                </span>
              </div>

              {/* Content card */}
              <div className="flex-1">
                <GlowCard className="p-5">
                  {/* Mobile year badge */}
                  <div className="md:hidden mb-3">
                    <span
                      className="inline-block px-2.5 py-1 rounded-badge font-mono text-xs font-bold text-white"
                      style={{ backgroundColor: entry.color }}
                    >
                      {entry.year}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="w-2 h-2 rounded-full hidden md:block"
                      style={{ backgroundColor: entry.color }}
                    />
                    <h3 className="text-sm font-semibold text-text-0">{entry.title}</h3>
                  </div>

                  <p className="text-xs text-text-2 leading-relaxed mb-3">{entry.description}</p>

                  <div className="flex flex-wrap gap-1.5">
                    {entry.highlights.map((h) => (
                      <span
                        key={h}
                        className="px-2 py-0.5 rounded-badge text-[10px] font-mono border"
                        style={{
                          borderColor: entry.color,
                          color: entry.color,
                          backgroundColor: entry.tint,
                        }}
                      >
                        {h}
                      </span>
                    ))}
                  </div>
                </GlowCard>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
