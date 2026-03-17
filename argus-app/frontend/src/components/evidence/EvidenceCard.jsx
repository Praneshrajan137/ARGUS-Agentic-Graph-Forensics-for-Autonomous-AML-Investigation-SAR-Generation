import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { FileText, Mail, Building, User } from 'lucide-react';
import { highlightContent } from '@/utils/highlightContent';

const TYPE_MAP = {
  sar_narrative: { icon: FileText, label: 'SAR Narrative', color: 'var(--accent-base)', tint: 'var(--accent-tint)' },
  email: { icon: Mail, label: 'Email', color: 'var(--cyan-base)', tint: 'var(--cyan-tint)' },
  bank_statement: { icon: Building, label: 'Bank Statement', color: 'var(--amber-base)', tint: 'var(--amber-tint)' },
  kyc_document: { icon: User, label: 'KYC Document', color: 'var(--emerald-base)', tint: 'var(--emerald-tint)' },
  default: { icon: FileText, label: 'Document', color: 'var(--text-2)', tint: 'var(--surface-2)' },
};

export default function EvidenceCard({ document }) {
  const type = TYPE_MAP[document.doc_type || document.type] || TYPE_MAP.default;
  const Icon = type.icon;
  const content = document.content || document.body || document.narrative || '';
  const preview = content.slice(0, 280);

  return (
    <motion.div
      whileHover={{ y: -2, boxShadow: 'var(--shadow-md)' }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className="bg-surface-0 rounded-card border border-surface-3 shadow-xs overflow-hidden"
    >
      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-badge text-[10px] font-bold uppercase"
            style={{ background: type.tint, color: type.color }}
          >
            <Icon className="w-3 h-3" />
            {type.label}
          </span>
          {document.subject_id && (
            <Link
              to={`/graph?node=${document.subject_id}`}
              className="font-mono text-xs font-bold hover:underline"
              style={{ color: 'var(--cyan-base)' }}
            >
              Entity {document.subject_id}
            </Link>
          )}
        </div>

        {/* Content preview with highlighting */}
        <div className="text-sm text-text-1 leading-relaxed line-clamp-4">
          {highlightContent(preview)}
          {content.length > 280 && <span className="text-text-3">...</span>}
        </div>
      </div>

      {/* Footer */}
      {document.evidence_id && (
        <div className="px-5 py-2.5 border-t border-surface-3 bg-surface-1">
          <span className="font-mono text-[10px] text-text-3">{document.evidence_id}</span>
        </div>
      )}
    </motion.div>
  );
}
