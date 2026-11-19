import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import InvestigationResults from '@/components/investigation/InvestigationResults';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Wrap in MemoryRouter because InvestigationResults uses <Link>. */
const renderWithRouter = (result) =>
  render(
    <MemoryRouter>
      <InvestigationResults result={result} />
    </MemoryRouter>
  );

/** Full mock investigation result matching InvestigationResponse schema. */
const MOCK_RESULT = {
  case_id: 'ARGUS-TEST123',
  subject_id: '0',
  jurisdiction: 'fincen',
  status: 'COMPLETE',
  detected_typology: 'STRUCTURING',
  involved_entities: ['0', '1', '2'],
  confidence_score: 0.5,
  sar_narrative: 'Subject 0 engaged in structuring activity via account 0.',
  sar_draft: null,
  evidence_package: {
    verdict: 'MATCH',
    reasoning: 'The compared observations match.',
    discrepancies: [],
  },
  detection_results: {
    structuring_hits: [
      {
        node: '0',
        tx_count: 15,
        currency: 'USD',
        total: '142500',
        mode: '9400',
        sources: ['3', '4', '5'],
      },
    ],
    layering_hits: [],
  },
  validation_errors: [],
  steps: [
    { name: 'receive', status: 'complete', duration_ms: 5, detail: 'OK' },
    { name: 'analyze', status: 'complete', duration_ms: 120, detail: 'OK' },
    { name: 'detect', status: 'complete', duration_ms: 80, detail: 'OK' },
    { name: 'synthesize', status: 'complete', duration_ms: 30, detail: 'OK' },
    { name: 'compute', status: 'complete', duration_ms: 2, detail: 'OK' },
    { name: 'draft', status: 'complete', duration_ms: 50, detail: 'OK' },
    { name: 'validate', status: 'complete', duration_ms: 15, detail: 'OK' },
    { name: 'submit', status: 'complete', duration_ms: 3, detail: 'OK' },
  ],
};

const PASSED_VALIDATION = {
  status: 'PASSED',
  passed: true,
  errors: [],
  checked_count: 3,
  eligible_count: 3,
  artifact_digest: 'sha256:stored-artifact',
  validator_version: 'source-checks-2',
};

