import { useState, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  AlertTriangle, Play, XCircle, FileText, Eye, Scale, HelpCircle, Table2,
} from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import ProvenanceDrawer from '@/components/workbench/ProvenanceDrawer';
import { ReconciliationBadge } from '@/pages/ImportReconcile';
import { useQuery, invalidateQueries } from '@/hooks/useQuery';
import { usePolling } from '@/hooks/usePolling';
import {
  getCase, getCaseRecords, enqueueCaseAnalysis, getJobStatus, cancelJob,
  addFindingDisposition, addCaseObservation,
} from '@/api/client';

/**
 * Challenge-first Case Workspace.
 * Visibly separates three concepts:
 *   1. Observed Facts (pinned ledger records + source file hash/row ordinal)
 *   2. Inferences (uncalibrated heuristic findings + raw findings preserved when dismissed)
 *   3. Unresolved Questions (exclusions, disagreements, reconciliation limits, stale evidence)
 */
export default function CaseWorkspace() {
  const { caseId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeJobId = searchParams.get('job_id') || null;

  const { data: caseData, loading, error, refetch } = useQuery(
    caseId ? `prod-case-${caseId}` : null,
    (opts) => getCase(caseId, opts),
    { enabled: Boolean(caseId) }
  );

  const { data: recordsData } = useQuery(
    caseId ? `prod-case-records-${caseId}` : null,
    (opts) => getCaseRecords(caseId, null, opts),
    { enabled: Boolean(caseId) }
  );

  const [hopDepth, setHopDepth] = useState(3);
  const [drawerRecord, setDrawerRecord] = useState(null);
  const [highlightedEventId, setHighlightedEventId] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Disposition form state per finding
  const [dispTarget, setDispTarget] = useState(null);
  const [dispStatus, setDispStatus] = useState('DISMISSED');
  const [dispRationale, setDispRationale] = useState('');
  const [dispBenign, setDispBenign] = useState('');

  // Scoped observation form state
  const [obsRef, setObsRef] = useState('');
  const [obsText, setObsText] = useState('');

  const latestJob = caseData?.jobs?.[0] || null;
  const pollJobId = activeJobId || (latestJob && !['COMPLETE', 'FAILED', 'CANCELLED'].includes(latestJob.status) ? latestJob.id : null);

  const { data: polledJob, networkWarning, polling } = usePolling(
    (opts) => getJobStatus(pollJobId, opts),
    {
      enabled: Boolean(pollJobId),
      isTerminal: (j) => ['COMPLETE', 'FAILED', 'CANCELLED'].includes(j?.status),
      onTerminal: () => {
        invalidateQueries(`prod-case-${caseId}`);
        refetch();
      },
    }
  );

  const recordsByEvent = useMemo(() => {
    const map = {};
    for (const r of recordsData?.records || []) {
      map[r.external_id] = r;
    }
    return map;
  }, [recordsData]);

  const analysisResult = polledJob?.result || latestJob?.result || null;
  const findings = analysisResult?.findings || [];
  const coverage = analysisResult?.coverage || null;
  const dispositionsByFinding = useMemo(() => {
    const map = {};
    for (const d of caseData?.dispositions || []) {
      if (!map[d.finding_id]) map[d.finding_id] = [];
      map[d.finding_id].push(d);
    }
    return map;
  }, [caseData]);

  const openCitation = (eventId) => {
    const rec = recordsByEvent[eventId] || {
      external_id: eventId,
      record_id: 'Lookup from pinned snapshot',
      source_file_id: 'pinned',
      row_number: 'n/a',
      digest: 'n/a',
      payload: { event_id: eventId },
    };
    setDrawerRecord(rec);
  };

  const handleJumpToRow = (eventId) => {
    setHighlightedEventId(eventId);
    setDrawerRecord(null);
    const el = document.getElementById(`ledger-row-${eventId}`);
    el?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
  };

  const handleRunAnalysis = async () => {
    setActionError(null);
    try {
      const resp = await enqueueCaseAnalysis(
        caseId,
        { hop_depth: hopDepth },
        `analyze-${caseId}-${Date.now()}`
      );
      setSearchParams({ job_id: resp.job_id });
      invalidateQueries(`prod-case-${caseId}`);
      refetch();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleCancelJob = async () => {
    if (!pollJobId) return;
    try {
      await cancelJob(pollJobId);
      refetch();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleSaveDisposition = async (e) => {
    e.preventDefault();
    if (!dispTarget) return;
    setActionError(null);
    try {
      await addFindingDisposition(caseId, {
        finding_id: dispTarget,
        disposition: dispStatus,
        rationale: dispRationale,
        benign_alternative: dispBenign || null,
        job_id: latestJob?.id || null,
      });
      setDispTarget(null);
      setDispRationale('');
      setDispBenign('');
      invalidateQueries(`prod-case-${caseId}`);
      await refetch();
    } catch (err) {
      setActionError(err.message);
    }
  };

  const handleAddObservation = async (e) => {
    e.preventDefault();
    setActionError(null);
    try {
      await addCaseObservation(caseId, {
        source_kind: 'ANALYST_NOTE',
        source_ref: obsRef.trim(),
        raw_text: obsText.trim(),
      });
      setObsRef('');
      setObsText('');
      invalidateQueries(`prod-case-${caseId}`);
      await refetch();
    } catch (err) {
      setActionError(err.message);
    }
  };

  if (loading) return <p className="text-sm text-text-2">Loading pinned case workspace...</p>;
  if (error) return <div role="alert" className="p-4 bg-rose-50 text-rose-800 rounded-card">{error.message}</div>;
  if (!caseData) return null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title={caseData.title}
          subtitle={`Case ${caseData.id} · Subject ${caseData.subject_id} · Pinned snapshot gen ${caseData.snapshot_generation}`}
        />
        <div className="flex items-center gap-2">
          <Link
            to={`/cases/${caseId}/review`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover"
          >
            <FileText className="w-4 h-4" aria-hidden="true" /> Narrative & Review
          </Link>
        </div>
      </div>

      {/* Stale Evidence Warning */}
      {caseData.evidence_stale && (
        <div
          role="alert"
          data-testid="stale-evidence-banner"
          className="p-4 rounded-card bg-amber-50 border border-amber-300 text-amber-900 text-sm flex items-start gap-3"
        >
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <strong>Newer evidence exists in this dataset.</strong> This case is pinned to generation{' '}
            <span className="font-mono font-bold">{caseData.snapshot_generation}</span>, while the dataset is now at
            generation <span className="font-mono font-bold">{caseData.current_dataset_generation}</span>. Current
            approval and export require refreshing to the latest generation and re-reviewing.
          </div>
        </div>
      )}

      {/* Analysis Control Bar */}
      <GlowCard className="p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-semibold uppercase text-text-2" htmlFor="hop-depth">Hop Depth</label>
          <input
            id="hop-depth"
            type="number"
            min={1}
            max={6}
            value={hopDepth}
            onChange={(e) => setHopDepth(Number(e.target.value))}
            className="w-16 px-2 py-1.5 font-mono text-sm border border-surface-3 rounded-btn bg-surface-0"
          />
          <button
            type="button"
            onClick={handleRunAnalysis}
            disabled={polling}
            className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover disabled:opacity-50"
          >
            <Play className="w-4 h-4" aria-hidden="true" />
            {polling ? `Running (${polledJob?.status || 'QUEUED'})...` : 'Run Scoped Analysis (202 Durable)'}
          </button>
          {polling && (
            <button
              type="button"
              onClick={handleCancelJob}
              className="inline-flex items-center gap-1.5 px-3 py-2 bg-rose-50 text-rose-700 border border-rose-200 rounded-btn text-xs font-semibold"
            >
              <XCircle className="w-4 h-4" aria-hidden="true" /> Cancel Job
            </button>
          )}
        </div>
        <ReconciliationBadge reconciliation={caseData.reconciliation} />
      </GlowCard>

      {networkWarning && (
        <div role="status" data-testid="network-warning" className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
          {networkWarning}
        </div>
      )}
      {actionError && (
        <div role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs font-mono text-rose-800">
          {actionError}
        </div>
      )}

      {/* ═══ THREE VISIBLY SEPARATED CONCEPTS ═══ */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* 1. OBSERVED FACTS */}
        <GlowCard className="p-5 space-y-4" data-testid="section-observed-facts">
          <div className="flex items-center gap-2 border-b border-surface-3 pb-3">
            <Table2 className="w-5 h-5 text-accent" aria-hidden="true" />
            <div>
              <h2 className="font-display text-xl text-text-0">Observed Facts</h2>
              <p className="text-xs text-text-2">Pinned source records (accessible table equivalent)</p>
            </div>
          </div>

          <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
            <table className="w-full text-left text-xs border-collapse" aria-label="Observed ledger transactions">
              <thead>
                <tr className="border-b border-surface-3 text-text-2 uppercase">
                  <th className="py-2 pr-2">Event ID</th>
                  <th className="py-2 pr-2">Amount</th>
                  <th className="py-2 pr-2">Type</th>
                  <th className="py-2">Row</th>
                </tr>
              </thead>
              <tbody>
                {(recordsData?.records || []).map((rec) => (
                  <tr
                    key={rec.record_id}
                    id={`ledger-row-${rec.external_id}`}
                    className={`border-b border-surface-2 ${highlightedEventId === rec.external_id ? 'bg-accent-tint' : ''}`}
                  >
                    <td className="py-2 pr-2 font-mono">
                      <button
                        type="button"
                        onClick={() => openCitation(rec.external_id)}
                        className="text-accent underline font-semibold text-left"
                      >
                        {rec.external_id}
                      </button>
                    </td>
                    <td className="py-2 pr-2 font-mono font-bold text-text-0">
                      {rec.payload?.currency} {rec.payload?.amount}
                    </td>
                    <td className="py-2 pr-2 font-mono text-text-2">{rec.payload?.event_type}</td>
                    <td className="py-2 font-mono text-text-3">#{rec.row_number}</td>
                  </tr>
                ))}
                {(recordsData?.records || []).length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-text-3">No transaction rows in pinned scope.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </GlowCard>

        {/* 2. INFERENCES (UNCALIBRATED HEURISTICS + DISPOSITIONS) */}
        <GlowCard className="p-5 space-y-4" data-testid="section-inferences">
          <div className="flex items-center gap-2 border-b border-surface-3 pb-3">
            <Scale className="w-5 h-5 text-amber-600" aria-hidden="true" />
            <div>
              <h2 className="font-display text-xl text-text-0">Inferences (Uncalibrated)</h2>
              <p className="text-xs text-text-2">Heuristic priorities — not probabilities or filing decisions</p>
            </div>
          </div>

          {coverage && (
            <div className="p-3 rounded-lg bg-surface-1 border border-surface-3 text-xs space-y-1" data-testid="workspace-coverage">
              <div className="font-semibold text-text-0">
                Analysis Coverage: <span className="font-mono">{coverage.status}</span>
              </div>
              <div className="font-mono text-text-2">
                Considered: {coverage.considered_events} · Excluded: {coverage.excluded_events_count} · Accounts: {coverage.scoped_accounts_count}
              </div>
              <p className="text-[11px] text-text-2">{coverage.negative_scope_notice}</p>
            </div>
          )}

          {findings.length === 0 ? (
            <p className="text-xs text-text-2 p-3 bg-surface-1 rounded-lg">
              No qualifying pattern found within this declared scope. This does not clear a customer.
            </p>
          ) : (
            <div className="space-y-3">
              {findings.map((f) => {
                const disps = dispositionsByFinding[f.finding_id] || [];
                const latestDisp = disps[0] || null;
                return (
                  <div
                    key={f.finding_id}
                    data-testid={`finding-card-${f.finding_id}`}
                    className="p-4 rounded-lg border border-surface-3 bg-surface-1 space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-text-0">
                        {f.typology} ({f.channel}/{f.mode})
                      </span>
                      <span className="font-mono text-[11px] text-text-2">
                        Priority (uncalibrated): {f.uncalibrated_priority_score}
                      </span>
                    </div>
                    <div className="text-xs font-mono text-text-1">
                      Total: <strong>{f.currency} {f.total_amount}</strong> across {f.event_count} event(s)
                    </div>
                    <p className="text-xs text-text-2">{f.reasoning}</p>

                    {/* Clickable 1-click provenance citations */}
                    <div className="flex flex-wrap gap-1 pt-1">
                      {(f.cited_event_ids || []).map((eid) => (
                        <button
                          key={eid}
                          type="button"
                          onClick={() => openCitation(eid)}
                          data-testid={`cite-${eid}`}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-badge bg-surface-0 border border-surface-3 font-mono text-[11px] text-accent hover:bg-accent-tint"
                        >
                          <Eye className="w-3 h-3" aria-hidden="true" /> {eid}
                        </button>
                      ))}
                    </div>

                    {/* Human disposition kept SEPARATE from raw finding */}
                    {latestDisp && (
                      <div
                        data-testid={`disposition-${f.finding_id}`}
                        className="p-2.5 rounded bg-surface-0 border border-surface-3 text-xs space-y-1"
                      >
                        <div className="font-semibold text-text-0">
                          Human Disposition: <span className="font-mono">{latestDisp.disposition}</span>
                          <span className="text-[11px] font-normal text-text-3 ml-2">(Raw finding preserved)</span>
                        </div>
                        <p className="text-text-1">{latestDisp.rationale}</p>
                        {latestDisp.benign_alternative && (
                          <p className="text-text-2">Benign alternative: {latestDisp.benign_alternative}</p>
                        )}
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => setDispTarget(f.finding_id)}
                      className="text-xs font-semibold text-accent underline"
                    >
                      Record / Update Human Disposition
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {dispTarget && (
            <form onSubmit={handleSaveDisposition} className="p-4 rounded-lg border border-accent bg-surface-0 space-y-2.5">
              <h3 className="text-xs font-bold uppercase text-text-0">
                Disposition for Finding {dispTarget} (Raw finding remains intact)
              </h3>
              <select
                value={dispStatus}
                onChange={(e) => setDispStatus(e.target.value)}
                aria-label="Disposition status"
                className="w-full px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn"
              >
                <option value="OPEN">OPEN</option>
                <option value="ESCALATED">ESCALATED</option>
                <option value="DISMISSED">DISMISSED (preserve raw finding)</option>
                <option value="NEEDS_INFO">NEEDS_INFO</option>
              </select>
              <textarea
                rows={2}
                required
                placeholder="Disposition rationale (required)"
                value={dispRationale}
                onChange={(e) => setDispRationale(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn"
              />
              <textarea
                rows={2}
                placeholder="Benign alternative explanation (optional)"
                value={dispBenign}
                onChange={(e) => setDispBenign(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn"
              />
              <div className="flex gap-2">
                <button type="submit" className="px-3 py-1.5 bg-accent text-white text-xs font-semibold rounded-btn">
                  Save Disposition
                </button>
                <button type="button" onClick={() => setDispTarget(null)} className="px-3 py-1.5 border border-surface-3 text-xs rounded-btn">
                  Cancel
                </button>
              </div>
            </form>
          )}
        </GlowCard>

        {/* 3. UNRESOLVED QUESTIONS (EXCLUSIONS, OBSERVATIONS, DISAGREEMENTS) */}
        <GlowCard className="p-5 space-y-4" data-testid="section-unresolved-questions">
          <div className="flex items-center gap-2 border-b border-surface-3 pb-3">
            <HelpCircle className="w-5 h-5 text-cyan-600" aria-hidden="true" />
            <div>
              <h2 className="font-display text-xl text-text-0">Unresolved Questions</h2>
              <p className="text-xs text-text-2">Excluded records, text disagreements & missing evidence</p>
            </div>
          </div>

          {/* Excluded records breakdown */}
          <div className="p-3 bg-surface-1 rounded-lg border border-surface-3 space-y-2">
            <h3 className="text-xs font-semibold uppercase text-text-1">Analysis Exclusions</h3>
            {coverage?.excluded_breakdown && Object.keys(coverage.excluded_breakdown).length > 0 ? (
              <ul className="space-y-1 text-xs font-mono">
                {Object.entries(coverage.excluded_breakdown).map(([reason, count]) => (
                  <li key={reason} className="flex justify-between">
                    <span className="text-text-2">{reason}</span>
                    <span className="font-bold text-text-0">{count}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-text-3">No excluded records reported in current analysis.</p>
            )}
          </div>

          {/* Scoped observations & disagreements */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase text-text-1">Scoped Observations & Comparisons</h3>
            {(caseData.observations || []).map((obs) => (
              <div key={obs.id} className="p-3 rounded-lg bg-surface-1 border border-surface-3 text-xs space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-text-0">{obs.source_ref}</span>
                  <span className="px-2 py-0.5 rounded-badge bg-amber-50 text-amber-800 font-mono text-[10px]">
                    {obs.comparison?.verdict || 'UNSCOPED'}
                  </span>
                </div>
                <p className="text-text-1">{obs.raw_text}</p>
                <p className="text-[11px] text-text-3">
                  {obs.comparison?.interpretation_notice || 'Disagreement is a question to investigate, not proof of deception.'}
                </p>
              </div>
            ))}

            <form onSubmit={handleAddObservation} className="pt-3 border-t border-surface-3 space-y-2">
              <input
                type="text"
                required
                placeholder="Source reference (e.g. teller-note-04)"
                value={obsRef}
                onChange={(e) => setObsRef(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs font-mono border border-surface-3 rounded-btn"
              />
              <textarea
                rows={2}
                required
                placeholder="Record literal unstructured observation (never parsed as instructions)..."
                value={obsText}
                onChange={(e) => setObsText(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn"
              />
              <button type="submit" className="px-3 py-1.5 bg-surface-1 border border-surface-3 text-xs font-semibold rounded-btn hover:bg-surface-2">
                Add Observation
              </button>
            </form>
          </div>
        </GlowCard>
      </div>

      <ProvenanceDrawer
        record={drawerRecord}
        onClose={() => setDrawerRecord(null)}
        onJumpToRow={handleJumpToRow}
      />
    </div>
  );
}
