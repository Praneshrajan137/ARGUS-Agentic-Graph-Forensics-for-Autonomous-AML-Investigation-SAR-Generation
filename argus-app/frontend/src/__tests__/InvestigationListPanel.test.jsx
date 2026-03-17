import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import InvestigationListPanel from '@/components/sar/InvestigationListPanel';

// Mock framer-motion to render plain elements
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => <div {...props}>{children}</div>,
    span: ({ children, ...props }) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }) => <>{children}</>,
}));

const mockInvestigations = [
  {
    case_id: 'ARGUS-001',
    sar_narrative: 'Suspicious structuring activity detected.',
    detected_typology: 'STRUCTURING',
    confidence_score: 0.85,
    jurisdiction: 'fincen',
    investigation_start: '2024-06-15T10:30:00Z',
    investigation_timestamp: 1718444200,
  },
  {
    case_id: 'ARGUS-002',
    sar_narrative: 'Multi-hop layering chain identified.',
    detected_typology: 'LAYERING',
    confidence_score: 0.72,
    jurisdiction: 'fiu_ind',
    investigation_start: '2024-06-16T08:00:00Z',
    investigation_timestamp: 1718521600,
  },
  {
    case_id: 'ARGUS-003',
    sar_narrative: '', // empty — should be filtered out
    detected_typology: 'NONE',
    confidence_score: 0.3,
    jurisdiction: 'fincen',
    investigation_start: '2024-06-17T12:00:00Z',
    investigation_timestamp: 1718622000,
  },
];

describe('InvestigationListPanel', () => {
  it('renders header with title', () => {
    render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText('SAR Reports')).toBeInTheDocument();
  });

  it('renders search input', () => {
    render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByPlaceholderText('Search by case ID...')).toBeInTheDocument();
  });

  it('filters out investigations without SAR narratives', () => {
    render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText('ARGUS-001')).toBeInTheDocument();
    expect(screen.getByText('ARGUS-002')).toBeInTheDocument();
    // ARGUS-003 has empty sar_narrative so should NOT appear
    expect(screen.queryByText('ARGUS-003')).not.toBeInTheDocument();
  });

  it('filters by search term', () => {
    render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    const input = screen.getByPlaceholderText('Search by case ID...');
    fireEvent.change(input, { target: { value: '002' } });
    expect(screen.queryByText('ARGUS-001')).not.toBeInTheDocument();
    expect(screen.getByText('ARGUS-002')).toBeInTheDocument();
  });

  it('calls onSelect when a card is clicked', () => {
    const onSelect = vi.fn();
    render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId={null}
        onSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByText('ARGUS-001'));
    expect(onSelect).toHaveBeenCalledWith('ARGUS-001');
  });

  it('highlights the selected investigation card', () => {
    const { container } = render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId="ARGUS-001"
        onSelect={() => {}}
      />
    );
    const selectedBtn = container.querySelector('button.bg-accent-tint');
    expect(selectedBtn).toBeTruthy();
  });

  it('shows empty state when no investigations have SAR narratives', () => {
    render(
      <InvestigationListPanel
        investigations={[{ case_id: 'X', sar_narrative: '' }]}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText('No SAR reports found')).toBeInTheDocument();
  });

  it('shows jurisdiction label for each card', () => {
    render(
      <InvestigationListPanel
        investigations={mockInvestigations}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText(/FinCEN/)).toBeInTheDocument();
    expect(screen.getByText(/FIU-IND/)).toBeInTheDocument();
  });

  it('handles null investigations gracefully', () => {
    render(
      <InvestigationListPanel
        investigations={null}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText('No SAR reports found')).toBeInTheDocument();
  });
});
