import { motion } from 'framer-motion';
import { FileText, Globe, Calendar, User, MapPin, AlertTriangle, Scale } from 'lucide-react';
import TypologyBadge from '@/components/shared/TypologyBadge';

const sarEntrance = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

export default function SARDocument({ investigation }) {
  if (!investigation) return null;

  const { sar_draft, sar_narrative, jurisdiction, case_id,
          confidence_score, detected_typology, investigation_start } = investigation;

  const isFinCEN = jurisdiction !== 'fiu_ind';
  const regLabel = isFinCEN ? 'FinCEN Suspicious Activity Report' : 'FIU-IND Suspicious Transaction Report';
  const regAct = isFinCEN ? 'Bank Secrecy Act (31 U.S.C. § 5318)' : 'Prevention of Money Laundering Act, 2002 (PMLA)';
  const regBody = isFinCEN ? 'Financial Crimes Enforcement Network (FinCEN)' : 'Financial Intelligence Unit — India (FIU-IND)';
  const tzLabel = isFinCEN ? 'UTC' : 'IST (+05:30)';

  // Format timestamp for jurisdiction
  const formatTime = (isoStr) => {
    if (!isoStr) return 'N/A';
    const d = new Date(isoStr);
    if (isFinCEN) return d.toUTCString();
    return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  };

  return (
    <motion.div
      variants={sarEntrance}
      initial="hidden"
      animate="show"
      className="relative max-w-4xl mx-auto"
      role="document"
      aria-label={`SAR Report ${case_id}`}
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
                {regLabel}
              </h1>
              <p className="text-sm mt-1" style={{ color: 'var(--sar-label)' }}>
                Filed pursuant to {regAct}
              </p>
            </div>
            <div className="text-right">
              <TypologyBadge typology={detected_typology} />
            </div>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-4 gap-4 mt-5">
            {[
              { label: 'Case ID', value: case_id, mono: true },
              { label: 'Filing Date', value: formatTime(investigation_start) },
              { label: 'Jurisdiction', value: isFinCEN ? 'United States' : 'India' },
              { label: 'Confidence', value: `${Math.round(confidence_score * 100)}%`, mono: true },
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
            content={sar_draft?.where || (isFinCEN ? 'United States' : 'India')}
          />

          {/* WHEN — Timeframe */}
          <SARSection
            icon={Calendar}
            label="WHEN — Timeframe of Activity"
            content={sar_draft?.when || 'See transaction records'}
            sublabel={`All timestamps in ${tzLabel}`}
          />

          {/* WHY — Suspicious Indicators */}
          <SARSection
            icon={Scale}
            label="WHY — Indicators of Suspicious Activity"
            content={sar_draft?.why || 'See detection results'}
          />

          {/* NARRATIVE */}
          <div className="pt-4 border-t" style={{ borderColor: 'var(--sar-border)' }}>
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-3"
                style={{ color: 'var(--sar-heading)' }}>
              Full Narrative
            </h3>
            <div
              className="font-mono text-sm leading-[1.8] whitespace-pre-wrap"
              style={{ color: 'var(--sar-text)' }}
            >
              {sar_narrative}
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
          className="px-8 py-4 border-t-2 flex items-center justify-between"
          style={{ borderColor: 'var(--sar-border)', background: 'rgba(241, 245, 249, 0.5)' }}
        >
          <div className="flex items-center gap-2">
            <Globe className="w-3.5 h-3.5" style={{ color: 'var(--sar-label)' }} />
            <span className="text-[10px] font-mono" style={{ color: 'var(--sar-label)' }}>
              {regBody}
            </span>
          </div>
          <span className="text-[10px] font-mono" style={{ color: 'var(--sar-label)' }}>
            Generated by ARGUS v1.0.0 · TRACER v7.0.0 ·{' '}
            {formatTime(new Date().toISOString())}
          </span>
        </div>
      </div>
    </motion.div>
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
