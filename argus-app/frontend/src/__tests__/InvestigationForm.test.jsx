import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import InvestigationForm from '@/components/investigation/InvestigationForm';

// Mock the API client
vi.mock('@/api/client', () => ({
  getNodes: vi.fn().mockResolvedValue({
    nodes: [
      {
        id: '0',
        name: 'John Doe',
        entity_type: 'individual',
        risk_rating: 'high',
        jurisdiction: 'US',
      },
      {
        id: '1',
        name: 'Acme Corp',
        entity_type: 'business',
        risk_rating: 'medium',
        jurisdiction: 'US',
      },
    ],
    total: 2,
    page: 1,
    per_page: 8,
    total_pages: 1,
  }),
}));

describe('InvestigationForm', () => {
  const mockSubmit = vi.fn();

  const renderForm = (props = {}) =>
    render(
      <InvestigationForm
        prefillSubjectId={null}
        isSubmitting={false}
        onSubmit={mockSubmit}
        {...props}
      />
    );

  it('renders subject search input', () => {
    renderForm();
    expect(screen.getByTestId('subject-search-input')).toBeInTheDocument();
  });

  it('renders hop depth slider with default value 3', () => {
    renderForm();
    const slider = screen.getByTestId('hop-depth-slider');
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveValue('3');
  });

  it('renders both jurisdiction buttons', () => {
    renderForm();
    expect(screen.getByTestId('jurisdiction-fincen')).toBeInTheDocument();
    expect(screen.getByTestId('jurisdiction-fiu_ind')).toBeInTheDocument();
  });

  it('renders auto-generated case ID starting with ARGUS-', () => {
    renderForm();
    const caseIdEl = screen.getByTestId('case-id-display');
    expect(caseIdEl.textContent).toMatch(/^ARGUS-/);
  });

  it('submit button is disabled when no subject is selected', () => {
    renderForm();
    const btn = screen.getByTestId('launch-investigation-btn');
    expect(btn).toBeDisabled();
  });

  it('submit button shows loading state when isSubmitting=true', () => {
    renderForm({ isSubmitting: true });
    expect(screen.getByText('Running Investigation...')).toBeInTheDocument();
  });

  it('submit button shows "Launch Investigation" when idle', () => {
    renderForm();
    expect(screen.getByText('Launch Investigation')).toBeInTheDocument();
  });

  it('changes hop depth when slider is adjusted', () => {
    renderForm();
    const slider = screen.getByTestId('hop-depth-slider');
    fireEvent.change(slider, { target: { value: '7' } });
    expect(slider).toHaveValue('7');
    expect(screen.getByText('7 hops')).toBeInTheDocument();
  });

  it('toggles jurisdiction when FIU-IND is clicked', () => {
    renderForm();
    const fiuBtn = screen.getByTestId('jurisdiction-fiu_ind');
    fireEvent.click(fiuBtn);
    // FIU-IND button should now have the active styling (bg-accent class)
    expect(fiuBtn.className).toContain('bg-accent');
  });

  it('pre-fills subject ID from URL param', () => {
    renderForm({ prefillSubjectId: '42' });
    const input = screen.getByTestId('subject-search-input');
    expect(input).toHaveValue('42');
  });

  it('renders Analysis Depth label', () => {
    renderForm();
    expect(screen.getByText('Analysis Depth')).toBeInTheDocument();
  });

  it('renders Jurisdiction label', () => {
    renderForm();
    expect(screen.getByText('Jurisdiction')).toBeInTheDocument();
  });
});
