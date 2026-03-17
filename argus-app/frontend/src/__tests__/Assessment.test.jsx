import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Assessment from '@/pages/Assessment';

// ResizeObserver polyfill for Recharts
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserver;

const mockInvestigations = [
  {
    case_id: 'ARGUS-001',
    status: 'COMPLETE',
    detected_typology: 'Layering',
    confidence_score: 0.87,
  },
  {
    case_id: 'ARGUS-002',
    status: 'RUNNING',
    detected_typology: 'Structuring',
    confidence_score: 0.45,
  },
  {
    case_id: 'ARGUS-003',
    status: 'COMPLETE',
    detected_typology: 'Structuring',
    confidence_score: 0.92,
  },
];

const mockAssessment = {
  overall_score: 0.82,
  rubric_breakdown: {
    pattern: { weight: 0.28, score: 85 },
    evidence: { weight: 0.20, score: 72 },
    narrative: { weight: 0.16, score: 60 },
    completeness: { weight: 0.16, score: 90 },
    efficiency: { weight: 0.20, score: 78 },
  },
  entity_metrics: {
    precision: 0.88,
    recall: 0.75,
    f1_score: 0.81,
  },
  hallucination_count: 0,
  hallucination_details: [],
  five_ws: {
    who: true,
    what: true,
    where: true,
    when: false,
    why: true,
  },
  missed_indicators: ['Unusual round-trip transfers'],
};

vi.mock('@/api/client', () => ({
  getInvestigations: vi.fn().mockResolvedValue(mockInvestigations),
  runAssessment: vi.fn().mockResolvedValue(mockAssessment),
}));

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual('framer-motion');
  return {
    ...actual,
    motion: new Proxy(actual.motion, {
      get(target, prop) {
        // Return a forwardRef wrapper that passes through props
        if (typeof prop === 'string' && !target[prop]) {
          return prop;
        }
        return target[prop];
      },
    }),
  };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <Assessment />
    </MemoryRouter>
  );

describe('Assessment Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page header', async () => {
    renderPage();
    expect(screen.getByText('Assessment')).toBeInTheDocument();
    expect(screen.getByText('Investigation quality scoring and rubric analysis')).toBeInTheDocument();
  });

  it('renders the investigation selector dropdown', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
  });

  it('renders the Run Assessment button', () => {
    renderPage();
    expect(screen.getByTestId('run-assessment-btn')).toBeInTheDocument();
  });

  it('Run Assessment button is disabled when no investigation is selected', () => {
    renderPage();
    expect(screen.getByTestId('run-assessment-btn')).toBeDisabled();
  });

  it('shows only completed investigations in the dropdown', async () => {
    renderPage();
    await waitFor(() => {
      const options = screen.getAllByRole('option');
      // 1 placeholder + 2 COMPLETE investigations (ARGUS-001, ARGUS-003)
      expect(options.length).toBe(3);
    });
  });

  it('shows empty state when no assessment has been run', () => {
    renderPage();
    expect(screen.getByText('Select an Investigation')).toBeInTheDocument();
  });

  it('enables Run Assessment button when an investigation is selected', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
    const selector = screen.getByTestId('investigation-selector');
    fireEvent.change(selector, { target: { value: 'ARGUS-001' } });
    expect(screen.getByTestId('run-assessment-btn')).not.toBeDisabled();
  });

  it('displays assessment results after clicking Run Assessment', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId('investigation-selector'), {
      target: { value: 'ARGUS-001' },
    });
    fireEvent.click(screen.getByTestId('run-assessment-btn'));

    await waitFor(() => {
      expect(screen.getByText('OVERALL')).toBeInTheDocument();
    });
  });

  it('renders Five Ws checklist after assessment', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId('investigation-selector'), {
      target: { value: 'ARGUS-001' },
    });
    fireEvent.click(screen.getByTestId('run-assessment-btn'));

    await waitFor(() => {
      expect(screen.getByText('WHO — Subject entities identified')).toBeInTheDocument();
      expect(screen.getByText('WHAT — Activity described')).toBeInTheDocument();
      expect(screen.getByText('WHERE — Jurisdiction specified')).toBeInTheDocument();
      expect(screen.getByText('WHEN — Timeframe documented')).toBeInTheDocument();
      expect(screen.getByText('WHY — Indicators articulated')).toBeInTheDocument();
    });
  });

  it('renders metric cards (Precision, Recall, F1 Score) after assessment', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId('investigation-selector'), {
      target: { value: 'ARGUS-001' },
    });
    fireEvent.click(screen.getByTestId('run-assessment-btn'));

    await waitFor(() => {
      expect(screen.getByText('Precision')).toBeInTheDocument();
      expect(screen.getByText('Recall')).toBeInTheDocument();
      expect(screen.getByText('F1 Score')).toBeInTheDocument();
    });
  });

  it('renders hallucination check section after assessment', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId('investigation-selector'), {
      target: { value: 'ARGUS-001' },
    });
    fireEvent.click(screen.getByTestId('run-assessment-btn'));

    await waitFor(() => {
      expect(screen.getByText('Hallucination Check')).toBeInTheDocument();
      expect(screen.getByText('0 found')).toBeInTheDocument();
    });
  });

  it('renders missed indicators section when present', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('investigation-selector')).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId('investigation-selector'), {
      target: { value: 'ARGUS-001' },
    });
    fireEvent.click(screen.getByTestId('run-assessment-btn'));

    await waitFor(() => {
      expect(screen.getByText('Unusual round-trip transfers')).toBeInTheDocument();
    });
  });
});
