import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import RubricChart from '@/components/assessment/RubricChart';

// Recharts uses ResizeObserver internally
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserver;

// Mock Recharts — jsdom has no layout engine so BarChart renders empty.
// We mock the chart components to verify data transformation logic.
vi.mock('recharts', () => {
  const MockBar = ({ dataKey, children }) => <div data-testid={`bar-${dataKey}`}>{children}</div>;
  const MockCell = ({ fill }) => <span data-fill={fill} />;
  const MockLabelList = ({ dataKey, formatter }) => (
    <div data-testid={`labels-${dataKey}`}>{formatter ? formatter(85) : ''}</div>
  );
  return {
    BarChart: ({ data, children }) => (
      <div data-testid="bar-chart" data-count={data?.length}>{children}</div>
    ),
    Bar: MockBar,
    XAxis: () => null,
    YAxis: ({ dataKey }) => <div data-testid={`yaxis-${dataKey}`} />,
    CartesianGrid: () => null,
    ResponsiveContainer: ({ children }) => <div>{children}</div>,
    Cell: MockCell,
    LabelList: MockLabelList,
  };
});

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

  it('passes 5 data items to BarChart', () => {
    render(<RubricChart rubric={mockRubric} />);
    expect(screen.getByTestId('bar-chart')).toHaveAttribute('data-count', '5');
  });

  it('renders the chart container with correct testid', () => {
    render(<RubricChart rubric={mockRubric} />);
    expect(screen.getByTestId('rubric-chart')).toBeInTheDocument();
  });

  it('renders with null rubric without crashing', () => {
    const { container } = render(<RubricChart rubric={null} />);
    expect(container).toBeInTheDocument();
    expect(screen.getByTestId('rubric-chart')).toBeInTheDocument();
  });

  it('renders with empty rubric without crashing', () => {
    const { container } = render(<RubricChart rubric={{}} />);
    expect(container).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toHaveAttribute('data-count', '5');
  });
});
