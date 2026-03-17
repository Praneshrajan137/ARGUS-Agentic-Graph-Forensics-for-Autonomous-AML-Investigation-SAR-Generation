// src/components/shared/AnimatedNumber.jsx
import { useEffect } from 'react';
import { motion, useSpring, useTransform, useMotionValue } from 'framer-motion';

/**
 * Spring-physics animated number countup.
 * @param {{ value: number, duration?: number }} props
 */
export function AnimatedNumber({ value, duration = 800 }) {
  const motionVal = useMotionValue(0);
  const spring = useSpring(motionVal, { stiffness: 100, damping: 30 });
  const display = useTransform(spring, (v) => Math.round(v));

  useEffect(() => {
    motionVal.set(value);
  }, [value, motionVal]);

  return <motion.span>{display}</motion.span>;
}
