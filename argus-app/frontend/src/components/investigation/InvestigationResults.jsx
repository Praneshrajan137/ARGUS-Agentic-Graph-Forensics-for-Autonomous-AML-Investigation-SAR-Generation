import React, { useEffect, useState, useCallback } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';
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

/**
 * Returns a CSS color variable based on confidence score (0–1 scale).
 * 0–0.29 → rose, 0.30–0.59 → amber, 0.60–0.79 → emerald, 0.80–1.0 → accent
 */
export function confidenceColor(score) {
  const pct = (score ?? 0) * 100;
  if (pct >= 80) return 'var(--accent-base)';
  if (pct >= 60) return 'var(--emerald-base)';
  if (pct >= 30) return 'var(--amber-base)';
  return 'var(--rose-base)';
}

/** Animated counter from 0 to value using spring physics. */
function AnimatedNumber({ value, duration = 0.8 }) {
  const spring = useSpring(0, { stiffness: 100, damping: 30 });
  const display = useTransform(spring, (v) => Math.round(v));

  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  return <motion.span>{display}</motion.span>;
}

/** SAR document entrance animation */
const sarEntrance = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
};

/**
 * Investigation results display with 7 sections:
 * 1. Result Header (typology + confidence)
 * 2. Confidence Breakdown (formula visualization)
 * 3. SAR Narrative Preview (paper metaphor + watermark)
 * 4. Detection Details (structuring + layering accordions)
 * 5. Evidence Package (verdict + discrepancies)
 * 6. Validation Report (hallucination check)
 * 7. Action Bar (Score / View SAR / Browse Evidence)
 *
 * @param {Object} result — Full investigation response from POST /api/investigation/investigate
 */
