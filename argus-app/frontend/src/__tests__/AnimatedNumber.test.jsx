import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AnimatedNumber } from '@/components/shared/AnimatedNumber';

describe('AnimatedNumber', () => {
  it('renders a motion.span element', () => {
    const { container } = render(<AnimatedNumber value={75} />);
    const span = container.querySelector('span');
    expect(span).toBeInTheDocument();
  });

  it('renders without crashing when value is 0', () => {
    const { container } = render(<AnimatedNumber value={0} />);
    expect(container.querySelector('span')).toBeInTheDocument();
  });

  it('renders without crashing when value is 100', () => {
    const { container } = render(<AnimatedNumber value={100} />);
    expect(container.querySelector('span')).toBeInTheDocument();
  });

  it('accepts a custom className via wrapper', () => {
    const { container } = render(
      <span data-testid="wrapper" className="font-mono">
        <AnimatedNumber value={42} />
      </span>
    );
    expect(screen.getByTestId('wrapper')).toHaveClass('font-mono');
  });
});
