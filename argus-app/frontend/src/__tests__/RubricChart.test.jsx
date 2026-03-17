import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import RubricChart from '@/components/assessment/RubricChart';

// Recharts uses ResizeObserver internally
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserver;

const mockRubric = {
  pattern: { weight: 0.28, score: 85 },
  evidence: { weight: 0.20, score: 72 },
  narrative: { weight: 0.16, score: 60 },
  completeness: { weight: 0.16, score: 90 },
  efficiency: { weight: 0.20, score: 78 },
};

describe('RubricChart', () => {
  it('renders without crashing', () => {
    const { container } = render(<RubricChart rubric={mockRubric} />);
    expect(container).toBeInTheDocument();
  });

  it('renders all 5 category names', () => {
    render(<RubricChart rubric={mockRubric} />);
    expect(screen.getByText('Pattern')).toBeInTheDocument();
    expect(screen.getByText('Evidence')).toBeInTheDocument();
    expect(screen.getByText('Narrative')).toBeInTheDocument();
    expect(screen.getByText('Completeness')).toBeInTheDocument();
    expect(screen.getByText('Efficiency')).toBeInTheDocument();
  });

  it('renders score percentage labels', () => {
    render(<RubricChart rubric={mockRubric} />);
    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();
    expect(screen.getByText('78%')).toBeInTheDocument();
  });

  it('renders with null rubric without crashing', () => {
    const { container } = render(<RubricChart rubric={null} />);
    expect(container).toBeInTheDocument();
  });

  it('renders with empty rubric defaulting scores to 0', () => {
    render(<RubricChart rubric={{}} />);
    // All scores should default to 0
    const zeroLabels = screen.getAllByText('0%');
    expect(zeroLabels.length).toBe(5);
  });
});
