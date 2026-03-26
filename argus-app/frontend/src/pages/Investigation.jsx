import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import InvestigationForm from '@/components/investigation/InvestigationForm';
import PipelineTracker from '@/components/investigation/PipelineTracker';
import InvestigationResults from '@/components/investigation/InvestigationResults';
import { runInvestigation, getInvestigationProgress, getInvestigation } from '@/api/client';
import { useToast } from '@/contexts/ToastContext';

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

/* eslint-disable no-console */
const logger_warn = (...args) => console.warn('[Investigation]', ...args);

/** Max polling duration before giving up (5 minutes) */
const MAX_POLL_MS = 5 * 60 * 1000;

/** Polling interval (2 seconds) */
const POLL_INTERVAL_MS = 2000;

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
 * Maps progress endpoint steps to PipelineTracker state.
 * Converts 'running' → 'active' for the pulsing animation.
 */
function stepsToState(steps) {
  const state = {};
  for (const step of steps || []) {
    state[step.name] = step.status === 'running' ? 'active' : step.status;
  }
  // Fill in any missing steps as pending
  for (const name of STEP_NAMES) {
    if (!state[name]) state[name] = 'pending';
  }
  return state;
}

/**
 * Updates pipeline state from the final API response.
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
 * Orchestrates: InvestigationForm → PipelineTracker (live polling) → InvestigationResults
 * Uses fire-and-poll: POST returns instantly, frontend polls progress endpoint.
 */
export default function Investigation() {
  const [searchParams] = useSearchParams();
  const { addToast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pipelineState, setPipelineState] = useState({});
  const [stepDetails, setStepDetails] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);
  const pollStartRef = useRef(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  /**
   * Poll the progress endpoint for real-time step updates.
   * Stops when status is COMPLETE or FAILED, then fetches the full result.
   */
  const startPolling = useCallback((caseId) => {
    pollStartRef.current = Date.now();

    pollRef.current = setInterval(async () => {
      // Safety timeout: stop polling after 5 minutes
      if (Date.now() - pollStartRef.current > MAX_POLL_MS) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setError('Investigation timed out — check SAR Viewer for results');
        setIsSubmitting(false);
        addToast('Investigation polling timed out', 'warning');
        return;
      }

      try {
        const progress = await getInvestigationProgress(caseId);

        // Update pipeline state from real step data
        setPipelineState(stepsToState(progress.steps));
        setStepDetails(
          (progress.steps || []).reduce((acc, s) => ({ ...acc, [s.name]: s }), {})
        );

        // Terminal state: fetch full result
        if (progress.status === 'COMPLETE' || progress.status === 'FAILED') {
          clearInterval(pollRef.current);
          pollRef.current = null;

          try {
            const fullResult = await getInvestigation(caseId);
            setResult(fullResult);
            setPipelineState(updatePipelineFromResult(fullResult));
            setStepDetails(
              (fullResult.steps || []).reduce((acc, s) => ({ ...acc, [s.name]: s }), {})
            );

            if (fullResult.status === 'COMPLETE') {
              addToast(`Investigation complete — case ${caseId}`, 'success');
            } else {
              setError(fullResult.error || 'Investigation failed');
              addToast(`Investigation failed: ${fullResult.error || 'unknown error'}`, 'error');
            }
          } catch (fetchErr) {
            setError(fetchErr.message || 'Failed to fetch investigation result');
            addToast(`Failed to fetch result: ${fetchErr.message}`, 'error');
          }

          setIsSubmitting(false);
        }
      } catch (pollErr) {
        // Polling error — don't stop, backend might be temporarily busy
        logger_warn('Poll error:', pollErr.message);
      }
    }, POLL_INTERVAL_MS);
  }, [addToast]);

  const handleSubmit = useCallback(
    async (formData) => {
      setIsSubmitting(true);
      setResult(null);
      setError(null);
      setPipelineState(createInitialPipelineState());
      setStepDetails({});

      try {
        // Fire: POST returns immediately with case_id + PENDING
        const response = await runInvestigation({
          subject_id: formData.subject_id,
          hop_depth: formData.hop_depth,
          jurisdiction: formData.jurisdiction,
          case_id: formData.case_id,
        });

        const caseId = response.case_id;

        // If backend already completed (fast investigation), use result directly
        if (response.status === 'COMPLETE' || response.status === 'FAILED') {
          setResult(response);
          setPipelineState(updatePipelineFromResult(response));
          setStepDetails(
            (response.steps || []).reduce((acc, s) => ({ ...acc, [s.name]: s }), {})
          );
          if (response.status === 'COMPLETE') {
            addToast(`Investigation complete — case ${caseId}`, 'success');
          } else {
            setError(response.error || 'Investigation failed');
            addToast(`Investigation failed: ${response.error || 'unknown'}`, 'error');
          }
          setIsSubmitting(false);
          return;
        }

        // Poll: start polling for real-time progress
        startPolling(caseId);
      } catch (err) {
        setError(err.message || 'Investigation failed to launch');
        setResult({ status: 'FAILED', error: err.message });
        addToast(`Investigation failed: ${err.message}`, 'error');
        setIsSubmitting(false);
      }
    },
    [startPolling, addToast]
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
                stepDetails={stepDetails}
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

        {/* SAR Mode & Validation Details */}
        {result && result.sar_mode && result.sar_mode !== 'none' && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <h3 className="text-sm font-semibold text-text-0 mb-4 uppercase tracking-wider">
                SAR Generation Details
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-surface-1 rounded-lg">
                  <span className="text-xs text-text-3 block mb-1">SAR Mode</span>
                  <span className={`font-mono text-sm font-bold ${
                    result.sar_mode === 'llm' ? 'text-emerald-400' : 'text-amber-400'
                  }`}>
                    {result.sar_mode === 'llm' ? 'LLM (GPT-4.1)' : 'Mechanical Template'}
                  </span>
                </div>
                <div className="p-3 bg-surface-1 rounded-lg">
                  <span className="text-xs text-text-3 block mb-1">Retry Count</span>
                  <span className="font-mono text-sm font-bold text-text-0">
                    {result.retry_count || 0}
                  </span>
                </div>
                <div className="p-3 bg-surface-1 rounded-lg">
                  <span className="text-xs text-text-3 block mb-1">Confidence</span>
                  <span className="font-mono text-sm font-bold text-text-0">
                    {((result.confidence_score || 0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              {result.validation_errors && result.validation_errors.length > 0 && (
                <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/20 rounded-lg border border-rose-200 dark:border-rose-800">
                  <span className="text-xs font-semibold text-rose-600 dark:text-rose-400 block mb-2">
                    Validation Issues ({result.validation_errors.length})
                  </span>
                  <ul className="space-y-1">
                    {result.validation_errors.map((err, i) => (
                      <li key={i} className="text-xs font-mono text-rose-700 dark:text-rose-300">
                        {typeof err === 'string' ? err : err.message || JSON.stringify(err)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </GlowCard>
          </motion.div>
        )}

        {/* Results: visible after completion */}
        {result && result.status !== 'IN_PROGRESS' && result.status !== 'PENDING' && result.status !== 'FAILED' && (
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
