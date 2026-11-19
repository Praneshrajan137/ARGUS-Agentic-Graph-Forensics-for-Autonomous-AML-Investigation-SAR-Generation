import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, FolderOpen, Plus, ArrowRight } from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import { useQuery, invalidateQueries } from '@/hooks/useQuery';
import { getCases, getDatasets, createCase } from '@/api/client';

export default function CaseQueue() {
  const { data: caseData, loading, error, refetch } = useQuery('prod-cases', getCases);
  const { data: dsData } = useQuery('prod-datasets', getDatasets);

  const [datasetId, setDatasetId] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [title, setTitle] = useState('');
  const [formError, setFormError] = useState(null);

  const datasets = dsData?.datasets || [];
  const activeDsId = datasetId || datasets[0]?.id || '';
  const cases = caseData?.cases || [];

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError(null);
    try {
      await createCase({ dataset_id: activeDsId, subject_id: subjectId.trim(), title: title.trim() });
      setSubjectId('');
      setTitle('');
      invalidateQueries('prod-cases');
      await refetch();
    } catch (err) {
      setFormError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Case Queue"
        subtitle="Assigned investigations pinned to immutable evidence snapshots"
      />

      <GlowCard className="p-6">
        <h2 className="font-display text-xl text-text-0 mb-3">Open New Scoped Case</h2>
        <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div>
            <label className="block text-xs font-semibold uppercase text-text-2 mb-1" htmlFor="case-ds">Dataset</label>
            <select
              id="case-ds"
              value={activeDsId}
              onChange={(e) => setDatasetId(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-surface-0 border border-surface-3 rounded-btn"
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>{d.name} (gen {d.generation})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-text-2 mb-1" htmlFor="case-subject">Subject Account / Entity ID</label>
            <input
              id="case-subject"
              type="text"
              required
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              placeholder="e.g. 002 or E1"
              className="w-full px-3 py-2 font-mono text-sm bg-surface-0 border border-surface-3 rounded-btn"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-text-2 mb-1" htmlFor="case-title">Case Title</label>
            <input
              id="case-title"
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Scoped review title"
              className="w-full px-3 py-2 text-sm bg-surface-0 border border-surface-3 rounded-btn"
            />
          </div>
          <button
            type="submit"
            disabled={!activeDsId}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover disabled:opacity-50"
          >
            <Plus className="w-4 h-4" aria-hidden="true" /> Open Case
          </button>
        </form>
        {formError && (
          <p role="alert" className="mt-3 text-xs font-mono text-rose-700">{formError}</p>
        )}
      </GlowCard>

      <GlowCard className="p-6">
        <h2 className="font-display text-xl text-text-0 mb-4">Assigned Cases ({cases.length})</h2>
        {loading && <p className="text-sm text-text-2">Loading cases...</p>}
        {error && <p role="alert" className="text-sm text-rose-700">{error.message}</p>}
        {!loading && cases.length === 0 && (
          <div className="py-8 text-center text-text-2 text-sm flex flex-col items-center gap-2">
            <FolderOpen className="w-8 h-8 text-text-3" aria-hidden="true" />
            <p>No cases assigned yet. Import a batch and open a case above.</p>
          </div>
        )}
        {cases.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-surface-3 text-text-2 uppercase">
                  <th className="py-2 pr-4">Case</th>
                  <th className="py-2 pr-4">Subject</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Evidence Freshness</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id} className="border-b border-surface-2">
                    <td className="py-3 pr-4">
                      <div className="font-semibold text-text-0">{c.title}</div>
                      <div className="font-mono text-[11px] text-text-3">{c.id}</div>
                    </td>
                    <td className="py-3 pr-4 font-mono text-text-0">{c.subject_id}</td>
                    <td className="py-3 pr-4">
                      <span className="px-2 py-0.5 rounded-badge bg-surface-2 text-text-0 font-mono font-semibold">
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      {c.evidence_stale ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-badge bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
                          <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
                          Stale (pinned gen {c.snapshot_generation}, current gen {c.current_dataset_generation})
                        </span>
                      ) : (
                        <span className="font-mono text-text-2">Current (gen {c.snapshot_generation})</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 flex items-center gap-2">
                      <Link
                        to={`/cases/${c.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 bg-accent text-white rounded-btn font-semibold hover:bg-accent-hover"
                      >
                        Workspace <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
                      </Link>
                      <Link
                        to={`/cases/${c.id}/review`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 bg-surface-1 border border-surface-3 text-text-0 rounded-btn font-semibold hover:bg-surface-2"
                      >
                        Review & Export
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlowCard>
    </div>
  );
}
