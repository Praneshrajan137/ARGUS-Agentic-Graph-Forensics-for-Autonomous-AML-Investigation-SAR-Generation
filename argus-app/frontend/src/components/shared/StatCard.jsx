import { motion } from 'framer-motion';
import { AnimatedNumber } from '@/components/shared/AnimatedNumber';

export default function StatCard({ label, value, icon: Icon, color = 'accent', decimals = 0, prefix = '', suffix = '', subtitle }) {
  const colorMap = {
    accent: { bg: 'var(--accent-tint)', icon: 'var(--accent-base)' },
    amber: { bg: 'var(--amber-tint)', icon: 'var(--amber-base)' },
    violet: { bg: 'var(--violet-tint)', icon: 'var(--violet-base)' },
    rose: { bg: 'var(--rose-tint)', icon: 'var(--rose-base)' },
    emerald: { bg: 'var(--emerald-tint)', icon: 'var(--emerald-base)' },
    cyan: { bg: 'var(--cyan-tint)', icon: 'var(--cyan-base)' },
  };
  const c = colorMap[color] || colorMap.accent;

  return (
    <motion.div
      whileHover={{ scale: 1.005, boxShadow: 'var(--shadow-md)' }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className="bg-surface-0 rounded-card border border-surface-3 shadow-sm p-6 flex items-start gap-4"
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: c.bg }}
      >
        {Icon && <Icon className="w-5 h-5" style={{ color: c.icon }} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-2 mb-1">{label}</p>
        <AnimatedNumber
          value={value}
          decimals={decimals}
          prefix={prefix}
          suffix={suffix}
          className="font-mono font-bold text-2xl text-text-0 tabular-nums"
        />
        {subtitle && <p className="text-xs text-text-3 mt-1">{subtitle}</p>}
      </div>
    </motion.div>
  );
}
