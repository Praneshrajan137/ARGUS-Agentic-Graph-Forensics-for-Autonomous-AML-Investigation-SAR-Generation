import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import InvestigationForm from '@/components/investigation/InvestigationForm';
import PipelineTracker from '@/components/investigation/PipelineTracker';
import InvestigationResults from '@/components/investigation/InvestigationResults';
import { runInvestigation } from '@/api/client';

/** Page-level stagger animation */
const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

/**
 * The 8 pipeline step names in execution order.
 * Used for Approach B animated simulation during the synchronous API call.
 */
const STEP_NAMES = [
  'receive',
  'analyze',
  'detect',
  'synthesize',
  'compute',
  'draft',
  'validate',
  'submit',
];

/**
 * Creates the initial pipeline state — all steps pending.
 */
function createInitialPipelineState() {
  const state = {};
  for (const name of STEP_NAMES) {
    state[name] = 'pending';
  }
  return state;
}

/**
 * Updates pipeline state from the real API response.
 * Maps step names to their actual status and marks post-failure steps as skipped.
 */
function updatePipelineFromResult(result) {
  const newState = {};

  // Map steps from result
  for (const step of result.steps || []) {
    newState[step.name] = step.status === 'running' ? 'complete' : step.status;
  }

  // Steps after a failed step → 'skipped'
  let failed = false;
  for (const name of STEP_NAMES) {
    if (failed && !newState[name]) {
      newState[name] = 'skipped';
    }
    if (newState[name] === 'failed') {
      failed = true;
    }
    // Default remaining to 'complete' if result is successful and step is missing
    if (!newState[name] && result.status === 'COMPLETE') {
      newState[name] = 'complete';
    }
  }

  return newState;
}

/**
 * /investigate page — the operational core of ARGUS.
 *
 * Orchestrates: InvestigationForm → PipelineTracker (animated) → InvestigationResults
 * Uses Approach B: synchronous POST with animated pipeline simulation.
 */
export default function Investigation() {
  const [searchParams] = useSearchParams();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pipelineState, setPipelineState] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  /**
   * Approach B: Animated pipeline simulation during synchronous fetch.
   * Advances steps sequentially every 400ms. Real result snaps to truth.
   */
  const startPipelineAnimation = useCallback(() => {
    let currentIdx = 0;
    intervalRef.current = setInterval(() => {
      if (currentIdx >= STEP_NAMES.length) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        return;
      }
      setPipelineState((prev) => {
        const updated = { ...prev };
        // Complete previous step
        if (currentIdx > 0) {
          updated[STEP_NAMES[currentIdx - 1]] = 'complete';
        }
        // Activate current step
        updated[STEP_NAMES[currentIdx]] = 'active';
        return updated;
      });
      currentIdx++;
    }, 400);
  }, []);

  const handleSubmit = useCallback(
    async (formData) => {
      setIsSubmitting(true);
      setResult(null);
      setError(null);
      setPipelineState(createInitialPipelineState());

      // Start animation
      startPipelineAnimation();

      try {
        const response = await runInvestigation({
          subject_id: formData.subject_id,
          hop_depth: formData.hop_depth,
          jurisdiction: formData.jurisdiction,
          case_id: formData.case_id,
        });

        // Stop animation and snap to real state
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }

        setResult(response);
        setPipelineState(updatePipelineFromResult(response));
      } catch (err) {
        // Stop animation
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }

        setError(err.message || 'Investigation failed');
        setResult({ status: 'FAILED', error: err.message });

        // Mark current and remaining steps as failed/skipped
        setPipelineState((prev) => {
          const updated = { ...prev };
          let foundActive = false;
          for (const name of STEP_NAMES) {
            if (updated[name] === 'active') {
              updated[name] = 'failed';
              foundActive = true;
            } else if (foundActive && updated[name] === 'pending') {
              updated[name] = 'skipped';
            }
          }
          return updated;
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [startPipelineAnimation]
  );

  const hasStarted = isSubmitting || Object.keys(pipelineState).length > 0;

  return (
    <div>
      <PageHeader
        title="Investigation Console"
        subtitle="Autonomous financial crime investigation pipeline"
      />

      <motion.div
        variants={stagger}
        initial="hidden"
        animate="show"
        className="space-y-6"
      >
        {/* Form */}
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6">
            <InvestigationForm
              prefillSubjectId={searchParams.get('subject_id')}
              isSubmitting={isSubmitting}
              onSubmit={handleSubmit}
            />
          </GlowCard>
        </motion.div>

        {/* Pipeline Tracker: visible once investigation started */}
        {hasStarted && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <h3 className="text-sm font-semibold text-text-0 mb-4 uppercase tracking-wider">
                Pipeline Status
              </h3>
              <PipelineTracker
                stepStates={pipelineState}
                stepDetails={
                  result?.steps?.reduce(
                    (acc, s) => ({ ...acc, [s.name]: s }),
                    {}
                  ) || {}
                }
              />
            </GlowCard>
          </motion.div>
        )}

        {/* Error display */}
        {error && !result?.sar_narrative && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <div
                className="flex items-center gap-2 text-sm font-medium"
                style={{ color: 'var(--rose-base)' }}
              >
                <span>⚠ Investigation Error:</span>
                <span className="font-mono">{error}</span>
              </div>
            </GlowCard>
          </motion.div>
        )}

        {/* Results: visible after completion */}
        {result && result.status !== 'IN_PROGRESS' && result.status !== 'FAILED' && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <InvestigationResults result={result} />
            </GlowCard>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
