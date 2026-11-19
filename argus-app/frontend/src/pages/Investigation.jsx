import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import InvestigationForm from '@/components/investigation/InvestigationForm';
import PipelineTracker from '@/components/investigation/PipelineTracker';
import InvestigationResults from '@/components/investigation/InvestigationResults';
import { runInvestigation, getInvestigationProgress, getInvestigation } from '@/api/client';
import { usePolling } from '@/hooks/usePolling';
import { useToast } from '@/contexts/ToastContext';

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

const STEP_NAMES = ['receive', 'analyze', 'detect', 'synthesize', 'compute', 'draft', 'validate', 'submit'];

function createInitialPipelineState() {
  return Object.fromEntries(STEP_NAMES.map((name) => [name, 'pending']));
}

function stepsToState(steps) {
  const state = createInitialPipelineState();
  for (const step of steps || []) {
    state[step.name] = step.status === 'running' ? 'active' : step.status;
  }
  return state;
}

function updatePipelineFromResult(result) {
  const newState = {};
  for (const step of result.steps || []) {
    newState[step.name] = step.status === 'running' ? 'complete' : step.status;
  }
  let failed = false;
  for (const name of STEP_NAMES) {
    if (failed && !newState[name]) newState[name] = 'skipped';
    if (newState[name] === 'failed') failed = true;
    if (!newState[name] && result.status === 'COMPLETE') newState[name] = 'complete';
  }
  return newState;
}

/**
 * Research runtime /investigate page — uses URL-driven ?case_id= resume and
 * abortable non-overlapping exponential backoff polling.
 */
