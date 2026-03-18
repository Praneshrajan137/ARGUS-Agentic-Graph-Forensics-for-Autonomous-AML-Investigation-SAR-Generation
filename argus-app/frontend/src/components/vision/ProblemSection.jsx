import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { TrendingDown, AlertOctagon, Clock, ShieldOff } from 'lucide-react';
import GlowCard from '@/components/shared/GlowCard';
import { AnimatedNumber } from '@/components/shared/AnimatedNumber';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] } },
};

const stats = [
  {
    value: 2,
    prefix: '$',
    suffix: 'T+',
    label: 'Laundered globally each year',
    icon: TrendingDown,
    color: 'rose',
  },
  {
    value: 90,
    suffix: '%+',
    label: 'False positive rates in production AML systems',
    icon: AlertOctagon,
    color: 'amber',
  },
  {
    value: 75,
    suffix: '%',
    label: 'Analyst time spent on manual data gathering',
    icon: Clock,
    color: 'violet',
  },
  {
    value: 1,
    prefix: '<',
    suffix: '%',
    label: 'Illicit funds successfully intercepted',
    icon: ShieldOff,
    color: 'rose',
  },
];

const colorMap = {
  rose: { bg: 'var(--rose-tint)', icon: 'var(--rose-base)', border: 'var(--rose-base)' },
  amber: { bg: 'var(--amber-tint)', icon: 'var(--amber-base)', border: 'var(--amber-base)' },
  violet: { bg: 'var(--violet-tint)', icon: 'var(--violet-base)', border: 'var(--violet-base)' },
};

export default function ProblemSection() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });

  return (
    <section ref={ref} className="space-y-6">
      <motion.h2
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="font-display text-2xl sm:text-3xl text-text-0 tracking-tight"
      >
        The Crisis in AML Compliance
      </motion.h2>

      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        {stats.map((stat) => {
          const colors = colorMap[stat.color];
          const Icon = stat.icon;
          return (
            <motion.div key={stat.label} variants={fadeUp}>
              <GlowCard className="p-5 h-full">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                  style={{ backgroundColor: colors.bg }}
                >
                  <Icon className="w-5 h-5" style={{ color: colors.icon }} />
                </div>
                <div className="font-display text-3xl text-text-0 tracking-tight">
                  {inView ? (
                    <AnimatedNumber
                      value={stat.value}
                      prefix={stat.prefix || ''}
                      suffix={stat.suffix || ''}
                    />
                  ) : (
                    <span>{stat.prefix || ''}{stat.value}{stat.suffix || ''}</span>
                  )}
                </div>
                <p className="text-sm text-text-2 mt-1.5 leading-snug">{stat.label}</p>
              </GlowCard>
            </motion.div>
          );
        })}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.4, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
      >
        <GlowCard className="p-6">
          <p className="text-sm text-text-2 leading-relaxed">
            Real financial crime data is locked behind regulatory walls and PII constraints.
            Traditional synthetic data lacks the structural realism of actual money laundering
            networks — the power-law topologies, the temporal clustering, the carefully crafted
            amounts just below reporting thresholds. Compliance teams are left training on
            unrealistic data, producing systems that flag everything and catch nothing.
          </p>
        </GlowCard>
      </motion.div>
    </section>
  );
}
