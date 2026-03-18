import { motion } from 'framer-motion';
import { Shield } from 'lucide-react';

const nodePositions = [
  { cx: 80, cy: 40, r: 6, color: 'var(--accent-base)', delay: 0 },
  { cx: 160, cy: 25, r: 5, color: 'var(--amber-base)', delay: 0.15 },
  { cx: 220, cy: 65, r: 7, color: 'var(--violet-base)', delay: 0.3 },
  { cx: 140, cy: 80, r: 5, color: 'var(--rose-base)', delay: 0.45 },
  { cx: 40, cy: 75, r: 4, color: 'var(--emerald-base)', delay: 0.6 },
  { cx: 260, cy: 30, r: 4, color: 'var(--cyan-base)', delay: 0.75 },
];

const edges = [
  { x1: 80, y1: 40, x2: 160, y2: 25, delay: 0.3 },
  { x1: 160, y1: 25, x2: 220, y2: 65, delay: 0.5 },
  { x1: 220, y1: 65, x2: 140, y2: 80, delay: 0.7 },
  { x1: 140, y1: 80, x2: 80, y2: 40, delay: 0.9 },
  { x1: 80, y1: 40, x2: 40, y2: 75, delay: 1.0 },
  { x1: 160, y1: 25, x2: 260, y2: 30, delay: 1.1 },
  { x1: 220, y1: 65, x2: 260, y2: 30, delay: 1.2 },
];

export default function VisionHero() {
  return (
    <div className="relative overflow-hidden rounded-card mb-12">
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          background: `radial-gradient(ellipse at 30% 50%, var(--accent-base), transparent 70%),
                       radial-gradient(ellipse at 70% 50%, var(--violet-base), transparent 70%)`,
        }}
      />

      <div className="relative px-8 py-16 sm:py-20 lg:py-24">
        <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-16">
          <div className="flex-1 text-center lg:text-left">
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, type: 'spring', stiffness: 200, damping: 20 }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-surface-3 bg-surface-0/80 mb-6"
            >
              <Shield className="w-4 h-4" style={{ color: 'var(--accent-base)' }} />
              <span className="font-mono text-[10px] tracking-widest uppercase" style={{ color: 'var(--accent-base)' }}>
                ARGUS Platform
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="font-display text-4xl sm:text-5xl lg:text-6xl text-text-0 tracking-tight leading-[1.1]"
            >
              The Future of Financial Crime Investigation
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="mt-5 text-base sm:text-lg text-text-2 max-w-xl mx-auto lg:mx-0 leading-relaxed"
            >
              Autonomous graph forensics that transforms how the world detects,
              investigates, and reports financial crime — with zero hallucinations
              and full regulatory compliance.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.55 }}
              className="mt-8 flex flex-wrap gap-3 justify-center lg:justify-start"
            >
              <span className="px-3 py-1 rounded-badge text-xs font-mono border border-surface-3 text-text-2 bg-surface-0/60">
                Dual-Agent Architecture
              </span>
              <span className="px-3 py-1 rounded-badge text-xs font-mono border border-surface-3 text-text-2 bg-surface-0/60">
                Graph Intelligence
              </span>
              <span className="px-3 py-1 rounded-badge text-xs font-mono border border-surface-3 text-text-2 bg-surface-0/60">
                Zero Hallucination
              </span>
            </motion.div>
          </div>

          {/* Animated mini-graph */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="flex-shrink-0 hidden sm:block"
          >
            <svg width="300" height="110" viewBox="0 0 300 110" fill="none">
              {edges.map((edge, i) => (
                <motion.line
                  key={i}
                  x1={edge.x1}
                  y1={edge.y1}
                  x2={edge.x2}
                  y2={edge.y2}
                  stroke="var(--surface-3)"
                  strokeWidth="1.5"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 0.6 }}
                  transition={{ duration: 0.8, delay: edge.delay, ease: 'easeInOut' }}
                />
              ))}
              {nodePositions.map((node, i) => (
                <motion.circle
                  key={i}
                  cx={node.cx}
                  cy={node.cy}
                  r={node.r}
                  fill={node.color}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ duration: 0.4, delay: node.delay, type: 'spring', stiffness: 300, damping: 15 }}
                />
              ))}
            </svg>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
