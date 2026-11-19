import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  GitBranch,
  FileSearch,
  ShieldCheck,
  ArrowRight,
  BarChart3,
  FileText,
  FolderOpen,
  Copy,
  Check as CheckIcon,
} from 'lucide-react';
import TypologyBadge from '@/components/shared/TypologyBadge';
import StatusBadge from '@/components/shared/StatusBadge';
import AccordionSection from '@/components/shared/AccordionSection';

/** SAR document entrance animation */
const sarEntrance = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
};

/** Investigation artifacts, heuristic score, and explicitly reported source checks. */
export default function InvestigationResults({ result }) {
  if (!result) return null;

  const totalDuration =
    result.steps?.reduce((sum, s) => sum + (s.duration_ms || 0), 0) || 0;

  return (
    <motion.div
      variants={sarEntrance}
      initial="hidden"
      animate="show"
      className="space-y-6"
      data-testid="investigation-results"
    >
      {/* ═══ Section 1: Result Header ═══ */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between py-4 border-b border-surface-3 gap-4">
        <div className="flex items-center gap-4 flex-wrap">
          <TypologyBadge typology={result.detected_typology} />
          <StatusBadge status={result.status} />
          <span className="text-xs font-mono text-text-3">
            {result.steps?.length || 0} steps · {totalDuration}ms
          </span>
        </div>
        <div className="text-xs text-text-2">
          <span>Heuristic score (uncalibrated): </span>
          <span className="font-mono tabular-nums" data-testid="heuristic-score">
            {Number.isFinite(result.confidence_score) ? result.confidence_score : 'Not available'}
          </span>
          <p className="text-text-3 mt-1">Not a probability or verification result.</p>
        </div>
      </div>

      {/* ═══ Draft Narrative Preview ═══ */}
      <div>
        <h4 className="text-sm font-semibold text-text-1">Draft investigation narrative</h4>
        <p className="text-xs text-text-2 mt-1">Not submitted to FinCEN. For review only.</p>
      </div>
      <div className="relative" data-testid="sar-preview">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          <span
            className="font-mono text-4xl font-bold tracking-[0.3em] uppercase select-none"
            style={{
              color: 'var(--sar-watermark)',
              transform: 'rotate(-25deg)',
            }}
            data-testid="sar-watermark"
          >
            CONFIDENTIAL
          </span>
        </div>
        {result.sar_narrative && (
          <div className="absolute top-3 right-3 z-20">
            <CopyButton text={result.sar_narrative} />
          </div>
        )}
        <div
          className="p-6 rounded-card border font-mono text-sm leading-relaxed whitespace-pre-wrap"
          style={{
            background: 'var(--sar-bg)',
            borderColor: 'var(--sar-border)',
            color: 'var(--sar-text)',
          }}
        >
          {result.sar_narrative || 'No draft narrative available.'}
        </div>
      </div>

      {/* ═══ Section 4: Detection Details ═══ */}
      <AccordionSection
        title="Structuring Detection"
        count={result.detection_results?.structuring_hits?.length || 0}
        defaultOpen={
          (result.detection_results?.structuring_hits?.length || 0) > 0
        }
        icon={AlertTriangle}
        accentColor="var(--amber-base)"
      >
        {(result.detection_results?.structuring_hits || []).length === 0 ? (
          <div className="text-sm text-text-3">
            No structuring patterns detected.
          </div>
        ) : (
          (result.detection_results?.structuring_hits || []).map((hit, i) => (
            <div
              key={i}
              className="p-4 bg-surface-1 rounded-lg border border-surface-3 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-bold text-text-0">
                  Account: {hit.node ?? 'Unknown'}
                </span>
                <span className="font-mono text-xs text-text-2">
                  {hit.tx_count ?? 'Unknown'} txns
                </span>
              </div>
              <div className="font-mono text-sm text-text-1">
                Total: <span className="font-bold">{hit.currency?.trim() || 'Currency unknown'} {hit.total ?? 'Not available'}</span>
                <span className="text-text-3 ml-2">Mode: {hit.currency?.trim() || 'Currency unknown'} {hit.mode ?? 'Not available'}</span>
              </div>
              {(hit.sources || []).length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {hit.sources.map((s) => (
                    <span
                      key={s}
                      className="px-2 py-0.5 rounded-badge text-[10px] font-mono"
                      style={{
                        background: 'var(--amber-tint)',
                        color: 'var(--amber-base)',
                      }}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </AccordionSection>

      <AccordionSection
        title="Layering Detection"
        count={result.detection_results?.layering_hits?.length || 0}
        defaultOpen={
          (result.detection_results?.layering_hits?.length || 0) > 0
        }
        icon={GitBranch}
        accentColor="var(--violet-base)"
      >
        {(result.detection_results?.layering_hits || []).length === 0 ? (
          <div className="text-sm text-text-3">
            No layering chains detected.
          </div>
        ) : (
          (result.detection_results?.layering_hits || []).map((chain, i) => (
            <div
              key={i}
              className="p-4 bg-surface-1 rounded-lg border border-surface-3 space-y-3"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-text-2">
                  Chain {i + 1}
                </span>
                <span
                  className="font-mono text-xs font-bold"
                  style={{ color: 'var(--violet-base)' }}
                >
                  {chain.hop_count} hops
                </span>
                <span className="font-mono text-xs text-text-3">
                  avg decay: {chain.avg_decay}
                </span>
              </div>
              {/* Chain node visualization: horizontal flow */}
              <div className="flex items-center gap-1 flex-wrap">
                {(chain.chain_nodes || []).map((node, ni) => (
                  <React.Fragment key={node}>
                    {ni > 0 && (
                      <ArrowRight className="w-3 h-3 text-text-3 flex-shrink-0" />
                    )}
                    <span
                      className="px-2 py-0.5 rounded-badge text-[10px] font-mono font-bold"
                      style={{
                        background: 'var(--violet-tint)',
                        color: 'var(--violet-base)',
                      }}
                    >
                      {node}
                    </span>
                  </React.Fragment>
                ))}
              </div>
            </div>
          ))
        )}
      </AccordionSection>

      {/* ═══ Section 5: Evidence Package ═══ */}
      <AccordionSection
        title="Evidence Synthesis"
        count={result.evidence_package?.discrepancies?.length || 0}
        defaultOpen={result.evidence_package?.verdict !== 'NOT_APPLICABLE'}
        icon={FileSearch}
        accentColor="var(--cyan-base)"
      >
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm text-text-2">Verdict:</span>
            <span
              className={`px-2.5 py-0.5 rounded-badge text-xs font-bold uppercase ${
                result.evidence_package?.verdict === 'DISAGREEMENT'
                  ? 'bg-amber-50 text-amber-700'
                  : 'bg-surface-2 text-text-2'
              }`}
              data-testid="evidence-verdict"
            >
              {result.evidence_package?.verdict || 'Not provided'}
            </span>
          </div>
          <p className="text-xs text-text-2">
            Evidence verdicts describe available observations, not a determination of suspicious activity.
          </p>
          {result.evidence_package?.reasoning && (
            <p className="text-sm text-text-1 leading-relaxed">
              {result.evidence_package.reasoning}
            </p>
          )}
          {(result.evidence_package?.discrepancies || []).length > 0 && (
            <div className="space-y-1">
              <span className="text-xs font-semibold text-text-2 uppercase tracking-wider">
                Discrepancies
              </span>
              {result.evidence_package.discrepancies.map((d, i) => (
                <div
                  key={i}
                  className="p-2 bg-amber-50 rounded text-xs font-mono text-amber-800"
                >
                  {typeof d === 'string' ? d : JSON.stringify(d)}
                </div>
              ))}
            </div>
          )}
        </div>
      </AccordionSection>

      {/* ═══ Analysis Coverage ═══ */}
      <AnalysisCoverage coverage={result.coverage} typology={result.detected_typology} />

      {/* ═══ Source Checks ═══ */}
      <SourceChecks validation={result.validation_result} />

      {/* ═══ Section 7: Action Bar ═══ */}
      <div className="flex flex-wrap items-center gap-3 pt-6 border-t border-surface-3 mt-6">
        <Link
          to={`/assessment?case_id=${result.case_id}`}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent text-white text-sm font-semibold
                     rounded-btn hover:bg-accent-hover transition-colors shadow-sm"
          data-testid="score-investigation-btn"
        >
          <BarChart3 className="w-4 h-4" />
          Score Investigation
        </Link>
        <Link
          to={`/sar?case_id=${result.case_id}`}
          className="flex items-center gap-2 px-5 py-2.5 bg-surface-0 text-text-1 text-sm font-semibold
                     rounded-btn border border-surface-3 hover:bg-surface-1 transition-colors"
          data-testid="view-sar-btn"
        >
          <FileText className="w-4 h-4" />
          View Draft Narrative
        </Link>
        <Link
          to={`/evidence?entity_id=${result.subject_id}`}
          className="flex items-center gap-2 px-5 py-2.5 bg-surface-0 text-text-1 text-sm font-semibold
                     rounded-btn border border-surface-3 hover:bg-surface-1 transition-colors"
          data-testid="browse-evidence-btn"
        >
          <FolderOpen className="w-4 h-4" />
          Browse Evidence
        </Link>
      </div>
    </motion.div>
  );
}

/** Clipboard copy button with success feedback. */
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(`Draft investigation narrative\nNot submitted to FinCEN. For review only.\n\n${text}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard API may fail in non-HTTPS */ }
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-btn
                 bg-surface-0/90 backdrop-blur-sm border border-surface-3
                 hover:bg-surface-1 transition-colors"
      type="button"
      title="Copy draft narrative to clipboard"
      aria-live="polite"
      data-testid="copy-narrative-btn"
    >
      {copied ? (
        <><CheckIcon className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" /><span className="text-emerald-600">Draft copied</span></>
      ) : (
        <><Copy className="w-3.5 h-3.5 text-text-2" aria-hidden="true" /><span className="text-text-2">Copy draft</span></>
      )}
    </button>
  );
}

/** Missing or contradictory validation metadata must never imply successful checks. */
function SourceChecks({ validation }) {
  const errors = Array.isArray(validation?.errors) ? validation.errors : [];
  const passed = validation?.status === 'PASSED' && validation.passed === true && errors.length === 0;
  let label = 'Not run';
  let color = 'var(--text-2)';

  if (passed) {
    label = 'Passed for the reported source checks';
    color = 'var(--emerald-base)';
  } else if (validation?.status === 'PASSED') {
    label = 'Inconsistent result — pass not confirmed';
    color = 'var(--rose-base)';
  } else if (validation?.status === 'FAILED') {
    label = 'Failed';
    color = 'var(--rose-base)';
  } else if (validation?.status === 'PARTIAL') {
    label = 'Partial — source checks incomplete';
    color = 'var(--amber-base)';
  } else if (validation?.status === 'NOT_APPLICABLE') {
    label = 'Not applicable';
  }

  const countLabel = (value) => Number.isInteger(value) && value >= 0 ? value : 'Not reported';

  return (
    <AccordionSection
      title="Source checks"
      count={errors.length}
      defaultOpen
      icon={passed ? ShieldCheck : FileSearch}
      accentColor={color}
    >
      <div role="status" className="text-sm font-medium" style={{ color }} data-testid="validation-status">
        {label}
      </div>
      <p className="text-xs font-mono text-text-2" data-testid="validation-coverage">
        Checked: {countLabel(validation?.checked_count)} · Eligible: {countLabel(validation?.eligible_count)}
      </p>
      <p className="text-xs text-text-2">
        Source checks cover only the reported scope; they do not establish narrative accuracy or legal compliance.
      </p>
      {validation?.validator_version && (
        <p className="text-xs font-mono text-text-2">Validator version: {validation.validator_version}</p>
      )}
      {validation?.artifact_digest && (
        <p className="text-xs font-mono text-text-2 break-all">Artifact digest: {validation.artifact_digest}</p>
      )}
      {errors.length > 0 && (
        <ul aria-label="Source check errors" className="space-y-1">
          {errors.map((error, i) => (
            <li key={i} className="p-2 bg-rose-50 rounded text-xs font-mono text-rose-800">
              {typeof error === 'string' ? error : JSON.stringify(error)}
            </li>
          ))}
        </ul>
      )}
    </AccordionSection>
  );
}

/** Explicit analysis coverage & limitations — partial coverage is never a clean negative. */
function AnalysisCoverage({ coverage, typology }) {
  const status = coverage?.status || 'NOT_REPORTED';
  const limitations = Array.isArray(coverage?.limitations) ? coverage.limitations : [];
  let label = 'Coverage not reported';
  let color = 'var(--text-2)';

  if (status === 'COMPLETE' && limitations.length === 0) {
    label = 'Complete within declared search scope';
    color = 'var(--emerald-base)';
  } else if (status === 'PARTIAL' || limitations.length > 0) {
    label = 'Partial — traversal or scope limits were reached';
    color = 'var(--amber-base)';
  } else if (status === 'NOT_EVALUATED' || status === 'FAILED') {
    label = 'Not evaluated';
    color = 'var(--rose-base)';
  }

  return (
    <AccordionSection
      title="Analysis coverage"
      count={limitations.length}
      defaultOpen={status !== 'COMPLETE' || limitations.length > 0}
      icon={limitations.length > 0 ? AlertTriangle : FileSearch}
      accentColor={color}
    >
      <div role="status" className="text-sm font-medium" style={{ color }} data-testid="coverage-status">
        {label}
      </div>
      <p className="text-xs text-text-2 mt-1">
        {typology === 'NONE'
          ? 'No qualifying pattern found within this declared scope. This does not clear a customer or establish compliance.'
          : 'Coverage reflects only the declared graph/window scope; partial coverage cannot establish a negative finding.'}
      </p>
      {limitations.length > 0 && (
        <ul aria-label="Coverage limitations" className="space-y-1 mt-2" data-testid="coverage-limitations">
          {limitations.map((item, i) => (
            <li key={i} className="p-2 bg-amber-50 rounded text-xs font-mono text-amber-900">
              {typeof item === 'string'
                ? item
                : `${item.reason || 'LIMIT'}: node ${item.node ?? 'unknown'} (limit ${item.limit ?? 'n/a'})`}
            </li>
          ))}
        </ul>
      )}
    </AccordionSection>
  );
}
