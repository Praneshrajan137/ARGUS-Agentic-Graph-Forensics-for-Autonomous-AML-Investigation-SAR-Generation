import { motion } from 'framer-motion';

export default function ConfidenceBar({ score, showLabel = true }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? 'var(--emerald-base)' : pct >= 50 ? 'var(--amber-base)' : 'var(--rose-base)';

  return (
    <div className="flex items-center gap-3">
      {showLabel && (
        <span className="font-mono text-sm font-bold tabular-nums" style={{ color }}>
          {pct}%
        </span>
      )}
      <div className="flex-1 h-2 bg-surface-2 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  );
}
