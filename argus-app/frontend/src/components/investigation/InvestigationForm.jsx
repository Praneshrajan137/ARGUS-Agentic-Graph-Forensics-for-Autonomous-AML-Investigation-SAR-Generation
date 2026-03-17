import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Crosshair } from 'lucide-react';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import { getNodes } from '@/api/client';

const JURISDICTIONS = [
  { value: 'fincen', label: 'FinCEN', subtitle: 'US / BSA', flag: '🇺🇸' },
  { value: 'fiu_ind', label: 'FIU-IND', subtitle: 'India / PMLA', flag: '🇮🇳' },
];

const RISK_COLORS = {
  low: { bg: 'var(--emerald-tint)', text: 'var(--emerald-base)' },
  medium: { bg: 'var(--amber-tint)', text: 'var(--amber-base)' },
  high: { bg: 'var(--rose-tint)', text: 'var(--rose-base)' },
};

const TYPE_COLORS = {
  individual: { bg: 'var(--cyan-tint)', text: 'var(--cyan-base)' },
  business: { bg: 'var(--violet-tint)', text: 'var(--violet-base)' },
  bank: { bg: 'var(--accent-tint)', text: 'var(--accent-base)' },
};

/**
 * Investigation input form with debounced autocomplete, hop slider,
 * jurisdiction segmented control, and auto-generated case ID.
 *
 * @param {string|null} prefillSubjectId — Pre-fill from URL param
 * @param {boolean}     isSubmitting     — External submitting state
 * @param {Function}    onSubmit         — Called with { subject_id, hop_depth, jurisdiction, case_id }
 */
