import { useState } from 'react';
import { Upload, CheckCircle2, AlertTriangle, HelpCircle, Plus } from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import { useQuery, invalidateQueries } from '@/hooks/useQuery';
import { getDatasets, createDataset, getDatasetImports, uploadImportBatch } from '@/api/client';

const RECON_META = {
  RECONCILED: {
    label: 'RECONCILED to declared independent controls',
    className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    icon: CheckCircle2,
  },
  MISMATCH: {
    label: 'MISMATCH against upstream controls',
    className: 'bg-rose-50 text-rose-800 border-rose-200',
    icon: AlertTriangle,
  },
  UNVERIFIED: {
    label: 'UNVERIFIED — no compatible independent controls supplied',
    className: 'bg-amber-50 text-amber-800 border-amber-200',
    icon: HelpCircle,
  },
};

export function ReconciliationBadge({ reconciliation }) {
  const status = reconciliation?.status || 'UNVERIFIED';
  const cfg = RECON_META[status] || RECON_META.UNVERIFIED;
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-badge text-xs font-semibold border ${cfg.className}`}
      data-testid="reconciliation-badge"
    >
      <Icon className="w-3.5 h-3.5" aria-hidden="true" />
      {cfg.label}
    </span>
  );
}

export default function ImportReconcile() {
  const { data: dsData, refetch: refetchDatasets } = useQuery('prod-datasets', getDatasets);
  const datasets = dsData?.datasets || [];
  const [selectedDsId, setSelectedDsId] = useState('');
  const activeDs = datasets.find((d) => d.id === selectedDsId) || datasets[0] || null;

  const { data: importsData, refetch: refetchImports } = useQuery(
    activeDs ? `prod-imports-${activeDs.id}` : null,
    (opts) => getDatasetImports(activeDs.id, opts),
    { enabled: Boolean(activeDs) }
  );

  const [newName, setNewName] = useState('');
  const [newNamespace, setNewNamespace] = useState('');
  const [filesMap, setFilesMap] = useState({});
  const [controlsJson, setControlsJson] = useState('');
  const [idempotencyKey, setIdempotencyKey] = useState(() => `import-${Date.now()}`);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [error, setError] = useState(null);

  const handleCreateDataset = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const created = await createDataset({ name: newName.trim(), namespace: newNamespace.trim() });
      setNewName('');
      setNewNamespace('');
      setSelectedDsId(created.id);
      invalidateQueries('prod-datasets');
      await refetchDatasets();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!activeDs) return;
    setSubmitting(true);
    setError(null);
    setFeedback(null);
    try {
      const fd = new FormData();
      fd.append('expected_generation', String(activeDs.generation));
      if (controlsJson.trim()) fd.append('controls_json', controlsJson.trim());
      for (const kind of ['entities', 'accounts', 'relationships', 'transactions']) {
        if (filesMap[kind]) fd.append(kind, filesMap[kind]);
      }
      const res = await uploadImportBatch(activeDs.id, fd, idempotencyKey.trim());
      setFeedback(res);
      setIdempotencyKey(`import-${Date.now()}`);
      invalidateQueries('prod-datasets');
      invalidateQueries(`prod-imports-${activeDs.id}`);
      await refetchDatasets();
      await refetchImports();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Import & Reconcile"
        subtitle="Controlled canonical CSV intake with independent upstream reconciliation"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlowCard className="p-6 space-y-4">
          <h2 className="font-display text-xl text-text-0">1. Dataset Scope</h2>
          <label className="block text-xs font-semibold text-text-2 uppercase" htmlFor="dataset-select">
            Active Dataset
          </label>
          <select
            id="dataset-select"
            value={activeDs?.id || ''}
            onChange={(e) => setSelectedDsId(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-surface-0 border border-surface-3 rounded-btn"
          >
            {datasets.length === 0 && <option value="">No datasets yet</option>}
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.namespace}) — gen {d.generation}
              </option>
            ))}
          </select>

          <form onSubmit={handleCreateDataset} className="pt-4 border-t border-surface-3 space-y-3">
            <h3 className="text-xs font-semibold text-text-2 uppercase">Create New Dataset</h3>
            <input
              type="text"
              placeholder="Display name (e.g. Core Checking)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm bg-surface-0 border border-surface-3 rounded-btn"
            />
            <input
              type="text"
              placeholder="Source namespace (e.g. us_core_bank)"
              value={newNamespace}
              onChange={(e) => setNewNamespace(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm font-mono bg-surface-0 border border-surface-3 rounded-btn"
            />
            <button
              type="submit"
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 bg-surface-1 border border-surface-3 rounded-btn text-sm font-semibold hover:bg-surface-2"
            >
              <Plus className="w-4 h-4" aria-hidden="true" /> Create Dataset
            </button>
          </form>
        </GlowCard>

        <GlowCard className="p-6 lg:col-span-2 space-y-4">
          <h2 className="font-display text-xl text-text-0">2. Canonical CSV Batch Upload</h2>
          <p className="text-xs text-text-2">
            Byte hashes verify file identity only, not completeness. Supply independent upstream control metadata
            to evaluate RECONCILED vs MISMATCH; missing controls remain explicitly UNVERIFIED.
          </p>

          <form onSubmit={handleUpload} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {['entities', 'accounts', 'relationships', 'transactions'].map((kind) => (
                <div key={kind} className="p-3 bg-surface-1 rounded-lg border border-surface-3">
                  <label className="block text-xs font-semibold uppercase text-text-1 mb-1" htmlFor={`csv-${kind}`}>
                    {kind}.csv
                  </label>
                  <input
                    id={`csv-${kind}`}
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => setFilesMap((prev) => ({ ...prev, [kind]: e.target.files?.[0] || null }))}
                    className="text-xs w-full"
                  />
                </div>
              ))}
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-text-2 mb-1" htmlFor="controls-json">
                Independent Upstream Controls JSON (optional)
              </label>
              <textarea
                id="controls-json"
                rows={4}
                value={controlsJson}
                onChange={(e) => setControlsJson(e.target.value)}
                placeholder='{"declaration": {...}, "upstream": {"origin": "INDEPENDENT_UPSTREAM", ...}}'
                className="w-full px-3 py-2 font-mono text-xs bg-surface-0 border border-surface-3 rounded-btn"
              />
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-semibold uppercase text-text-2 mb-1" htmlFor="idem-key">
                  Idempotency Key
                </label>
                <input
                  id="idem-key"
                  type="text"
                  value={idempotencyKey}
                  onChange={(e) => setIdempotencyKey(e.target.value)}
                  required
                  className="w-full px-3 py-2 font-mono text-xs bg-surface-0 border border-surface-3 rounded-btn"
                />
              </div>
              <button
                type="submit"
                disabled={!activeDs || submitting}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover disabled:opacity-50"
              >
                <Upload className="w-4 h-4" aria-hidden="true" />
                {submitting ? 'Validating & Activating...' : `Activate Batch (from gen ${activeDs?.generation ?? 0})`}
              </button>
            </div>
          </form>

          {error && (
            <div role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs font-mono text-rose-800">
              {error}
            </div>
          )}

          {feedback && (
            <div className="p-4 bg-surface-1 border border-surface-3 rounded-lg space-y-2" data-testid="import-result">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="font-mono text-xs font-bold text-text-0">
                  Activated Generation {feedback.generation} · Snapshot {feedback.snapshot_id}
                </span>
                <ReconciliationBadge reconciliation={feedback.reconciliation} />
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div>Raw rows: {feedback.reconciliation?.observed?.raw_row_count ?? 0}</div>
                <div>Normalized events: {feedback.reconciliation?.observed?.normalized_event_count ?? 0}</div>
                <div>Eligible: {feedback.reconciliation?.observed?.analysis_eligible_count ?? 0}</div>
                <div>Excluded: {feedback.reconciliation?.observed?.excluded_count ?? 0}</div>
              </div>
            </div>
          )}
        </GlowCard>
      </div>

      <GlowCard className="p-6">
        <h2 className="font-display text-xl text-text-0 mb-4">Activated Batch History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-surface-3 text-text-2 uppercase">
                <th className="py-2 pr-4">Batch</th>
                <th className="py-2 pr-4">Parent Gen</th>
                <th className="py-2 pr-4">Reconciliation</th>
                <th className="py-2 pr-4">Raw / Normalized</th>
                <th className="py-2 pr-4">Schema / Transform</th>
              </tr>
            </thead>
            <tbody>
              {(importsData?.imports || []).map((imp) => (
                <tr key={imp.id} className="border-b border-surface-2">
                  <td className="py-2.5 pr-4 font-mono">{imp.id.slice(0, 12)}</td>
                  <td className="py-2.5 pr-4 font-mono">{imp.parent_generation}</td>
                  <td className="py-2.5 pr-4">
                    <ReconciliationBadge reconciliation={imp.reconciliation} />
                  </td>
                  <td className="py-2.5 pr-4 font-mono">
                    {imp.reconciliation?.observed?.raw_row_count ?? 0} / {imp.reconciliation?.observed?.normalized_event_count ?? 0}
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-text-2">
                    {imp.schema_version} · {imp.transformation_version}
                  </td>
                </tr>
              ))}
              {(importsData?.imports || []).length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-text-3">No activated imports for this dataset yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </GlowCard>
    </div>
  );
}
