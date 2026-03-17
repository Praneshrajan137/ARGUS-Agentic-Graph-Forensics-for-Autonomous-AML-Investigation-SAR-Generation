import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AccordionSection from '@/components/shared/AccordionSection';
import { AlertTriangle } from 'lucide-react';

// Minimal framer-motion mock is not needed — jsdom handles basic rendering.

describe('AccordionSection', () => {
  const defaultProps = {
    title: 'Test Section',
    children: <p data-testid="accordion-content">Inner content</p>,
  };

  it('renders with title', () => {
    render(<AccordionSection {...defaultProps} />);
    expect(screen.getByText('Test Section')).toBeInTheDocument();
  });

  it('is collapsed by default (defaultOpen=false)', () => {
    render(<AccordionSection {...defaultProps} />);
    expect(screen.queryByTestId('accordion-content')).not.toBeInTheDocument();
  });

  it('is open when defaultOpen=true', () => {
    render(<AccordionSection {...defaultProps} defaultOpen />);
    expect(screen.getByTestId('accordion-content')).toBeInTheDocument();
  });

  it('toggles open/close on button click', () => {
    render(<AccordionSection {...defaultProps} />);
    const button = screen.getByRole('button');

    // Initially closed
    expect(button).toHaveAttribute('aria-expanded', 'false');

    // Click to open
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('accordion-content')).toBeInTheDocument();

    // Click to close
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('shows count badge when count > 0', () => {
    render(<AccordionSection {...defaultProps} count={5} />);
    expect(screen.getByTestId('accordion-count')).toHaveTextContent('5');
  });

  it('hides count badge when count is 0', () => {
    render(<AccordionSection {...defaultProps} count={0} />);
    expect(screen.queryByTestId('accordion-count')).not.toBeInTheDocument();
  });

  it('renders with an icon', () => {
    render(
      <AccordionSection
        {...defaultProps}
        icon={AlertTriangle}
        accentColor="var(--amber-base)"
      />
    );
    // The icon renders as an SVG inside the button
    const button = screen.getByRole('button');
    const svgs = button.querySelectorAll('svg');
    // Should have the icon SVG + the chevron SVG = at least 2
    expect(svgs.length).toBeGreaterThanOrEqual(2);
  });

  it('applies data-testid based on title', () => {
    render(<AccordionSection {...defaultProps} />);
    expect(screen.getByTestId('accordion-test-section')).toBeInTheDocument();
  });
});
