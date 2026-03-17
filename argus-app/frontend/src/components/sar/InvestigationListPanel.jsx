import { useState, useMemo } from 'react';
import { Search, FileText } from 'lucide-react';
import TypologyBadge from '@/components/shared/TypologyBadge';
import ConfidenceBar from '@/components/shared/ConfidenceBar';

export default function InvestigationListPanel({ investigations, selectedId, onSelect }) {
  const [search, setSearch] = useState('');

  // Filter to only those with SAR narratives, then by search
  const filtered = useMemo(() => {
    return (investigations || [])
      .filter(inv => inv.sar_narrative && inv.sar_narrative.length > 0)
      .filter(inv => !search || inv.case_id.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => (b.investigation_timestamp || 0) - (a.investigation_timestamp || 0));
  }, [investigations, search]);

  return (
    <div className="w-[300px] flex-shrink-0 border-r border-surface-3 bg-surface-1 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-surface-3">
        <h3 className="font-display text-lg text-text-0 mb-3">SAR Reports</h3>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-3" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by case ID..."
            className="w-full pl-9 pr-3 py-2 text-sm bg-surface-0 border border-surface-3
                       rounded-btn focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filtered.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="w-8 h-8 text-text-3 mx-auto mb-2" />
            <p className="text-sm text-text-3">No SAR reports found</p>
            <p className="text-xs text-text-3 mt-1">Run an investigation first</p>
          </div>
        ) : (
          filtered.map(inv => (
            <button
              key={inv.case_id}
              onClick={() => onSelect(inv.case_id)}
              className={`w-full text-left p-3 rounded-lg transition-all ${
                selectedId === inv.case_id
                  ? 'bg-accent-tint border border-accent/20'
                  : 'hover:bg-surface-0 border border-transparent'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-xs font-bold text-text-0 truncate">
                  {inv.case_id}
                </span>
                <TypologyBadge typology={inv.detected_typology} />
              </div>
              <ConfidenceBar score={inv.confidence_score || 0} />
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-[10px] text-text-3">
                  {inv.jurisdiction === 'fiu_ind' ? '🇮🇳 FIU-IND' : '🇺🇸 FinCEN'}
                </span>
                <span className="text-[10px] font-mono text-text-3">
                  {inv.investigation_start ? new Date(inv.investigation_start).toLocaleDateString() : ''}
                </span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
