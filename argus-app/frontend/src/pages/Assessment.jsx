import { useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { BarChart3, Check, X, Target } from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import ErrorCard from '@/components/shared/ErrorCard';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import EmptyState from '@/components/shared/EmptyState';
import ScoreGauge from '@/components/assessment/ScoreGauge';
import RubricChart from '@/components/assessment/RubricChart';
import { AnimatedNumber } from '@/components/shared/AnimatedNumber';
import { useQuery } from '@/hooks/useQuery';
import { getInvestigations, runAssessment } from '@/api/client';

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

function scoreColor(pct) {
  if (pct >= 80) return 'var(--accent-base)';
  if (pct >= 60) return 'var(--emerald-base)';
  if (pct >= 30) return 'var(--amber-base)';
  return 'var(--rose-base)';
}

export default function Assessment() {
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [assessment, setAssessment] = useState(null);
  const [assessing, setAssessing] = useState(false);
  const [assessError, setAssessError] = useState(null);

  const { data: investigations } = useQuery('investigations', getInvestigations);
  const investigationList = investigations?.investigations || investigations || [];
  const completedInvestigations = investigationList.filter(
    (inv) => inv.status === 'COMPLETE'
  );

  const handleAssess = async () => {
    if (!selectedCaseId) return;
    setAssessing(true);
    setAssessError(null);
    try {
      const result = await runAssessment(selectedCaseId);
      setAssessment(result);
    } catch (err) {
      setAssessError(err instanceof Error ? err : new Error(err?.message || String(err)));
    } finally {
      setAssessing(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Assessment"
        subtitle="Investigation quality scoring and rubric analysis"
      />

      <motion.div
        variants={stagger}
        initial="hidden"
        animate="show"
        className="space-y-6"
      >
        {/* ═══ INVESTIGATION SELECTOR ═══ */}
        <motion.div variants={fadeUp}>
          <GlowCard className="p-6">
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <label className="text-sm font-medium text-text-1 mb-1.5 block">
                  Select Investigation
                </label>
                <select
                  data-testid="investigation-selector"
                  value={selectedCaseId}
                  onChange={(e) => {
                    setSelectedCaseId(e.target.value);
                    setAssessment(null);
                  }}
                  className="w-full px-3 py-2.5 text-sm font-mono bg-surface-0 border border-surface-3
                             rounded-btn focus:outline-none focus:ring-2 focus:ring-accent/30"
                >
                  <option value="">Choose an investigation...</option>
                  {completedInvestigations.map((inv) => (
                    <option key={inv.case_id} value={inv.case_id}>
                      {inv.case_id} — {inv.detected_typology} (
                      {Math.round((inv.confidence_score || 0) * 100)}%)
                    </option>
                  ))}
                </select>
              </div>
              <button
                data-testid="run-assessment-btn"
                onClick={handleAssess}
                disabled={!selectedCaseId || assessing}
                className="flex items-center gap-2 px-6 py-2.5 bg-accent text-white text-sm font-semibold
                           rounded-btn hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                           transition-all shadow-sm"
              >
                {assessing ? (
                  <LoadingSpinner size={16} />
                ) : (
                  <BarChart3 className="w-4 h-4" />
                )}
                {assessing ? 'Scoring...' : 'Run Assessment'}
              </button>
            </div>
          </GlowCard>
        </motion.div>

        {/* ═══ ERROR ═══ */}
        {assessError && (
          <motion.div variants={fadeUp}>
            <ErrorCard error={assessError} onRetry={handleAssess} />
          </motion.div>
        )}

        {/* ═══ RESULTS ═══ */}
        {assessment && (
          <>
            {/* Score + Rubric Row */}
            <motion.div variants={fadeUp} className="grid grid-cols-12 gap-6">
              {/* Gauge */}
              <div className="col-span-4">
                <GlowCard className="p-6 flex items-center justify-center">
                  <div className="relative inline-flex items-center justify-center">
                    <ScoreGauge score={assessment.overall_score || 0} />
                  </div>
                </GlowCard>
              </div>

              {/* Rubric Chart */}
              <div className="col-span-8">
                <GlowCard className="p-6">
                  <h3 className="text-sm font-semibold text-text-0 uppercase tracking-wider mb-4">
                    Rubric Breakdown
                  </h3>
                  <RubricChart rubric={assessment.rubric_breakdown} />
                </GlowCard>
              </div>
            </motion.div>

            {/* Entity Metrics */}
            <motion.div variants={fadeUp} className="grid grid-cols-3 gap-4">
              <MetricCard
                label="Precision"
                value={assessment.entity_metrics?.precision || 0}
                description="Flagged entities that were actually criminal"
              />
              <MetricCard
                label="Recall"
                value={assessment.entity_metrics?.recall || 0}
                description="Criminal entities correctly detected"
              />
              <MetricCard
                label="F1 Score"
                value={assessment.entity_metrics?.f1_score || 0}
                description="Harmonic mean of precision & recall"
              />
            </motion.div>

            {/* Hallucination + Five Ws Row */}
            <motion.div variants={fadeUp} className="grid grid-cols-2 gap-6">
              {/* Hallucination Report */}
              <GlowCard className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-text-0 uppercase tracking-wider">
                    Hallucination Check
                  </h3>
                  <span
                    className={`px-3 py-1 rounded-badge text-xs font-bold ${
                      (assessment.hallucination_count || 0) === 0
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-rose-50 text-rose-700'
                    }`}
                  >
                    {assessment.hallucination_count || 0} found
                  </span>
                </div>
                {(assessment.hallucination_count || 0) === 0 ? (
                  <div className="flex items-center gap-2 py-4 text-emerald-600">
                    <Check className="w-5 h-5" />
                    <span className="font-medium text-sm">
                      Zero hallucinations — all references verified
                    </span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {(assessment.hallucination_details || []).map((h, i) => (
                      <div
                        key={i}
                        className="p-2 bg-rose-50 rounded text-xs font-mono text-rose-800"
                      >
                        {h}
                      </div>
                    ))}
                  </div>
                )}
              </GlowCard>

              {/* Five Ws Checklist */}
              <GlowCard className="p-6">
                <h3 className="text-sm font-semibold text-text-0 uppercase tracking-wider mb-4">
                  Five Ws Validation
                </h3>
                <FiveWsChecklist fiveWs={assessment.five_ws} />
              </GlowCard>
            </motion.div>

            {/* Missed Indicators */}
            {(assessment.missed_indicators || []).length > 0 && (
              <motion.div variants={fadeUp}>
                <GlowCard className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Target className="w-4 h-4 text-status-amber" />
                    <h3 className="text-sm font-semibold text-text-0 uppercase tracking-wider">
                      Missed Indicators ({assessment.missed_indicators.length})
                    </h3>
                  </div>
                  <div className="space-y-2">
                    {assessment.missed_indicators.map((indicator, i) => (
                      <div
                        key={i}
                        className="p-3 bg-amber-50 rounded-lg text-sm text-amber-800"
                      >
                        {indicator}
                      </div>
                    ))}
                  </div>
                </GlowCard>
              </motion.div>
            )}
          </>
        )}

        {/* ═══ EMPTY STATE ═══ */}
        {!assessment && !assessing && completedInvestigations.length === 0 && (
          <EmptyState
            icon={BarChart3}
            title="No Completed Investigations"
            description="Run an investigation first to generate results that can be scored."
            action={
              <Link to="/investigate"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover transition-colors">
                Go to Investigation Console
              </Link>
            }
          />
        )}
        {!assessment && !assessing && completedInvestigations.length > 0 && (
          <EmptyState
            icon={BarChart3}
            title="Select an Investigation"
            description="Choose a completed investigation above to run quality assessment scoring."
          />
        )}
      </motion.div>
    </div>
  );
}

/* ═══ METRIC CARD (local to Assessment) ═══ */
function MetricCard({ label, value, description }) {
  const pct = Math.round(value * 100);
  return (
    <GlowCard className="p-5 text-center">
      <span className="text-xs font-semibold uppercase tracking-wider text-text-2">
        {label}
      </span>
      <div className="mt-2">
        <span
          className="font-display text-3xl"
          style={{ color: scoreColor(pct) }}
        >
          <AnimatedNumber value={pct} />
        </span>
        <span className="text-sm text-text-3">%</span>
      </div>
      {description && (
        <p className="text-xs text-text-3 mt-2">{description}</p>
      )}
    </GlowCard>
  );
}

/* ═══ FIVE WS CHECKLIST (local to Assessment) ═══ */
function FiveWsChecklist({ fiveWs }) {
  const items = [
    { key: 'who', label: 'WHO — Subject entities identified' },
    { key: 'what', label: 'WHAT — Activity described' },
    { key: 'where', label: 'WHERE — Jurisdiction specified' },
    { key: 'when', label: 'WHEN — Timeframe documented' },
    { key: 'why', label: 'WHY — Indicators articulated' },
  ];

  return (
    <div className="space-y-2">
      {items.map(({ key, label }) => {
        const passed = fiveWs?.[key];
        return (
          <div
            key={key}
            className="flex items-center gap-3 py-2 px-3 rounded-lg bg-surface-1"
          >
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                passed ? 'bg-emerald-500' : 'bg-rose-500'
              }`}
            >
              {passed ? (
                <Check className="w-3 h-3 text-white" />
              ) : (
                <X className="w-3 h-3 text-white" />
              )}
            </div>
            <span
              className={`text-sm ${
                passed ? 'text-text-1' : 'text-status-rose'
              }`}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
