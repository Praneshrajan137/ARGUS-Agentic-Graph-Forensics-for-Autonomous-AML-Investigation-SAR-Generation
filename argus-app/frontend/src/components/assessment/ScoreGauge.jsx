import { useEffect } from 'react';
import { motion, useSpring, useTransform, useMotionValue } from 'framer-motion';

const CIRCUMFERENCE = 2 * Math.PI * 80;

/**
 * Maps a percentage score to the appropriate design-system color variable.
 * @param {number} pct - Score as percentage (0–100)
 * @returns {string} CSS custom property
 */
function scoreColor(pct) {
  if (pct >= 80) return 'var(--accent-base)';
  if (pct >= 60) return 'var(--emerald-base)';
  if (pct >= 30) return 'var(--amber-base)';
  return 'var(--rose-base)';
}

/**
 * SVG circular gauge — analytical centerpiece of the Assessment page.
 *
 * @param {{ score: number, label?: string }} props
 *   score: 0.0–1.0 (fraction)
 *   label: text below the number (default "OVERALL")
 */
export default function ScoreGauge({ score, label = 'OVERALL' }) {
  const pct = Math.round(score * 100);
  const color = scoreColor(pct);
  const offset = CIRCUMFERENCE * (1 - pct / 100);

  // Animated number countup
  const motionVal = useMotionValue(0);
  const spring = useSpring(motionVal, { stiffness: 60, damping: 20 });
  const display = useTransform(spring, (v) => Math.round(v));

  useEffect(() => {
    motionVal.set(pct);
  }, [pct, motionVal]);

  return (
    <div className="flex flex-col items-center" data-testid="score-gauge">
      <svg
        width="200"
        height="200"
        viewBox="0 0 200 200"
        className="-rotate-90"
      >
        {/* Background ring */}
        <circle
          cx="100"
          cy="100"
          r="80"
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth="12"
          strokeOpacity="0.3"
        />
        {/* Score ring */}
        <motion.circle
          cx="100"
          cy="100"
          r="80"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          initial={{ strokeDashoffset: CIRCUMFERENCE }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      {/* Center text (positioned absolutely over SVG) */}
      <div
        className="absolute flex flex-col items-center"
        style={{ marginTop: '60px' }}
      >
        <motion.span
          className="font-display text-5xl font-normal tabular-nums leading-none"
          style={{ color }}
        >
          {display}
        </motion.span>
        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-text-2 mt-1">
          {label}
        </span>
      </div>
    </div>
  );
}
