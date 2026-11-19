import { motion } from 'framer-motion';

export default function GlowCard({ children, className = '', accent = false, ...rest }) {
  return (
    <motion.div
      {...rest}
      whileHover={{ boxShadow: accent ? '0 0 0 1px var(--accent-base), var(--shadow-lg)' : 'var(--shadow-md)' }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className={`bg-surface-0 rounded-card border border-surface-3 shadow-sm ${className}`}
    >
      {children}
    </motion.div>
  );
}
