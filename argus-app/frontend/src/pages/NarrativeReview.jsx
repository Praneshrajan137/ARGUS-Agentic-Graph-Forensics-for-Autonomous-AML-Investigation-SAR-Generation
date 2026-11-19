import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  AlertTriangle, CheckCircle2, Download, Eye, GitCompare, Lock, MessageSquare, ArrowLeft,
} from 'lucide-react';
import PageHeader from '@/components/shared/PageHeader';
import GlowCard from '@/components/shared/GlowCard';
import ProvenanceDrawer from '@/components/workbench/ProvenanceDrawer';
import { useQuery, invalidateQueries } from '@/hooks/useQuery';
import {
  getCase, getArtifact, createCaseArtifact, freezeArtifact, reviewArtifact,
  exportArtifact, closeCase, addCaseComment,
} from '@/api/client';

/** Line-by-line deterministic diff between two narrative revisions. */
function computeLineDiff(oldText, newText) {
  const a = (oldText || '').split('\n');
  const b = (newText || '').split('\n');
  const max = Math.max(a.length, b.length);
  const rows = [];
  for (let i = 0; i < max; i += 1) {
    if (a[i] === b[i]) {
      rows.push({ kind: 'same', left: a[i] ?? '', right: b[i] ?? '' });
    } else {
      rows.push({ kind: 'changed', left: a[i] ?? '', right: b[i] ?? '' });
    }
  }
  return rows;
}

