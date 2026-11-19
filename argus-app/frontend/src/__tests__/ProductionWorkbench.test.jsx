import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CaseWorkspace from '@/pages/CaseWorkspace';
import NarrativeReview from '@/pages/NarrativeReview';
import { ReconciliationBadge } from '@/pages/ImportReconcile';
import { useQuery, clearAllQueries } from '@/hooks/useQuery';
import { usePolling } from '@/hooks/usePolling';
import * as api from '@/api/client';

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual('@/api/client');
  return {
    ...actual,
    getCase: vi.fn(),
    getCaseRecords: vi.fn(),
    getArtifact: vi.fn(),
    getJobStatus: vi.fn(),
    enqueueCaseAnalysis: vi.fn(),
    addFindingDisposition: vi.fn(),
    addCaseObservation: vi.fn(),
    createCaseArtifact: vi.fn(),
    freezeArtifact: vi.fn(),
    reviewArtifact: vi.fn(),
    exportArtifact: vi.fn(),
    closeCase: vi.fn(),
    addCaseComment: vi.fn(),
  };
});

const MOCK_CASE = {
  id: 'case-101',
  dataset_id: 'ds-1',
  snapshot_id: 'snap-1',
  subject_id: '002',
  title: 'Cash & Wire Review',
  status: 'OPEN',
  version: 1,
  snapshot_generation: 1,
  current_dataset_generation: 2,
  evidence_stale: true,
  reconciliation: { status: 'UNVERIFIED', reason: 'no_independent_controls_supplied' },
  jobs: [{
    id: 'job-1',
    status: 'COMPLETE',
    result: {
      findings: [{
        finding_id: 'fnd-1',
        typology: 'STRUCTURING',
        channel: 'CASH',
        mode: 'FAN_IN',
        currency: 'USD',
        total_amount: '95000',
        event_count: 10,
        cited_event_ids: ['TX-001'],
        uncalibrated_priority_score: '0.65',
        reasoning: '10 cash deposits within 48h window.',
      }],
      coverage: {
        status: 'PARTIAL',
        considered_events: 10,
        excluded_events_count: 2,
        excluded_breakdown: { PENDING_EVENT: 1, FX_EVENT_UNSUPPORTED: 1 },
        scoped_accounts_count: 1,
        limitations: [{ reason: 'MAX_NODE_DEGREE', node: '002', limit: 500 }],
        negative_scope_notice: 'No qualifying pattern found within this declared scope does not clear a customer.',
      },
    },
  }],
  observations: [{
    id: 'obs-1',
    source_ref: 'teller-note-1',
    raw_text: 'Customer stated deposit was $12,000 USD',
    comparison: {
      verdict: 'DISAGREEMENT',
      interpretation_notice: 'A numerical disagreement is a question requiring scoped investigation, neither proof that the ledger is true nor proof of wrongdoing.',
    },
  }],
  dispositions: [{
    id: 'disp-1',
    finding_id: 'fnd-1',
    disposition: 'DISMISSED',
    rationale: 'Verified seasonal retail cash receipts.',
    benign_alternative: 'Retail weekend deposit cycle',
    actor_id: 'analyst-1',
  }],
  comments: [],
  artifacts: [{
    id: 'art-2',
    revision_number: 2,
    parent_artifact_id: 'art-1',
    status: 'APPROVED',
    payload_digest: 'a'.repeat(64),
    contributors: ['analyst-1'],
  }, {
    id: 'art-1',
    revision_number: 1,
    parent_artifact_id: null,
    status: 'CHANGES_REQUESTED',
    payload_digest: 'b'.repeat(64),
    contributors: ['analyst-1'],
  }],
};

const MOCK_RECORDS = {
  records: [{
    record_id: 'rec-tx-1',
    external_id: 'TX-001',
    digest: 'c'.repeat(64),
    source_file_id: 'sf-1',
    source_file_sha256: 'd'.repeat(64),
    source_filename: 'transactions.csv',
    row_number: 7,
    analysis_eligible: true,
    exclusion_reason: null,
    payload: { id: 'TX-001', amount: '9500', currency: 'USD', event_type: 'CASH_DEPOSIT' },
  }],
};

