import { motion } from 'framer-motion';
import GlowCard from '@/components/shared/GlowCard';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const technologies = [
  {
    label: 'LangGraph 8-Node Loop',
    description: 'Autonomous decision-making through a state machine with conditional edges — receive, analyze, detect, synthesize, compute, draft, validate, submit.',
    color: 'var(--cyan-base)',
  },
  {
    label: 'BFS + DFS Traversal',
    description: 'Breadth-first search for fan-in structuring detection. Iterative depth-first search for layering chain discovery with decay analysis.',
    color: 'var(--violet-base)',
  },
  {
    label: 'Protocol Buffers (A2A)',
    description: 'Type-safe inter-agent communication with 80% size reduction over JSON. Seven message types defining the complete investigation protocol.',
    color: 'var(--accent-base)',
  },
  {
    label: 'spaCy NER Pipeline',
    description: 'Named entity recognition for evidence synthesis — extracting persons, organizations, amounts, and financial identifiers from unstructured text.',
    color: 'var(--emerald-base)',
  },
  {
    label: 'GPT-4.1 + Mechanical Fallback',
    description: 'LLM-powered Five Ws SAR narrative generation at temperature 0.0 with seed 42. Deterministic template fallback if validation fails three times.',
    color: 'var(--amber-base)',
  },
  {
    label: 'Barabási-Albert Graphs',
    description: 'Scale-free network topology with power-law degree distribution — matching the structure of real-world financial transaction networks.',
    color: 'var(--rose-base)',
  },
];

export default function TechShowcase() {
  return (
    <section className="space-y-6">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight"
      >
        The Technology
      </motion.h2>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        {technologies.map((tech) => (
          <motion.div key={tech.label} variants={fadeUp}>
            <GlowCard
              className="p-5 h-full border-l-4"
              style={{ borderLeftColor: tech.color }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: tech.color }}
                />
                <h3 className="font-mono text-sm font-semibold text-text-0">{tech.label}</h3>
              </div>
              <p className="text-xs text-text-2 leading-relaxed">{tech.description}</p>
            </GlowCard>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