export default function NarrativeReview() {
  const { caseId } = useParams();
  const { data: caseData, refetch: refetchCase } = useQuery(
    caseId ? `prod-case-${caseId}` : null,
    (opts) => getCase(caseId, opts),
    { enabled: Boolean(caseId) }
  );

  const artifacts = caseData?.artifacts || [];
  const [selectedArtifactId, setSelectedArtifactId] = useState(null);
  const [compareArtifactId, setCompareArtifactId] = useState(null);
  const activeArtifactId = selectedArtifactId || artifacts[0]?.id || null;

  const { data: artifact, refetch: refetchArtifact } = useQuery(
    activeArtifactId ? `prod-artifact-${activeArtifactId}` : null,
    (opts) => getArtifact(activeArtifactId, opts),
    { enabled: Boolean(activeArtifactId) }
  );

  const { data: compareArtifact } = useQuery(
    compareArtifactId ? `prod-artifact-${compareArtifactId}` : null,
    (opts) => getArtifact(compareArtifactId, opts),
    { enabled: Boolean(compareArtifactId) }
  );

  const [interpretationText, setInterpretationText] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [commentBody, setCommentBody] = useState('');
  const [closureMemo, setClosureMemo] = useState('');
  const [drawerRecord, setDrawerRecord] = useState(null);
  const [exportedPkg, setExportedPkg] = useState(null);
  const [error, setError] = useState(null);

  const citedByEvent = useMemo(() => {
    const map = {};
    for (const r of artifact?.manifest?.cited_records || []) {
      if (r.kind === 'transactions') {
        const sf = (artifact?.manifest?.source_files || []).find((s) => s.source_file_id === r.source_file_id);
        map[r.external_id] = {
          ...r,
          source_file_sha256: sf?.sha256,
          source_filename: sf?.filename,
        };
      }
    }
    return map;
  }, [artifact]);

  const diffRows = useMemo(() => {
    if (!compareArtifact || !artifact) return null;
    return computeLineDiff(compareArtifact.narrative, artifact.narrative);
  }, [compareArtifact, artifact]);

  const refreshAll = async () => {
    invalidateQueries(`prod-case-${caseId}`);
    if (activeArtifactId) invalidateQueries(`prod-artifact-${activeArtifactId}`);
    await refetchCase();
    if (activeArtifactId) await refetchArtifact();
  };

  const handleCreateDraft = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const created = await createCaseArtifact(caseId, {
        analyst_interpretations: interpretationText.trim()
          ? [{ text: interpretationText.trim() }]
          : [],
        parent_artifact_id: activeArtifactId || null,
      });
      setInterpretationText('');
      setSelectedArtifactId(created.id);
      await refreshAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleFreeze = async () => {
    if (!activeArtifactId) return;
    setError(null);
    try {
      await freezeArtifact(activeArtifactId);
      await refreshAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleReview = async (decision) => {
    if (!activeArtifactId) return;
    setError(null);
    try {
      await reviewArtifact(activeArtifactId, { decision, review_note: reviewNote || null });
      setReviewNote('');
      await refreshAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleExport = async (allowHistorical = false) => {
    if (!activeArtifactId) return;
    setError(null);
    try {
      const pkg = await exportArtifact(activeArtifactId, { allow_historical: allowHistorical });
      setExportedPkg(pkg);
      await refreshAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCloseCase = async () => {
    setError(null);
    try {
      await closeCase(caseId, { closed_reason: 'NO_FILING_WARRANTED', closure_memo: closureMemo || null });
      await refreshAll();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleAddComment = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await addCaseComment(caseId, { body: commentBody, artifact_id: activeArtifactId });
      setCommentBody('');
      await refreshAll();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Narrative, Independent Review & Export"
          subtitle="Reviewed package — not filed. Approval binds exact frozen bytes, contributor ancestry, and snapshot freshness."
        />
        <Link
          to={`/cases/${caseId}`}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-surface-1 border border-surface-3 rounded-btn text-xs font-semibold text-text-0"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" /> Back to Case Workspace
        </Link>
      </div>

      {artifact?.evidence_stale && (
        <div role="alert" data-testid="review-stale-warning" className="p-4 bg-amber-50 border border-amber-300 rounded-card text-sm text-amber-900 flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <strong>Stale evidence warning:</strong> This revision cites snapshot generation{' '}
            <span className="font-mono font-bold">{artifact.snapshot_generation}</span>, while the dataset is now at
            generation <span className="font-mono font-bold">{artifact.current_dataset_generation}</span>. Current
            approval and current export are blocked; approved historical packages remain accessible only with an
            explicit historical label.
          </div>
        </div>
      )}

      {error && (
        <div role="alert" data-testid="review-error" className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs font-mono text-rose-800">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Revisions, New Draft, Comments */}
        <div className="space-y-6">
          <GlowCard className="p-5 space-y-3">
            <h2 className="font-display text-xl text-text-0">Revisions ({artifacts.length})</h2>
            <div className="space-y-2">
              {artifacts.map((a) => (
                <div
                  key={a.id}
                  className={`p-3 rounded-lg border text-xs flex items-center justify-between gap-2 ${
                    a.id === activeArtifactId ? 'border-accent bg-accent-tint/40' : 'border-surface-3 bg-surface-1'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedArtifactId(a.id)}
                    className="text-left flex-1"
                  >
                    <div className="font-mono font-bold text-text-0">Rev {a.revision_number} · {a.status}</div>
                    <div className="font-mono text-[10px] text-text-3 truncate">{a.payload_digest.slice(0, 20)}...</div>
                  </button>
                  {a.id !== activeArtifactId && (
                    <button
                      type="button"
                      onClick={() => setCompareArtifactId(a.id === compareArtifactId ? null : a.id)}
                      className="px-2 py-1 border border-surface-3 bg-surface-0 rounded text-[11px] inline-flex items-center gap-1"
                    >
                      <GitCompare className="w-3 h-3" aria-hidden="true" /> Diff
                    </button>
                  )}
                </div>
              ))}
            </div>

            <form onSubmit={handleCreateDraft} className="pt-3 border-t border-surface-3 space-y-2">
              <label className="block text-xs font-semibold uppercase text-text-2" htmlFor="interp-input">
                Analyst Interpretation (Human Judgment — creates new revision)
              </label>
              <textarea
                id="interp-input"
                rows={3}
                value={interpretationText}
                onChange={(e) => setInterpretationText(e.target.value)}
                placeholder="Optional human interpretation (clearly separated from observed facts)..."
                className="w-full px-2.5 py-2 text-xs border border-surface-3 rounded-btn bg-surface-0"
              />
              <button
                type="submit"
                className="w-full px-4 py-2 bg-accent text-white text-xs font-semibold rounded-btn hover:bg-accent-hover"
              >
                {artifacts.length > 0 ? 'Generate New Revision (DRAFT)' : 'Generate Deterministic Draft'}
              </button>
            </form>
          </GlowCard>

          <GlowCard className="p-5 space-y-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-text-2" aria-hidden="true" />
              <h2 className="font-display text-lg text-text-0">Review Comments</h2>
            </div>
            <p className="text-[11px] text-text-2">
              Comments alone do not add authorship to the contributor ancestry.
            </p>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {(caseData?.comments || []).map((cm) => (
                <div key={cm.id} className="p-2.5 bg-surface-1 rounded text-xs">
                  <div className="font-mono text-[10px] text-text-3">{cm.author_id}</div>
                  <p className="text-text-1 mt-0.5">{cm.body}</p>
                </div>
              ))}
            </div>
            <form onSubmit={handleAddComment} className="space-y-2">
              <input
                type="text"
                required
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
                placeholder="Add review question or comment..."
                className="w-full px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn"
              />
              <button type="submit" className="px-3 py-1.5 bg-surface-1 border border-surface-3 rounded-btn text-xs font-semibold">
                Post Comment
              </button>
            </form>
          </GlowCard>
        </div>

        {/* Right 2 columns: Frozen Narrative, Claims, Diff, Approval & Export */}
        <div className="lg:col-span-2 space-y-6">
          {artifact ? (
            <>
              <GlowCard className="p-6 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-surface-3 pb-3">
                  <div>
                    <h2 className="font-display text-2xl text-text-0">
                      Revision {artifact.revision_number} — {artifact.status}
                    </h2>
                    <p className="text-xs font-mono text-text-2 break-all">
                      Payload digest: {artifact.payload_digest}
                    </p>
                    <p className="text-xs font-mono text-text-3">
                      Material contributors: {(artifact.contributors || []).join(', ') || 'None'}
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-badge bg-amber-50 border border-amber-200 text-amber-900 text-xs font-bold">
                    REVIEWED PACKAGE — NOT FILED
                  </span>
                </div>

                {/* Typed factual claims with 1-click source provenance */}
                <div className="space-y-2" data-testid="factual-claims-list">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-2">
                    Verified Factual Claims (Click any citation for source row & SHA-256)
                  </h3>
                  {(artifact.manifest?.factual_claims || []).map((clm) => (
                    <div key={clm.claim_id} className="p-3 bg-surface-1 rounded-lg border border-surface-3 text-xs space-y-1.5">
                      <div className="font-semibold text-text-0">
                        <span className="font-mono text-accent mr-1.5">{clm.claim_id}</span>
                        {clm.statement}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {(clm.cited_event_ids || []).map((eid) => (
                          <button
                            key={eid}
                            type="button"
                            onClick={() => setDrawerRecord(citedByEvent[eid] || { external_id: eid, row_number: 'n/a', payload: {} })}
                            className="inline-flex items-center gap-1 px-2 py-0.5 bg-surface-0 border border-surface-3 rounded font-mono text-[11px] text-accent hover:bg-accent-tint"
                          >
                            <Eye className="w-3 h-3" aria-hidden="true" /> {eid}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Literal narrative bytes */}
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-2 mb-2">
                    Exact Frozen UTF-8 Narrative (Five Ws + How)
                  </h3>
                  <pre
                    data-testid="frozen-narrative"
                    className="p-4 rounded-lg border font-mono text-xs whitespace-pre-wrap leading-relaxed"
                    style={{ background: 'var(--sar-bg)', borderColor: 'var(--sar-border)', color: 'var(--sar-text)' }}
                  >
                    {artifact.narrative}
                  </pre>
                </div>

                {/* Action Bar: Freeze -> Independent Review -> Export / Close */}
                <div className="pt-4 border-t border-surface-3 space-y-3">
                  {artifact.status === 'DRAFT' && (
                    <button
                      type="button"
                      onClick={handleFreeze}
                      className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover"
                    >
                      <Lock className="w-4 h-4" aria-hidden="true" /> Freeze Exact Bytes for Review (IN_REVIEW)
                    </button>
                  )}

                  {artifact.status === 'IN_REVIEW' && (
                    <div className="p-4 bg-surface-1 rounded-lg border border-surface-3 space-y-3">
                      <h3 className="text-xs font-bold uppercase text-text-0">Independent Reviewer Action</h3>
                      <p className="text-xs text-text-2">
                        Approval is denied to every material contributor in the revision ancestry.
                      </p>
                      <textarea
                        rows={2}
                        placeholder="Reviewer note (stored in separate approval envelope)"
                        value={reviewNote}
                        onChange={(e) => setReviewNote(e.target.value)}
                        className="w-full px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn bg-surface-0"
                      />
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => handleReview('APPROVED')}
                          className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-btn hover:bg-emerald-700"
                        >
                          <CheckCircle2 className="w-4 h-4" aria-hidden="true" /> Approve Frozen Package
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReview('CHANGES_REQUESTED')}
                          className="px-4 py-2 bg-amber-600 text-white text-xs font-semibold rounded-btn hover:bg-amber-700"
                        >
                          Request Changes
                        </button>
                      </div>
                    </div>
                  )}

                  {(artifact.status === 'APPROVED' || artifact.status === 'APPROVED_HISTORICAL') && (
                    <div className="flex flex-wrap gap-2">
                      {!artifact.evidence_stale && (
                        <button
                          type="button"
                          onClick={() => handleExport(false)}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white text-xs font-semibold rounded-btn hover:bg-accent-hover"
                        >
                          <Download className="w-4 h-4" aria-hidden="true" /> Export Current Reviewed Package
                        </button>
                      )}
                      {artifact.evidence_stale && (
                        <button
                          type="button"
                          onClick={() => handleExport(true)}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-amber-700 text-white text-xs font-semibold rounded-btn hover:bg-amber-800"
                        >
                          <Download className="w-4 h-4" aria-hidden="true" /> Export Historical Approved Package (Superseded)
                        </button>
                      )}
                    </div>
                  )}

                  {/* Closure without export */}
                  <div className="pt-3 border-t border-surface-2 flex flex-wrap items-center gap-2">
                    <input
                      type="text"
                      value={closureMemo}
                      onChange={(e) => setClosureMemo(e.target.value)}
                      placeholder="Optional institutional closure memo (if closing without export)"
                      className="flex-1 min-w-[220px] px-2.5 py-1.5 text-xs border border-surface-3 rounded-btn"
                    />
                    <button
                      type="button"
                      onClick={handleCloseCase}
                      className="px-3 py-1.5 bg-surface-1 border border-surface-3 text-xs font-semibold rounded-btn hover:bg-surface-2"
                    >
                      Close Without Export
                    </button>
                  </div>
                </div>
              </GlowCard>

              {/* Side-by-side Revision Diff */}
              {diffRows && (
                <GlowCard className="p-5 space-y-2" data-testid="revision-diff">
                  <h3 className="font-display text-lg text-text-0">
                    Revision Diff: Rev {compareArtifact.revision_number} vs Rev {artifact.revision_number}
                  </h3>
                  <div className="grid grid-cols-2 gap-2 font-mono text-[11px] max-h-64 overflow-y-auto">
                    {diffRows.map((row, idx) => (
                      <div key={idx} className="contents">
                        <div className={`p-1 rounded ${row.kind === 'changed' ? 'bg-rose-50 text-rose-900' : 'bg-surface-1 text-text-2'}`}>
                          {row.left || ' '}
                        </div>
                        <div className={`p-1 rounded ${row.kind === 'changed' ? 'bg-emerald-50 text-emerald-900' : 'bg-surface-1 text-text-2'}`}>
                          {row.right || ' '}
                        </div>
                      </div>
                    ))}
                  </div>
                </GlowCard>
              )}

              {/* Export Output Preview */}
              {exportedPkg && (
                <GlowCard className="p-5 space-y-2" data-testid="export-output">
                  <div className="font-bold text-xs text-text-0">{exportedPkg.banner}</div>
                  <div className="font-mono text-[11px] text-text-2">
                    Export ID: {exportedPkg.export_id} · Kind: {exportedPkg.export_kind} · Payload Digest: {exportedPkg.payload_digest}
                  </div>
                  <div className="font-mono text-[11px] text-text-2">
                    Approval Envelope Digest: {exportedPkg.envelope_digest}
                  </div>
                </GlowCard>
              )}
            </>
          ) : (
            <GlowCard className="p-8 text-center text-sm text-text-2">
              No draft revision exists for this case yet. Click &ldquo;Generate Deterministic Draft&rdquo; to build a
              source-cited Five Ws + How package.
            </GlowCard>
          )}
        </div>
      </div>

      <ProvenanceDrawer record={drawerRecord} onClose={() => setDrawerRecord(null)} />
    </div>
  );
}