describe('Milestone F: Challenge-first Production Workbench', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearAllQueries();
    api.getCase.mockResolvedValue(MOCK_CASE);
    api.getCaseRecords.mockResolvedValue(MOCK_RECORDS);
  });

  it('renders three explicit reconciliation badges (RECONCILED, MISMATCH, UNVERIFIED)', () => {
    const { rerender } = render(<ReconciliationBadge reconciliation={{ status: 'RECONCILED' }} />);
    expect(screen.getByTestId('reconciliation-badge')).toHaveTextContent(/RECONCILED/);
    rerender(<ReconciliationBadge reconciliation={{ status: 'MISMATCH' }} />);
    expect(screen.getByTestId('reconciliation-badge')).toHaveTextContent(/MISMATCH/);
    rerender(<ReconciliationBadge reconciliation={{ status: 'UNVERIFIED' }} />);
    expect(screen.getByTestId('reconciliation-badge')).toHaveTextContent(/UNVERIFIED/);
  });

  it('separates Observed Facts, Inferences, and Unresolved Questions, preserves dismissed raw findings, and opens provenance in 1 click', async () => {
    render(
      <MemoryRouter initialEntries={['/cases/case-101']}>
        <Routes>
          <Route path="/cases/:caseId" element={<CaseWorkspace />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByTestId('section-observed-facts')).toBeInTheDocument());
    expect(screen.getByTestId('section-inferences')).toBeInTheDocument();
    expect(screen.getByTestId('section-unresolved-questions')).toBeInTheDocument();

    // Stale evidence warning visible
    expect(screen.getByTestId('stale-evidence-banner')).toHaveTextContent(/Newer evidence exists/);

    // Dismissed disposition preserves raw finding alongside human disposition
    expect(screen.getByTestId('finding-card-fnd-1')).toHaveTextContent('95000');
    expect(screen.getByTestId('disposition-fnd-1')).toHaveTextContent('DISMISSED');
    expect(screen.getByTestId('disposition-fnd-1')).toHaveTextContent('Raw finding preserved');

    // Exclusions and disagreement disclaimer visible under Unresolved Questions
    expect(screen.getByTestId('section-unresolved-questions')).toHaveTextContent('PENDING_EVENT');
    expect(screen.getByTestId('section-unresolved-questions')).toHaveTextContent('DISAGREEMENT');
    expect(screen.getByTestId('section-unresolved-questions')).toHaveTextContent(/neither proof/);

    // 1-click from cited event ID reaches exact source file SHA-256 and CSV row ordinal
    fireEvent.click(screen.getByTestId('cite-TX-001'));
    expect(screen.getByTestId('provenance-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('provenance-row-number')).toHaveTextContent('Row #7');
    expect(screen.getByTestId('provenance-sha256')).toHaveTextContent('d'.repeat(64));
  });

  it('shows stale-evidence historical export option, revision diff, and non-filing stamp in NarrativeReview', async () => {
    api.getArtifact.mockImplementation((id) => Promise.resolve({
      id,
      case_id: 'case-101',
      revision_number: id === 'art-2' ? 2 : 1,
      status: id === 'art-2' ? 'APPROVED' : 'CHANGES_REQUESTED',
      payload_digest: (id === 'art-2' ? 'a' : 'b').repeat(64),
      contributors: ['analyst-1'],
      narrative: id === 'art-2' ? '=== REVIEW PACKAGE — NOT FILED ===\nRev 2 line' : '=== REVIEW PACKAGE — NOT FILED ===\nRev 1 line',
      manifest: {
        factual_claims: [{ claim_id: 'CLM-001', statement: 'Cited USD total 9500.', cited_event_ids: ['TX-001'] }],
        cited_records: [{ kind: 'transactions', external_id: 'TX-001', source_file_id: 'sf-1', row_number: 7, digest: 'c'.repeat(64), payload: { amount: '9500' } }],
        source_files: [{ source_file_id: 'sf-1', sha256: 'd'.repeat(64), filename: 'transactions.csv' }],
      },
      evidence_stale: true,
      snapshot_generation: 1,
      current_dataset_generation: 2,
    }));

    render(
      <MemoryRouter initialEntries={['/cases/case-101/review']}>
        <Routes>
          <Route path="/cases/:caseId/review" element={<NarrativeReview />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByTestId('frozen-narrative')).toBeInTheDocument());
    expect(screen.getByTestId('review-stale-warning')).toBeInTheDocument();
    expect(screen.getByText('REVIEWED PACKAGE — NOT FILED')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Export Historical Approved Package/i })).toBeInTheDocument();

    // Open side-by-side revision diff
    fireEvent.click(screen.getByRole('button', { name: /Diff/i }));
    await waitFor(() => expect(screen.getByTestId('revision-diff')).toBeInTheDocument());
  });

  it('prevents a slow prior-case response from overwriting a newly selected case in useQuery', async () => {
    let resolveSlow;
    const slowPromise = new Promise((res) => { resolveSlow = res; });
    const fetchers = {
      'case-A': () => slowPromise,
      'case-B': () => Promise.resolve({ title: 'Newer Case B' }),
    };

    function Harness({ caseKey }) {
      const { data } = useQuery(caseKey, () => fetchers[caseKey](), { staleTime: 0 });
      return <div data-testid="active-title">{data?.title || 'loading'}</div>;
    }

    const { rerender } = render(<Harness caseKey="case-A" />);
    rerender(<Harness caseKey="case-B" />);
    await waitFor(() => expect(screen.getByTestId('active-title')).toHaveTextContent('Newer Case B'));

    // Now the stale prior Case A resolves late -> MUST NOT overwrite Case B
    resolveSlow({ title: 'Stale Case A' });
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.getByTestId('active-title')).toHaveTextContent('Newer Case B');
  });

  it('treats transient polling network failure as a warning, NOT job failure', async () => {
    const pollFn = vi.fn().mockRejectedValueOnce(new Error('network down')).mockResolvedValueOnce({ status: 'COMPLETE' });
    function PollHarness() {
      const { data, networkWarning } = usePolling(pollFn, {
        enabled: true,
        initialDelayMs: 20,
        isTerminal: (d) => d?.status === 'COMPLETE',
      });
      return (
        <div>
          <span data-testid="poll-status">{data?.status || 'RUNNING'}</span>
          <span data-testid="poll-warn">{networkWarning || 'none'}</span>
        </div>
      );
    }

    render(<PollHarness />);
    await waitFor(() => expect(screen.getByTestId('poll-warn')).toHaveTextContent(/Network connection interrupted/));
    expect(screen.getByTestId('poll-status')).toHaveTextContent('RUNNING');
    await waitFor(() => expect(screen.getByTestId('poll-status')).toHaveTextContent('COMPLETE'));
  });
});