export default function InvestigationForm({
  prefillSubjectId,
  isSubmitting,
  onSubmit,
}) {
  const [subjectId, setSubjectId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [hopDepth, setHopDepth] = useState(3);
  const [jurisdiction, setJurisdiction] = useState('fincen');
  const [caseId] = useState(
    () => `ARGUS-${Date.now().toString(36).toUpperCase()}`
  );
  const [showDropdown, setShowDropdown] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const debounceRef = useRef(null);
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  // Pre-fill from URL param
  useEffect(() => {
    if (prefillSubjectId) {
      setSubjectId(prefillSubjectId);
      setSearchQuery(prefillSubjectId);
    }
  }, [prefillSubjectId]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target) &&
        inputRef.current &&
        !inputRef.current.contains(e.target)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Debounced search
  const handleSearchChange = useCallback((value) => {
    setSearchQuery(value);
    setSubjectId('');
    setHighlightedIndex(-1);

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!value.trim()) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await getNodes({ search: value.trim(), per_page: 8 });
        setSearchResults(res.nodes || []);
        setShowDropdown(true);
      } catch {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
  }, []);

  const selectItem = useCallback((node) => {
    setSubjectId(String(node.id));
    setSearchQuery(node.name || String(node.id));
    setShowDropdown(false);
    setSearchResults([]);
    setHighlightedIndex(-1);
  }, []);

  // Keyboard navigation for dropdown
  const handleKeyDown = useCallback(
    (e) => {
      if (!showDropdown || searchResults.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev < searchResults.length - 1 ? prev + 1 : 0
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedIndex((prev) =>
          prev > 0 ? prev - 1 : searchResults.length - 1
        );
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < searchResults.length) {
          selectItem(searchResults[highlightedIndex]);
        }
      } else if (e.key === 'Escape') {
        setShowDropdown(false);
        setHighlightedIndex(-1);
      }
    },
    [showDropdown, searchResults, highlightedIndex, selectItem]
  );

  const handleSubmit = () => {
    if (!subjectId || isSubmitting) return;
    onSubmit({
      subject_id: subjectId,
      hop_depth: hopDepth,
      jurisdiction,
      case_id: caseId,
    });
  };

  return (
    <div className="space-y-6">
      {/* 2-column grid on desktop, single column on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Subject ID Search */}
        <div className="relative">
          <label className="block text-sm font-medium text-text-1 mb-1.5">
            Subject Entity
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-3" />
            <input
              ref={inputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (searchResults.length > 0) setShowDropdown(true);
              }}
              placeholder="Search by node ID or name..."
              className="w-full pl-10 pr-4 py-2.5 bg-surface-0 border border-surface-3
                         rounded-btn text-sm text-text-0 font-mono
                         focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent
                         placeholder:text-text-3 transition-all"
              data-testid="subject-search-input"
            />
            {searchLoading && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <LoadingSpinner size={16} />
              </div>
            )}
          </div>

          {/* Autocomplete dropdown */}
          {showDropdown && (
            <div
              ref={dropdownRef}
              className="absolute top-full left-0 right-0 mt-1 z-50
                         bg-surface-0 border border-surface-3 rounded-card shadow-lg
                         max-h-64 overflow-y-auto"
              data-testid="search-dropdown"
            >
              {searchResults.length === 0 ? (
                <div className="px-4 py-3 text-sm text-text-3">
                  No matching entities
                </div>
              ) : (
                searchResults.map((node, i) => {
                  const risk = RISK_COLORS[node.risk_rating] || RISK_COLORS.low;
                  const typeColor =
                    TYPE_COLORS[node.entity_type] || TYPE_COLORS.individual;
                  return (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => selectItem(node)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors
                        ${i === highlightedIndex ? 'bg-accent-tint' : 'hover:bg-surface-1'}`}
                      data-testid={`search-result-${node.id}`}
                    >
                      <span className="font-mono text-sm font-bold text-text-0 min-w-[3rem]">
                        {node.id}
                      </span>
                      <span className="text-sm text-text-1 truncate flex-1">
                        {node.name}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded-badge text-[10px] font-semibold uppercase"
                        style={{
                          background: typeColor.bg,
                          color: typeColor.text,
                        }}
                      >
                        {node.entity_type}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded-badge text-[10px] font-semibold uppercase"
                        style={{ background: risk.bg, color: risk.text }}
                      >
                        {node.risk_rating}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Hop Depth Slider */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-text-1">
              Analysis Depth
            </label>
            <span className="font-mono text-sm font-bold" style={{ color: 'var(--accent-base)' }}>
              {hopDepth} hops
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={10}
            value={hopDepth}
            onChange={(e) => setHopDepth(+e.target.value)}
            className="w-full h-2 bg-surface-2 rounded-full appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5
                       [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full
                       [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:shadow-md
                       [&::-webkit-slider-thumb]:cursor-pointer"
            data-testid="hop-depth-slider"
          />
          <div className="flex justify-between text-[10px] font-mono text-text-3">
            <span>1</span>
            <span>3</span>
            <span>5</span>
            <span>7</span>
            <span>10</span>
          </div>
        </div>

        {/* Jurisdiction Selector — segmented control */}
        <div>
          <label className="block text-sm font-medium text-text-1 mb-1.5">
            Jurisdiction
          </label>
          <div className="flex rounded-btn border border-surface-3 overflow-hidden">
            {JURISDICTIONS.map((j) => (
              <button
                key={j.value}
                type="button"
                onClick={() => setJurisdiction(j.value)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm
                  font-medium transition-all
                  ${
                    jurisdiction === j.value
                      ? 'bg-accent text-white shadow-inner'
                      : 'bg-surface-0 text-text-2 hover:bg-surface-1'
                  }`}
                data-testid={`jurisdiction-${j.value}`}
              >
                <span className="text-lg">{j.flag}</span>
                <div className="text-left">
                  <div className="font-semibold">{j.label}</div>
                  <div className="text-[10px] opacity-80">{j.subtitle}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Case ID Display */}
        <div>
          <label className="block text-sm font-medium text-text-1 mb-1.5">
            Case ID
          </label>
          <div className="flex items-center gap-2 px-3 py-2.5 bg-surface-2 rounded-btn border border-surface-3">
            <Crosshair className="w-4 h-4 text-text-3 flex-shrink-0" />
            <span
              className="font-mono text-sm font-medium text-text-1"
              data-testid="case-id-display"
            >
              {caseId}
            </span>
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={!subjectId || isSubmitting}
        className="w-full py-3 px-6 bg-accent text-white font-semibold rounded-btn
                   hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                   transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2"
        data-testid="launch-investigation-btn"
        type="button"
      >
        {isSubmitting ? (
          <>
            <LoadingSpinner size={18} />
            <span>Running Investigation...</span>
          </>
        ) : (
          <>
            <Search className="w-4 h-4" />
            <span>Launch Investigation</span>
          </>
        )}
      </button>
    </div>
  );
}
