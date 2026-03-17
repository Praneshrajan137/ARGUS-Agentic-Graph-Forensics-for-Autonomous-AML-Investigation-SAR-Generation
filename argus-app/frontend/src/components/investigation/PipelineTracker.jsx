import React from 'react';
import { motion } from 'framer-motion';
import {
  Inbox,
  Microscope,
  Radar,
  FlaskConical,
  Calculator,
  PenTool,
  ShieldCheck,
  Send,
  Check,
  X,
} from 'lucide-react';

/**
 * 8-step investigation pipeline definitions.
 * Each step maps to a backend pipeline stage.
 */
const PIPELINE_STEPS = [
  { key: 'receive', label: 'Receive', icon: Inbox, desc: 'Initialize case' },
  { key: 'analyze', label: 'Analyze', icon: Microscope, desc: 'Build subgraph' },
  { key: 'detect', label: 'Detect', icon: Radar, desc: 'Run heuristics' },
  { key: 'synthesize', label: 'Synthesize', icon: FlaskConical, desc: 'Cross-ref evidence' },
  { key: 'compute', label: 'Compute', icon: Calculator, desc: 'Score confidence' },
  { key: 'draft', label: 'Draft', icon: PenTool, desc: 'Generate SAR' },
  { key: 'validate', label: 'Validate', icon: ShieldCheck, desc: 'Zero hallucination' },
  { key: 'submit', label: 'Submit', icon: Send, desc: 'File report' },
];

/** Framer Motion variants for staggered entrance */
const pipelineStagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.2, delayChildren: 0.1 } },
};

const stepEntrance = {
  hidden: { opacity: 0, scale: 0.8, y: 8 },
  show: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 300, damping: 20 },
  },
};

/** Active step pulsing animation */
const activePulse = {
  scale: [1, 1.05, 1],
  transition: { duration: 1.5, repeat: Infinity, ease: 'easeInOut' },
};

/**
 * Style map for pipeline step states.
 * Each state defines bg class, icon color, and label color.
 */
const STATE_STYLES = {
  pending: {
    bg: 'bg-surface-2',
    iconColor: 'text-text-3',
    labelColor: 'text-text-3',
  },
  active: {
    bg: 'bg-accent',
    iconColor: 'text-white',
    labelColor: 'text-text-0',
  },
  complete: {
    bg: 'bg-emerald-500',
    iconColor: 'text-white',
    labelColor: 'text-text-1',
  },
  failed: {
    bg: 'bg-rose-500',
    iconColor: 'text-white',
    labelColor: 'text-status-rose',
  },
  skipped: {
    bg: 'bg-surface-2 border-2 border-dashed border-surface-3',
    iconColor: 'text-text-3',
    labelColor: 'text-text-3',
  },
  warning: {
    bg: 'bg-amber-500',
    iconColor: 'text-white',
    labelColor: 'text-status-amber',
  },
};

/** Individual pipeline step node */
function PipelineStepNode({ step, index, state, detail, prevComplete }) {
  const styles = STATE_STYLES[state] || STATE_STYLES.pending;
  const Icon = step.icon;

  return (
    <motion.div
      variants={stepEntrance}
      className="flex flex-row md:flex-col items-center relative flex-1 min-w-0 gap-3 md:gap-0"
      data-testid={`pipeline-step-${step.key}`}
      data-state={state}
      role="listitem"
      aria-label={`${step.label}: ${state}`}
      aria-current={state === 'active' ? 'step' : undefined}
    >
      {/* Connector line — horizontal on desktop, vertical on mobile */}
      {index > 0 && (
        <>
          {/* Desktop: horizontal connector */}
          <div className="absolute -left-1/2 top-4 w-full h-0.5 hidden md:block">
            <motion.div
              className="h-full rounded-full"
              style={{
                background: prevComplete
                  ? 'var(--emerald-base)'
                  : 'var(--surface-3)',
              }}
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.3, delay: index * 0.2 }}
            />
          </div>
          {/* Mobile: vertical connector */}
          <div className="absolute left-4 -top-3 w-0.5 h-3 md:hidden">
            <motion.div
              className="w-full h-full rounded-full"
              style={{
                background: prevComplete
                  ? 'var(--emerald-base)'
                  : 'var(--surface-3)',
              }}
              initial={{ scaleY: 0 }}
              animate={{ scaleY: 1 }}
              transition={{ duration: 0.2, delay: index * 0.15 }}
            />
          </div>
        </>
      )}

      {/* Icon circle — smaller on mobile */}
      <div className="relative flex-shrink-0">
        <motion.div
          className={`w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center relative z-10 ${styles.bg}`}
          animate={state === 'active' ? activePulse : {}}
        >
          {state === 'complete' ? (
            <Check className="w-3.5 h-3.5 md:w-4 md:h-4 text-white" />
          ) : state === 'failed' ? (
            <X className="w-3.5 h-3.5 md:w-4 md:h-4 text-white" />
          ) : (
            <Icon className={`w-3.5 h-3.5 md:w-4 md:h-4 ${styles.iconColor}`} />
          )}
        </motion.div>

        {/* Active pulse ring */}
        {state === 'active' && (
          <motion.div
            className="absolute inset-0 rounded-full"
            style={{ border: '2px solid var(--accent-base)' }}
            animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
      </div>

      {/* Label + detail — beside icon on mobile, below on desktop */}
      <div className="flex flex-col md:items-center">
        <span
          className={`md:mt-2 text-xs font-semibold ${styles.labelColor} md:text-center`}
        >
          {step.label}
        </span>

        {/* Detail (visible after completion) */}
        {detail && detail.duration_ms != null && (
          <motion.span
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-0.5 text-[10px] font-mono text-text-3 md:text-center truncate max-w-[80px]"
          >
            {detail.duration_ms}ms
          </motion.span>
        )}
      </div>
    </motion.div>
  );
}

/**
 * Pipeline tracker showing the 8-step investigation pipeline.
 *
 * @param {Object} stepStates  — Map of step key → state string
 * @param {Object} stepDetails — Map of step key → { duration_ms, detail }
 */
export default function PipelineTracker({ stepStates = {}, stepDetails = {} }) {
  return (
    <motion.div
      variants={pipelineStagger}
      initial="hidden"
      animate="show"
      className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 md:gap-2 px-4"
      data-testid="pipeline-tracker"
      role="list"
      aria-label="Investigation pipeline steps"
    >
      {PIPELINE_STEPS.map((step, i) => (
        <PipelineStepNode
          key={step.key}
          step={step}
          index={i}
          state={stepStates[step.key] || 'pending'}
          detail={stepDetails[step.key]}
          prevComplete={
            i > 0 && stepStates[PIPELINE_STEPS[i - 1].key] === 'complete'
          }
        />
      ))}
    </motion.div>
  );
}

/** Exported for testing */
export { PIPELINE_STEPS, STATE_STYLES };