export default function InvestigationResults({ result }) {
  if (!result) return null;

  const totalDuration =
    result.steps?.reduce((sum, s) => sum + (s.duration_ms || 0), 0) || 0;

  // Confidence breakdown calculation
  const typology = result.detected_typology || 'NONE';
  const base = typology === 'BOTH' ? 0.6 : typology === 'NONE' ? 0.0 : 0.3;
  const evBoost =
    result.evidence_package?.verdict &&
    [
      'CORROBORATED',
      'SUSPICIOUS_DISCREPANCY',
      'CONFIRMED',
      'PARTIAL_MATCH',
    ].includes(result.evidence_package.verdict)
      ? 0.2
      : 0.0;
  const discBoost =
    (result.evidence_package?.discrepancies?.length || 0) > 0 ? 0.2 : 0.0;

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
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-2">Confidence</span>
          <span
            className="font-mono text-2xl font-bold tabular-nums"
            style={{ color: confidenceColor(result.confidence_score) }}
            data-testid="confidence-value"
          >
            <AnimatedNumber
              value={Math.round((result.confidence_score ?? 0) * 100)}
            />
            %
          </span>
        </div>
      </div>

      {/* ═══ Section 2: Confidence Breakdown ═══ */}
      <div data-testid="confidence-breakdown">
        <h4 className="text-xs font-semibold text-text-2 uppercase tracking-wider mb-3">
          Confidence Formula
        </h4>
        <div className="flex items-center gap-2 flex-wrap font-mono text-sm">
          <BreakdownChip
            label="base"
            value={base.toFixed(1)}
            sublabel={typology}
            highlight={base > 0}
            tintVar="--emerald-tint"
            colorVar="--emerald-base"
          />
          <span className="text-text-3 font-bold">+</span>
          <BreakdownChip
            label="evidence"
            value={evBoost.toFixed(1)}
            sublabel={result.evidence_package?.verdict || 'N/A'}
            highlight={evBoost > 0}
            tintVar="--accent-tint"
            colorVar="--accent-base"
          />
          <span className="text-text-3 font-bold">+</span>
          <BreakdownChip
            label="discrepancy"
            value={discBoost.toFixed(1)}
            sublabel={
              discBoost > 0
                ? `${result.evidence_package?.discrepancies?.length} found`
                : 'None'
            }
            highlight={discBoost > 0}
            tintVar="--amber-tint"
            colorVar="--amber-base"
          />
          <span className="text-text-3 font-bold">=</span>
          <span
            className="px-3 py-1.5 rounded-badge font-bold text-base"
            style={{
              background:
                (result.confidence_score ?? 0) >= 0.5
                  ? 'var(--emerald-tint)'
                  : 'var(--rose-tint)',
              color:
                (result.confidence_score ?? 0) >= 0.5
                  ? 'var(--emerald-base)'
                  : 'var(--rose-base)',
            }}
            data-testid="confidence-total"
          >
            {((result.confidence_score ?? 0) * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* ═══ Section 3: SAR Narrative Preview ═══ */}
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
          {result.sar_narrative ||
            'No SAR generated (confidence below threshold).'}
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
                  Mule:{' '}
                  <span style={{ color: 'var(--rose-base)' }}>{hit.node}</span>
                </span>
                <span className="font-mono text-xs text-text-2">
                  {hit.tx_count} txns · {hit.currency}
                </span>
              </div>
              <div className="font-mono text-sm text-text-1">
                Total: <span className="font-bold">${hit.total}</span>
                <span className="text-text-3 ml-2">Mode: {hit.mode}</span>
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
                result.evidence_package?.verdict === 'CORROBORATED'
                  ? 'bg-emerald-50 text-emerald-700'
                  : result.evidence_package?.verdict ===
                      'SUSPICIOUS_DISCREPANCY'
                    ? 'bg-amber-50 text-amber-700'
                    : 'bg-surface-2 text-text-2'
              }`}
              data-testid="evidence-verdict"
            >
              {result.evidence_package?.verdict || 'N/A'}
            </span>
          </div>
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

      {/* ═══ Section 6: Validation Report ═══ */}
      <AccordionSection
        title="Hallucination Validation"
        count={result.validation_errors?.length || 0}
        defaultOpen
        icon={ShieldCheck}
        accentColor={
          (result.validation_errors?.length || 0) > 0
            ? 'var(--rose-base)'
            : 'var(--emerald-base)'
        }
      >
        {(result.validation_errors || []).length === 0 ? (
          <div
            className="flex items-center gap-2 text-sm"
            style={{ color: 'var(--emerald-base)' }}
            data-testid="validation-pass"
          >
            <ShieldCheck className="w-4 h-4" />
            <span className="font-medium">
              Zero hallucinations detected — all entities and transactions
              verified
            </span>
          </div>
        ) : (
          <div className="space-y-1">
            {result.validation_errors.map((err, i) => (
              <div
                key={i}
                className="p-2 bg-rose-50 rounded text-xs font-mono text-rose-800"
              >
                {err}
              </div>
            ))}
          </div>
        )}
      </AccordionSection>

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
          View Full SAR
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
      await navigator.clipboard.writeText(text);
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
      title="Copy narrative to clipboard"
      data-testid="copy-narrative-btn"
    >
      {copied ? (
        <><CheckIcon className="w-3.5 h-3.5 text-emerald-500" /><span className="text-emerald-600">Copied</span></>
      ) : (
        <><Copy className="w-3.5 h-3.5 text-text-2" /><span className="text-text-2">Copy</span></>
      )}
    </button>
  );
}

/** Confidence formula chip for the breakdown visualisation. */
function BreakdownChip({
  label,
  value,
  sublabel,
  highlight,
  tintVar,
  colorVar,
}) {
  return (
    <div
      className="px-3 py-1.5 rounded-badge text-center"
      style={{
        background: highlight ? `var(${tintVar})` : 'var(--surface-2)',
        color: highlight ? `var(${colorVar})` : 'var(--text-3)',
      }}
    >
      <div className="font-bold text-base">{value}</div>
      <div className="text-[9px] uppercase tracking-wider">{label}</div>
      <div className="text-[8px] opacity-70 truncate max-w-[80px]">
        {sublabel}
      </div>
    </div>
  );
}
