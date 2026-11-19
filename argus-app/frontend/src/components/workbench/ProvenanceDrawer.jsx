import { useEffect } from 'react';
import { X, FileCheck2, ArrowDownRight } from 'lucide-react';

/**
 * Source Provenance Drawer — enables <=2-interaction navigation from any
 * factual claim or finding citation directly to its exact pinned ledger record,
 * source file SHA-256, and CSV row ordinal.
 */
export default function ProvenanceDrawer({ record, onClose, onJumpToRow }) {
  useEffect(() => {
    if (!record) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [record, onClose]);

  if (!record) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-900/30"
      role="dialog"
      aria-modal="true"
      aria-label={`Source provenance for record ${record.external_id}`}
      data-testid="provenance-drawer"
    >
      <div className="w-full max-w-lg bg-surface-0 border-l border-surface-3 h-full overflow-y-auto p-6 shadow-xl flex flex-col gap-4">
        <div className="flex items-start justify-between border-b border-surface-3 pb-4">
          <div className="flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-accent" aria-hidden="true" />
            <div>
              <h2 className="font-display text-xl text-text-0">Source Record Provenance</h2>
              <p className="text-xs font-mono text-text-2">Event ID: {record.external_id}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close provenance drawer"
            className="p-2 rounded-btn border border-surface-3 hover:bg-surface-1 text-text-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <dl className="grid grid-cols-1 gap-2 text-xs bg-surface-1 p-4 rounded-lg border border-surface-3">
          <div className="flex justify-between gap-2">
            <dt className="text-text-2">Record ID</dt>
            <dd className="font-mono text-text-0 break-all">{record.record_id}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-2">Source File</dt>
            <dd className="font-mono text-text-0">{record.source_filename || record.source_file_id}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-2">Parsed CSV Row Ordinal</dt>
            <dd className="font-mono font-bold text-text-0" data-testid="provenance-row-number">Row #{record.row_number}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-text-2">Source File SHA-256</dt>
            <dd className="font-mono text-[11px] text-text-1 break-all" data-testid="provenance-sha256">
              {record.source_file_sha256 || 'Recorded in manifest'}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-text-2">Canonical Record Digest</dt>
            <dd className="font-mono text-[11px] text-text-1 break-all">{record.digest}</dd>
          </div>
          {record.exclusion_reason && (
            <div className="flex justify-between gap-2 text-amber-800 bg-amber-50 p-2 rounded">
              <dt className="font-semibold">Analysis Exclusion</dt>
              <dd className="font-mono">{record.exclusion_reason}</dd>
            </div>
          )}
        </dl>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-2 mb-2">
            Pinned Canonical Payload (Literal Source Values)
          </h3>
          <pre className="p-3 rounded-lg bg-surface-1 border border-surface-3 font-mono text-xs text-text-0 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(record.payload, null, 2)}
          </pre>
        </div>

        {onJumpToRow && (
          <button
            type="button"
            onClick={() => onJumpToRow(record.external_id)}
            className="mt-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover"
          >
            <ArrowDownRight className="w-4 h-4" aria-hidden="true" />
            Highlight in Observed Facts Table
          </button>
        )}
      </div>
    </div>
  );
}
