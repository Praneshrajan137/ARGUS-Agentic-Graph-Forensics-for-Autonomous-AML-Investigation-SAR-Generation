// src/components/shared/AnimatedNumber.jsx
import { useEffect } from 'react';
import { motion, useSpring, useTransform, useMotionValue } from 'framer-motion';

/**
 * Spring-physics animated number countup.
 *
 * @param {{ value: number, decimals?: number, prefix?: string, suffix?: string, className?: string }} props
 *   value:    target number to animate to
 *   decimals: decimal places to display (default 0)
 *   prefix:   text before number (e.g. "$")
 *   suffix:   text after number (e.g. "%")
 *   className: optional CSS classes for the <span>
 */
export function AnimatedNumber({ value, decimals = 0, prefix = '', suffix = '', className = '' }) {
  const motionVal = useMotionValue(0);
  const spring = useSpring(motionVal, { stiffness: 100, damping: 30 });
  const display = useTransform(spring, (v) =>
    `${prefix}${v.toFixed(decimals)}${suffix}`
  );

  useEffect(() => {
    motionVal.set(typeof value === 'number' && !isNaN(value) ? value : 0);
  }, [value, motionVal]);

  return <motion.span className={className}>{display}</motion.span>;
}