describe('InvestigationResults', () => {
  it('returns null when result is null', () => {
    const { container } = render(
      <MemoryRouter>
        <InvestigationResults result={null} />
      </MemoryRouter>
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders investigation results container', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('investigation-results')).toBeInTheDocument();
  });

  it('displays STRUCTURING typology badge', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByText('Structuring')).toBeInTheDocument();
  });

  it('displays COMPLETE status badge', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByText('Complete')).toBeInTheDocument();
  });

  it('displays step count and total duration', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByText(/8 steps/)).toBeInTheDocument();
    expect(screen.getByText(/305ms/)).toBeInTheDocument();
  });

  it('displays SAR narrative text', () => {
    renderWithRouter(MOCK_RESULT);
    expect(
      screen.getByText(/Subject 0 engaged in structuring/)
    ).toBeInTheDocument();
  });

  it('displays CONFIDENTIAL watermark', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('sar-watermark')).toHaveTextContent(
      'CONFIDENTIAL'
    );
  });

  it('shows the supplied score as an uncalibrated heuristic, not a formula or percentage', () => {
    const { container } = renderWithRouter({
      ...MOCK_RESULT,
      confidence_score: 0.1234,
      detected_typology: 'BOTH',
      evidence_package: { verdict: 'DISAGREEMENT', discrepancies: ['Observation mismatch'] },
    });
    expect(screen.getByText('Heuristic score (uncalibrated):')).toBeInTheDocument();
    expect(screen.getByTestId('heuristic-score')).toHaveTextContent('0.1234');
    expect(screen.getByText('Not a probability or verification result.')).toBeInTheDocument();
    expect(screen.queryByText(/Confidence Formula/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('confidence-breakdown')).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/\d+%/);
  });

  it.each([undefined, null, NaN, Infinity])('does not invent a zero score for %s', (score) => {
    renderWithRouter({ ...MOCK_RESULT, confidence_score: score });
    expect(screen.getByTestId('heuristic-score')).toHaveTextContent('Not available');
  });

  it('preserves a supplied zero heuristic score', () => {
    renderWithRouter({ ...MOCK_RESULT, confidence_score: 0 });
    expect(screen.getByTestId('heuristic-score')).toHaveTextContent(/^0$/);
  });

  it('shows structuring detection accordion auto-expanded', () => {
    renderWithRouter(MOCK_RESULT);
    // Structuring hit details should be visible since defaultOpen is true when hits > 0
    expect(screen.getByText('Account: 0')).toBeInTheDocument();
    expect(screen.getByText(/15 txns/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Structuring Detection/ })).toHaveAttribute('aria-expanded', 'true');
  });

  it('treats omitted validation_result as not run despite empty legacy errors and a completed pipeline', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('validation-status')).toHaveTextContent(/^Not run$/);
    expect(screen.getByTestId('validation-status')).toHaveStyle({ color: 'var(--text-2)' });
    expect(screen.getByTestId('validation-coverage')).toHaveTextContent('Checked: Not reported · Eligible: Not reported');
    expect(screen.queryByText(/zero hallucinations|all.*verified/i)).not.toBeInTheDocument();
  });

  it('displays evidence verdict', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('evidence-verdict')).toHaveTextContent(
      'MATCH'
    );
  });

  it('renders action buttons', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('score-investigation-btn')).toBeInTheDocument();
    expect(screen.getByTestId('view-sar-btn')).toBeInTheDocument();
    expect(screen.getByTestId('browse-evidence-btn')).toBeInTheDocument();
  });

  it('action links contain correct case_id in href', () => {
    renderWithRouter(MOCK_RESULT);
    const sarLink = screen.getByTestId('view-sar-btn');
    expect(sarLink).toHaveAttribute(
      'href',
      '/sar?case_id=ARGUS-TEST123'
    );
  });

  it('shows fallback text when sar_narrative is empty', () => {
    renderWithRouter({ ...MOCK_RESULT, sar_narrative: '' });
    expect(
      screen.getByText('No draft narrative available.')
    ).toBeInTheDocument();
  });

  it('copies only draft-labeled text and announces completion', async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByRole('heading', { name: 'Draft investigation narrative' })).toBeInTheDocument();
    expect(screen.getByText('Not submitted to FinCEN. For review only.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Copy draft' }));
    expect(writeText).toHaveBeenCalledWith(
      `Draft investigation narrative\nNot submitted to FinCEN. For review only.\n\n${MOCK_RESULT.sar_narrative}`
    );
    expect(screen.getByRole('button', { name: 'Draft copied' })).toHaveAttribute('aria-live', 'polite');
  });

  it('preserves currency and amount for each hit without labeling accounts as mules', () => {
    renderWithRouter({
      ...MOCK_RESULT,
      detection_results: {
        structuring_hits: [
          { node: 'us-account', currency: 'USD', total: '142500.01', mode: '9400', tx_count: 15 },
          { node: 'in-account', currency: 'INR', total: '700000.25', mode: '49000', tx_count: 15 },
          { node: 'eu-account', currency: 'EUR', total: '8100.50', mode: '2700', tx_count: 3 },
          { node: 'unknown-currency', total: '125.00', tx_count: 1 },
        ],
      },
    });
    const section = screen.getByTestId('accordion-structuring-detection');
    expect(within(section).getByText('Account: us-account')).toBeInTheDocument();
    expect(within(section).getByText('USD 142500.01')).toBeInTheDocument();
    expect(within(section).getByText('INR 700000.25')).toBeInTheDocument();
    expect(within(section).getByText('EUR 8100.50')).toBeInTheDocument();
    expect(within(section).getByText('Currency unknown 125.00')).toBeInTheDocument();
    expect(section).not.toHaveTextContent(/Mule|\$/);
  });

  it.each(['NO_OBSERVATION', 'NOT_COMPARABLE', 'MATCH', 'DISAGREEMENT', 'INSUFFICIENT_DATA'])(
    'preserves evidence verdict %s without inventing corroboration', (verdict) => {
      renderWithRouter({ ...MOCK_RESULT, evidence_package: { verdict } });
      expect(screen.getByTestId('evidence-verdict')).toHaveTextContent(verdict);
      expect(screen.queryByText(/corroborated|confirmed|partial.match/i)).not.toBeInTheDocument();
      expect(screen.getByText(/not a determination of suspicious activity/)).toBeInTheDocument();
    }
  );

  it('reports missing evidence without a fabricated verdict', () => {
    renderWithRouter({ ...MOCK_RESULT, evidence_package: undefined });
    expect(screen.getByTestId('evidence-verdict')).toHaveTextContent('Not provided');
  });
});