export default function Investigation() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();
  const [activeCaseId, setActiveCaseId] = useState(() => searchParams.get('case_id') || null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pipelineState, setPipelineState] = useState({});
  const [stepDetails, setStepDetails] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Sync URL ?case_id= on reload/navigation
  useEffect(() => {
    const cid = searchParams.get('case_id');
    if (cid && cid !== activeCaseId) {
      setActiveCaseId(cid);
    }
  }, [searchParams, activeCaseId]);

  const { networkWarning, polling } = usePolling(
    (opts) => getInvestigationProgress(activeCaseId, opts),
    {
      enabled: Boolean(activeCaseId) && (!result || result.case_id !== activeCaseId),
      isTerminal: (p) => p?.status === 'COMPLETE' || p?.status === 'FAILED',
      onData: (progress) => {
        setPipelineState(stepsToState(progress.steps));
        setStepDetails((progress.steps || []).reduce((acc, s) => ({ ...acc, [s.name]: s }), {}));
      },
      onTerminal: async () => {
        try {
          const fullResult = await getInvestigation(activeCaseId);
          setResult(fullResult);
          setPipelineState(updatePipelineFromResult(fullResult));
          setStepDetails((fullResult.steps || []).reduce((acc, s) => ({ ...acc, [s.name]: s }), {}));
          if (fullResult.status === 'COMPLETE') {
            addToast(`Investigation complete — case ${activeCaseId}`, 'success');
          } else {
            setError(fullResult.error || 'Investigation failed');
            addToast(`Investigation failed: ${fullResult.error || 'unknown error'}`, 'error');
          }
        } catch (fetchErr) {
          setError(fetchErr.message || 'Failed to fetch investigation result');
        } finally {
          setIsSubmitting(false);
        }
      },
    }
  );

  const handleSubmit = useCallback(
    async (formData) => {
      setIsSubmitting(true);
      setResult(null);
      setError(null);
      setPipelineState(createInitialPipelineState());
      setStepDetails({});

      try {
        const response = await runInvestigation({
          subject_id: formData.subject_id,
          hop_depth: formData.hop_depth,
          jurisdiction: formData.jurisdiction,
          case_id: formData.case_id,
        });
        const caseId = response.case_id;
        setActiveCaseId(caseId);
        setSearchParams({ case_id: caseId });

        if (response.status === 'COMPLETE' || response.status === 'FAILED') {
          setResult(response);
          setPipelineState(updatePipelineFromResult(response));
          setStepDetails((response.steps || []).reduce((acc, s) => ({ ...acc, [s.name]: s }), {}));
          if (response.status === 'COMPLETE') {
            addToast(`Investigation complete — case ${caseId}`, 'success');
          } else {
            setError(response.error || 'Investigation failed');
            addToast(`Investigation failed: ${response.error || 'unknown error'}`, 'error');
          }
          setIsSubmitting(false);
        }
      } catch (err) {
        setError(err.message || 'Investigation failed to launch');
        setResult({ status: 'FAILED', error: err.message });
        addToast(`Investigation failed: ${err.message}`, 'error');
        setIsSubmitting(false);
      }
    },
    [addToast, setSearchParams]
  );

  const hasStarted = isSubmitting || polling || Object.keys(pipelineState).length > 0;

  return (
    <div>
      <PageHeader
        title="Investigation Console"
        subtitle="Scoped graph analysis and draft narrative workspace (research runtime)"
      />

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6">
            <InvestigationForm
              prefillSubjectId={searchParams.get('subject_id')}
              isSubmitting={isSubmitting || polling}
              onSubmit={handleSubmit}
            />
          </GlowCard>
        </motion.div>

        {networkWarning && (
          <div role="status" className="p-3 bg-amber-50 border border-amber-200 rounded-card text-xs text-amber-900">
            {networkWarning}
          </div>
        )}

        {hasStarted && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <h3 className="text-sm font-semibold text-text-0 mb-4 uppercase tracking-wider">
                Pipeline Status
              </h3>
              <PipelineTracker stepStates={pipelineState} stepDetails={stepDetails} />
            </GlowCard>
          </motion.div>
        )}

        {error && !result?.sar_narrative && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <div className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--rose-base)' }}>
                <span>⚠ Investigation Error:</span>
                <span className="font-mono">{error}</span>
              </div>
            </GlowCard>
          </motion.div>
        )}

        {result && result.sar_mode && result.sar_mode !== 'none' && (
          <motion.div variants={fadeUp}>
            <GlowCard className="p-6">
              <h3 className="text-sm font-semibold text-text-0 mb-4 uppercase tracking-wider">
                Draft Generation Details
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-surface-1 rounded-lg">
                  <span className="text-xs text-text-3 block mb-1">Draft Mode</span>
                  <span className={`font-mono text-sm font-bold ${
                    result.sar_mode === 'llm' ? 'text-emerald-600' : 'text-amber-600'
                  }`}>
                    {result.sar_mode === 'llm' ? 'LLM (Research)' : 'Mechanical Template'}
                  </span>
                </div>
                <div className="p-3 bg-surface-1 rounded-lg">
                  <span className="text-xs text-text-3 block mb-1">Retry Count</span>
                  <span className="font-mono text-sm font-bold text-text-0">
                    {result.retry_count || 0}
                  </span>
                </div>
                <div className="p-3 bg-surface-1 rounded-lg">
                  <span className="text-xs text-text-3 block mb-1">Heuristic Score (Uncalibrated)</span>
                  <span className="font-mono text-sm font-bold text-text-0">
                    {Number.isFinite(result.confidence_score) ? result.confidence_score : 'Not available'}
                  </span>
                </div>
              </div>
              {result.validation_errors && result.validation_errors.length > 0 && (
                <div className="mt-4 p-3 bg-rose-50 rounded-lg border border-rose-200">
                  <span className="text-xs font-semibold text-rose-700 block mb-2">
                    Validation Issues ({result.validation_errors.length})
                  </span>
                  <ul className="space-y-1">
                    {result.validation_errors.map((err, i) => (
                      <li key={i} className="text-xs font-mono text-rose-800">
                        {typeof err === 'string' ? err : err.message || JSON.stringify(err)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </GlowCard>
          </motion.div>
        )}

        {result && result.status !== 'IN_PROGRESS' && result.status !== 'PENDING' && (
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
