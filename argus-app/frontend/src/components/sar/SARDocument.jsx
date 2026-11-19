import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Globe, Calendar, User, MapPin, AlertTriangle, Scale, Copy, Check } from 'lucide-react';
import TypologyBadge from '@/components/shared/TypologyBadge';

const sarEntrance = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

export default function SARDocument({ investigation }) {
  if (!investigation) return null;

  const { sar_draft, sar_narrative, jurisdiction, case_id,
          detected_typology, investigation_timestamp, investigation_start } = investigation;

  const isFinCEN = jurisdiction === 'fincen';
  const isFiuInd = jurisdiction === 'fiu_ind';
  const regAct = isFinCEN
    ? 'Bank Secrecy Act (31 U.S.C. § 5318)'
    : isFiuInd ? 'Prevention of Money Laundering Act, 2002 (PMLA)' : null;
  const regBody = isFinCEN
    ? 'Financial Crimes Enforcement Network (FinCEN)'
    : isFiuInd ? 'Financial Intelligence Unit — India (FIU-IND)' : 'Not provided';
  const submissionNotice = `Not submitted to FinCEN.${isFiuInd ? ' Not submitted to FIU-IND.' : ''}`;
  const createdAt = persistedCreationTime(investigation_timestamp, investigation_start);

  return (
    <motion.div
      variants={sarEntrance}
      initial="hidden"
      animate="show"
      className="relative max-w-4xl mx-auto"
      role="document"
      aria-label={`Draft investigation narrative ${case_id || ''}`.trim()}
    >
      {/* CONFIDENTIAL Watermark */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10 overflow-hidden">
        <span
          className="font-mono text-6xl font-bold tracking-[0.4em] uppercase select-none whitespace-nowrap"
          style={{ color: 'var(--sar-watermark)', transform: 'rotate(-30deg) scale(1.5)' }}
        >
          CONFIDENTIAL
        </span>
      </div>

      {/* Document */}
      <div
        className="relative z-0 rounded-card border-2 overflow-hidden"
        style={{
          background: 'var(--sar-bg)',
          borderColor: 'var(--sar-border)',
          boxShadow: '0 4px 24px rgba(0, 0, 0, 0.06)',
        }}
      >
        {/* ═══ DOCUMENT HEADER ═══ */}
        <div className="px-8 py-6 border-b-2" style={{ borderColor: 'var(--sar-border)' }}>
          <div className="flex items-start justify-between">
            <div>
              <h1
                className="font-display text-2xl tracking-tight"
                style={{ color: 'var(--sar-heading)' }}
              >
                Draft investigation narrative
              </h1>
              <p className="text-sm mt-1" style={{ color: 'var(--sar-label)' }}>
                {regAct
                  ? `Prepared under ${regAct} for review—not filed.`
                  : 'Prepared for review—not filed. Regulatory context not provided.'}
              </p>
              <p className="text-xs mt-2" style={{ color: 'var(--sar-label)' }}>
                Regulatory context only; this draft does not establish legal compliance.
              </p>
              <p className="text-sm font-semibold mt-2" style={{ color: 'var(--sar-heading)' }}>
                {submissionNotice}
              </p>
            </div>
            <div className="text-right">
              <TypologyBadge typology={detected_typology} />
            </div>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
            {[
              { label: 'Case ID', value: case_id || 'Not provided', mono: true },
              {
                label: 'Created (UTC)',
                value: createdAt
                  ? <time dateTime={createdAt.toISOString()} data-testid="investigation-created-at">{createdAt.toUTCString()}</time>
                  : 'Not available',
              },
              { label: 'Jurisdiction', value: isFinCEN ? 'United States' : isFiuInd ? 'India' : jurisdiction || 'Unknown' },
              { label: 'Document status', value: 'Draft — for review' },
            ].map(({ label, value, mono }) => (
              <div key={label}>
                <span className="text-[10px] uppercase tracking-wider font-semibold"
                      style={{ color: 'var(--sar-label)' }}>
                  {label}
                </span>
                <p className={`text-sm mt-0.5 ${mono ? 'font-mono font-bold' : 'font-medium'}`}
                   style={{ color: 'var(--sar-text)' }}>
                  {value}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* ═══ FIVE Ws SECTIONS ═══ */}
        <div className="px-8 py-6 space-y-6">
          {/* WHO — Subjects */}
          <SARSection
            icon={User}
            label="WHO — Subjects Under Investigation"
            content={sar_draft?.who || 'Entities not identified'}
          />

          {/* WHAT — Activity Description */}
          <SARSection
            icon={AlertTriangle}
            label="WHAT — Description of Suspicious Activity"
            content={sar_draft?.what || detected_typology}
          />

          {/* WHERE — Geographic Information */}
          <SARSection
            icon={MapPin}
            label="WHERE — Geographic Information"
            content={sar_draft?.where?.trim() || 'Unknown — geographic information not provided'}
          />

          {/* WHEN — Timeframe */}
          <SARSection
            icon={Calendar}
            label="WHEN — Timeframe of Activity"
            content={sar_draft?.when || 'Activity timeframe not provided'}
          />

          {/* WHY — Suspicious Indicators */}
          <SARSection
            icon={Scale}
            label="WHY — Indicators of Suspicious Activity"
            content={sar_draft?.why || 'See detection results'}
          />

          {/* NARRATIVE */}
          <div className="pt-4 border-t" style={{ borderColor: 'var(--sar-border)' }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider"
                  style={{ color: 'var(--sar-heading)' }}>
                Full Draft Narrative
              </h3>
              {sar_narrative && <SARCopyButton text={sar_narrative} submissionNotice={submissionNotice} />}
            </div>
            <div
              className="font-mono text-sm leading-[1.8] whitespace-pre-wrap"
              style={{ color: 'var(--sar-text)' }}
            >
              {sar_narrative || 'No draft narrative available.'}
            </div>
          </div>

          {/* CITED TRANSACTIONS */}
          {sar_draft?.cited_tx_ids?.length > 0 && (
            <div className="pt-4 border-t" style={{ borderColor: 'var(--sar-border)' }}>
              <h3 className="text-sm font-semibold uppercase tracking-wider mb-3"
                  style={{ color: 'var(--sar-heading)' }}>
                Referenced Transactions ({sar_draft.cited_tx_ids.length})
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {sar_draft.cited_tx_ids.map(txId => (
                  <span
                    key={txId}
                    className="px-2.5 py-1 rounded-badge text-[10px] font-mono font-bold bg-surface-2"
                    style={{ color: 'var(--sar-text)' }}
                  >
                    {txId}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ═══ REGULATORY FOOTER ═══ */}
        <div
          className="px-8 py-4 border-t-2 flex flex-wrap items-center justify-between gap-3"
          style={{ borderColor: 'var(--sar-border)', background: 'rgba(241, 245, 249, 0.5)' }}
        >
          <div className="flex items-center gap-2">
            <Globe className="w-3.5 h-3.5" style={{ color: 'var(--sar-label)' }} />
            <span className="text-[10px] font-mono" style={{ color: 'var(--sar-label)' }}>
              Regulatory context: {regBody}
            </span>
          </div>
          <span className="text-[10px] font-mono" style={{ color: 'var(--sar-label)' }}>
            Draft only · Review required before any submission
          </span>
        </div>
      </div>
    </motion.div>
  );
}

/** The API persists epoch seconds; never substitute the viewer's current time. */
function persistedCreationTime(timestamp, start) {
  const epoch = Number.isFinite(timestamp) ? new Date(timestamp * 1000) : null;
  if (epoch && Number.isFinite(epoch.getTime())) return epoch;
  const fallback = typeof start === 'string' && start.trim() ? new Date(start) : null;
  return fallback && Number.isFinite(fallback.getTime()) ? fallback : null;
}

function SARCopyButton({ text, submissionNotice }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(`Draft investigation narrative\n${submissionNotice} For review only.\n\n${text}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard may fail in non-HTTPS */ }
  }, [text, submissionNotice]);

  return (
    <button
      onClick={handleCopy}
      className="relative z-20 flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-btn
                 bg-surface-0/90 backdrop-blur-sm border border-surface-3
                 hover:bg-surface-1 transition-colors"
      type="button"
      title="Copy draft narrative to clipboard"
      aria-live="polite"
    >
      {copied ? (
        <><Check className="w-3.5 h-3.5 text-emerald-500" aria-hidden="true" /><span className="text-emerald-600">Draft copied</span></>
      ) : (
        <><Copy className="w-3.5 h-3.5 text-text-2" aria-hidden="true" /><span className="text-text-2">Copy draft</span></>
      )}
    </button>
  );
}

function SARSection({ icon: Icon, label, content, sublabel }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className="w-4 h-4" style={{ color: 'var(--accent-base)' }} />
        <h3 className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--sar-heading)' }}>
          {label}
        </h3>
      </div>
      <p className="font-mono text-sm leading-relaxed pl-6" style={{ color: 'var(--sar-text)' }}>
        {content}
      </p>
      {sublabel && (
        <p className="text-[10px] mt-1 pl-6" style={{ color: 'var(--sar-label)' }}>
          {sublabel}
        </p>
      )}
    </div>
  );
}
