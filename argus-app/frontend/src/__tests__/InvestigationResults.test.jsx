import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import InvestigationResults, {
  confidenceColor,
} from '@/components/investigation/InvestigationResults';

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
  sar_narrative: 'Subject 0 engaged in structuring activity via mule node 0.',
  sar_draft: null,
  evidence_package: {
    verdict: 'CORROBORATED',
    reasoning: 'Evidence supports structuring pattern.',
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

describe('confidenceColor', () => {
  it('returns rose for scores 0–0.29', () => {
    expect(confidenceColor(0)).toBe('var(--rose-base)');
    expect(confidenceColor(0.15)).toBe('var(--rose-base)');
    expect(confidenceColor(0.29)).toBe('var(--rose-base)');
  });

  it('returns amber for scores 0.30–0.59', () => {
    expect(confidenceColor(0.3)).toBe('var(--amber-base)');
    expect(confidenceColor(0.5)).toBe('var(--amber-base)');
    expect(confidenceColor(0.59)).toBe('var(--amber-base)');
  });

  it('returns emerald for scores 0.60–0.79', () => {
    expect(confidenceColor(0.6)).toBe('var(--emerald-base)');
    expect(confidenceColor(0.75)).toBe('var(--emerald-base)');
  });

  it('returns accent for scores 0.80–1.0', () => {
    expect(confidenceColor(0.8)).toBe('var(--accent-base)');
    expect(confidenceColor(1.0)).toBe('var(--accent-base)');
  });

  it('handles null/undefined as rose', () => {
    expect(confidenceColor(null)).toBe('var(--rose-base)');
    expect(confidenceColor(undefined)).toBe('var(--rose-base)');
  });
});

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

  it('displays confidence breakdown', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('confidence-breakdown')).toBeInTheDocument();
    expect(screen.getByTestId('confidence-total')).toBeInTheDocument();
  });

  it('shows structuring detection accordion auto-expanded', () => {
    renderWithRouter(MOCK_RESULT);
    // Structuring hit details should be visible since defaultOpen is true when hits > 0
    expect(screen.getByText(/Mule:/)).toBeInTheDocument();
    expect(screen.getByText(/15 txns/)).toBeInTheDocument();
  });

  it('shows zero hallucinations message when no validation errors', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('validation-pass')).toBeInTheDocument();
    expect(
      screen.getByText(/Zero hallucinations detected/)
    ).toBeInTheDocument();
  });

  it('displays evidence verdict', () => {
    renderWithRouter(MOCK_RESULT);
    expect(screen.getByTestId('evidence-verdict')).toHaveTextContent(
      'CORROBORATED'
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
      screen.getByText('No SAR generated (confidence below threshold).')
    ).toBeInTheDocument();
  });

  it('shows validation errors when present', () => {
    renderWithRouter({
      ...MOCK_RESULT,
      validation_errors: ['Entity X not found', 'Transaction mismatch'],
    });
    expect(screen.getByText('Entity X not found')).toBeInTheDocument();
    expect(screen.getByText('Transaction mismatch')).toBeInTheDocument();
  });
});