describe('source checks', () => {
  it.each([undefined, null, {}, { errors: [] }, { passed: true, errors: [] }])(
    'never infers a pass from incomplete validator metadata: %j', (validation_result) => {
      const { container } = renderWithRouter({ ...MOCK_RESULT, validation_result });
      expect(screen.getByTestId('validation-status')).toHaveTextContent(/^Not run$/);
      expect(screen.getByTestId('validation-status')).toHaveStyle({ color: 'var(--text-2)' });
      expect(container.textContent).not.toMatch(/zero hallucinations|all.*verified|Passed for/);
    }
  );

  it('reports an explicit pass with bounded scope and supplied provenance', () => {
    const { container } = renderWithRouter({ ...MOCK_RESULT, validation_result: PASSED_VALIDATION });
    expect(screen.getByTestId('validation-status')).toHaveTextContent('Passed for the reported source checks');
    expect(screen.getByTestId('validation-status')).toHaveStyle({ color: 'var(--emerald-base)' });
    expect(screen.getByTestId('validation-coverage')).toHaveTextContent('Checked: 3 · Eligible: 3');
    expect(screen.getByText('Validator version: source-checks-2')).toBeInTheDocument();
    expect(screen.getByText('Artifact digest: sha256:stored-artifact')).toBeInTheDocument();
    expect(screen.getByText(/do not establish narrative accuracy or legal compliance/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/zero hallucinations|all.*verified/i);
  });

  it.each([false, undefined, 'true'])(
    'requires passed to be the boolean true, not %s', (passed) => {
      renderWithRouter({ ...MOCK_RESULT, validation_result: { ...PASSED_VALIDATION, passed } });
      expect(screen.getByTestId('validation-status')).toHaveTextContent('Inconsistent result — pass not confirmed');
    }
  );

  it('does not show success for contradictory passed metadata with errors', () => {
    renderWithRouter({
      ...MOCK_RESULT,
      validation_result: { ...PASSED_VALIDATION, errors: ['Transaction mismatch'] },
    });
    expect(screen.getByTestId('validation-status')).toHaveTextContent('Inconsistent result — pass not confirmed');
    expect(screen.getByRole('list', { name: 'Source check errors' })).toHaveTextContent('Transaction mismatch');
  });

  it.each([
    ['PARTIAL', 'Partial — source checks incomplete', 'var(--amber-base)'],
    ['FAILED', 'Failed', 'var(--rose-base)'],
  ])('reports %s, counts and errors explicitly', (status, label, color) => {
    renderWithRouter({
      ...MOCK_RESULT,
      validation_result: {
        ...PASSED_VALIDATION, status, passed: false, checked_count: 2, eligible_count: 5,
        errors: ['Entity X not found', 'Transaction mismatch'],
      },
    });
    expect(screen.getByTestId('validation-status')).toHaveTextContent(label);
    expect(screen.getByTestId('validation-status')).toHaveStyle({ color });
    expect(screen.getByTestId('validation-coverage')).toHaveTextContent('Checked: 2 · Eligible: 5');
    const errors = screen.getByRole('list', { name: 'Source check errors' });
    expect(within(errors).getAllByRole('listitem')).toHaveLength(2);
    expect(errors).toHaveTextContent('Entity X not found');
    expect(errors).toHaveTextContent('Transaction mismatch');
  });

  it.each(['PARTIAL', 'FAILED'])('does not promote %s to passed when errors are empty', (status) => {
    renderWithRouter({ ...MOCK_RESULT, validation_result: { ...PASSED_VALIDATION, status } });
    expect(screen.getByTestId('validation-status')).not.toHaveTextContent('Passed for');
    expect(screen.getByTestId('validation-status')).toHaveTextContent(status === 'PARTIAL' ? 'Partial' : 'Failed');
  });

  it.each([['NOT_RUN', 'Not run'], ['NOT_APPLICABLE', 'Not applicable']])(
    'keeps %s neutral and preserves zero counts', (status, label) => {
      renderWithRouter({
        ...MOCK_RESULT,
        validation_result: { status, passed: false, errors: [], checked_count: 0, eligible_count: 0 },
      });
      expect(screen.getByTestId('validation-status')).toHaveTextContent(label);
      expect(screen.getByTestId('validation-status')).toHaveStyle({ color: 'var(--text-2)' });
      expect(screen.getByTestId('validation-coverage')).toHaveTextContent('Checked: 0 · Eligible: 0');
    }
  );

  it('displays partial analysis coverage limitations explicitly', () => {
    renderWithRouter({
      ...MOCK_RESULT,
      detected_typology: 'NONE',
      coverage: {
        status: 'PARTIAL',
        limitations: [{ reason: 'MAX_NODE_DEGREE', node: 'hub_1', limit: 500 }],
      },
    });
    expect(screen.getByTestId('coverage-status')).toHaveTextContent('Partial — traversal or scope limits were reached');
    expect(screen.getByTestId('coverage-limitations')).toHaveTextContent('MAX_NODE_DEGREE: node hub_1 (limit 500)');
    expect(screen.getByText(/does not clear a customer/i)).toBeInTheDocument();
  });
});
