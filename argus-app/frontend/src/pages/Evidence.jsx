import { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Search, FolderOpen } from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import ErrorCard from '@/components/shared/ErrorCard';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import EmptyState from '@/components/shared/EmptyState';
import EvidenceCard from '@/components/evidence/EvidenceCard';
import { useQuery } from '@/hooks/useQuery';
import { getEvidence } from '@/api/client';

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] } },
};

export default function Evidence() {
  const [searchParams] = useSearchParams();
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState(searchParams.get('entity_id') || '');

  // Debounce keyword search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  const queryParams = useMemo(() => ({
    keyword: debouncedKeyword || undefined,
    type: typeFilter || undefined,
    entity_id: entityFilter || undefined,
    limit: 100,
  }), [debouncedKeyword, typeFilter, entityFilter]);

  const queryKey = `evidence-${JSON.stringify(queryParams)}`;
  const { data, loading, error, refetch } = useQuery(
    queryKey, () => getEvidence(queryParams), { staleTime: 15000 }
  );

  const documents = data?.documents || data || [];

  return (
    <div>
      <PageHeader
        title="Evidence Browser"
        subtitle={`${documents.length} document${documents.length !== 1 ? 's' : ''} found`}
      />

      {/* Search and Filters */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-3" />
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="Search evidence content..."
            className="w-full pl-9 pr-3 py-2.5 text-sm bg-surface-0 border border-surface-3
                       rounded-btn focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
          />
        </div>
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          className="px-3 py-2.5 text-sm bg-surface-0 border border-surface-3 rounded-btn
                     focus:outline-none focus:ring-2 focus:ring-accent/30"
        >
          <option value="">All Types</option>
          <option value="sar_narrative">SAR Narrative</option>
          <option value="email">Email</option>
          <option value="bank_statement">Bank Statement</option>
          <option value="kyc_document">KYC Document</option>
        </select>
        <input
          type="text"
          value={entityFilter}
          onChange={e => setEntityFilter(e.target.value)}
          placeholder="Entity ID"
          className="w-32 px-3 py-2.5 text-sm font-mono bg-surface-0 border border-surface-3
                     rounded-btn focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
      </div>

      {/* Content */}
      {loading && documents.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size={32} />
        </div>
      ) : error ? (
        <ErrorCard error={error} onRetry={refetch} />
      ) : documents.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="No Evidence Found"
          description={keyword || typeFilter || entityFilter
            ? "No documents match your current filters. Try broadening your search."
            : "Evidence documents will appear here after graph generation."}
        />
      ) : (
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          {documents.map((doc, i) => (
            <motion.div key={doc.evidence_id || i} variants={fadeUp}>
              <EvidenceCard document={doc} />
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
