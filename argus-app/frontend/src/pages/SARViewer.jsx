import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import PageHeader from '@/components/shared/PageHeader';
import ErrorCard from '@/components/shared/ErrorCard';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import EmptyState from '@/components/shared/EmptyState';
import InvestigationListPanel from '@/components/sar/InvestigationListPanel';
import SARDocument from '@/components/sar/SARDocument';
import { useQuery } from '@/hooks/useQuery';
import { getInvestigations, getInvestigation } from '@/api/client';
import { FileText } from 'lucide-react';

export default function SARViewer() {
  const [searchParams] = useSearchParams();
  const [selectedCaseId, setSelectedCaseId] = useState(searchParams.get('case_id') || null);

  const { data: investigations, loading, error, refetch } = useQuery(
    'investigations', getInvestigations
  );

  const { data: selectedInvestigation, loading: detailLoading } = useQuery(
    selectedCaseId ? `investigation-${selectedCaseId}` : null,
    () => getInvestigation(selectedCaseId),
    { enabled: !!selectedCaseId }
  );

  // Auto-select from URL param
  useEffect(() => {
    const caseId = searchParams.get('case_id');
    if (caseId) setSelectedCaseId(caseId);
  }, [searchParams]);

  if (loading) {
    return (
      <div>
        <PageHeader title="SAR Viewer" subtitle="Dual-jurisdiction regulatory reports" />
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size={32} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="SAR Viewer" subtitle="Dual-jurisdiction regulatory reports" />
        <ErrorCard error={error} onRetry={refetch} />
      </div>
    );
  }

  const investigationList = investigations?.investigations || investigations || [];
  const sarInvestigations = investigationList.filter(inv => inv.sar_narrative || inv.sar_draft);

  if (sarInvestigations.length === 0) {
    return (
      <div>
        <PageHeader title="SAR Viewer" subtitle="Dual-jurisdiction regulatory reports" />
        <EmptyState
          icon={FileText}
          title="No SAR Reports"
          description="Run an investigation to generate a Suspicious Activity Report."
          action={
            <Link to="/investigate"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover transition-colors">
              Go to Investigation Console
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="SAR Viewer" subtitle="Dual-jurisdiction regulatory reports" />
      <div className="flex h-[calc(100vh-180px)] bg-surface-0 rounded-card border border-surface-3 overflow-hidden">
        <InvestigationListPanel
          investigations={sarInvestigations}
          selectedId={selectedCaseId}
          onSelect={setSelectedCaseId}
        />
        <div className="flex-1 overflow-y-auto p-6">
          {selectedCaseId && detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <LoadingSpinner size={32} />
            </div>
          ) : selectedInvestigation ? (
            <SARDocument investigation={selectedInvestigation} />
          ) : (
            <div className="flex items-center justify-center h-full text-text-3">
              <p className="text-sm">Select a report from the sidebar</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
