import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import GlowCard from '@/components/shared/GlowCard';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const visions = [
  {
    lead: 'A Compliance Operating System',
    body: 'ARGUS evolves from a detection tool into the operating system for financial compliance — where every investigation, every SAR, every audit trail flows through a single, intelligent graph. Compliance teams stop reacting to alerts and start operating with full situational awareness.',
  },
  {
    lead: 'A Regulatory Intelligence Network',
    body: 'A shared intelligence fabric connecting financial institutions, regulators, and law enforcement. Federated graph analysis across organizational boundaries without exposing sensitive data — enabling coordinated action against transnational financial crime at scale.',
  },
  {
    lead: 'The Standard for Synthetic AML Data',
    body: 'The authoritative source of realistic, labeled financial crime datasets for the global compliance industry. Training ground for next-generation ML models, benchmark for detection algorithms, and foundation for regulatory technology innovation.',
  },
];

export default function PlatformPotential() {
  return (
    <section>
      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
      >
        <GlowCard className="p-8 border-l-4" style={{ borderLeftColor: 'var(--accent-base)' }}>
          <motion.h2
            variants={fadeUp}
            className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight mb-6"
          >
            What ARGUS Becomes
          </motion.h2>

          <div className="space-y-6">
            {visions.map((v) => (
              <motion.div key={v.lead} variants={fadeUp}>
                <h3 className="text-sm font-semibold text-text-0 mb-1.5">{v.lead}</h3>
                <p className="text-sm text-text-2 leading-relaxed">{v.body}</p>
              </motion.div>
            ))}
          </div>

          <motion.div variants={fadeUp} className="mt-8">
            <Link
              to="/graph"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover transition-colors shadow-sm"
            >
              Explore the Graph <ArrowRight className="w-4 h-4" />
            </Link>
          </motion.div>
        </GlowCard>
      </motion.div>
    </section>
  );
}
