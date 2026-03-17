import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ScoreGauge from '@/components/assessment/ScoreGauge';

describe('ScoreGauge', () => {
  it('renders an SVG element with correct viewBox', () => {
    const { container } = render(<ScoreGauge score={0.85} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('viewBox', '0 0 200 200');
  });

  it('renders two circle elements (background + foreground)', () => {
    const { container } = render(<ScoreGauge score={0.5} />);
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(2);
  });

  it('renders background ring with correct radius and stroke width', () => {
    const { container } = render(<ScoreGauge score={0.5} />);
    const bgCircle = container.querySelectorAll('circle')[0];
    expect(bgCircle).toHaveAttribute('r', '80');
    expect(bgCircle).toHaveAttribute('stroke-width', '12');
  });

  it('renders foreground ring with round linecap', () => {
    const { container } = render(<ScoreGauge score={0.5} />);
    const fgCircle = container.querySelectorAll('circle')[1];
    expect(fgCircle).toHaveAttribute('stroke-linecap', 'round');
  });

  it('renders the "OVERALL" label by default', () => {
    render(<ScoreGauge score={0.7} />);
    expect(screen.getByText('OVERALL')).toBeInTheDocument();
  });

  it('renders a custom label when provided', () => {
    render(<ScoreGauge score={0.7} label="QUALITY" />);
    expect(screen.getByText('QUALITY')).toBeInTheDocument();
  });

  it('applies indigo color for scores >= 80%', () => {
    const { container } = render(<ScoreGauge score={0.85} />);
    const fgCircle = container.querySelectorAll('circle')[1];
    expect(fgCircle.getAttribute('stroke')).toBe('var(--accent-base)');
  });

  it('applies emerald color for scores 60-79%', () => {
    const { container } = render(<ScoreGauge score={0.65} />);
    const fgCircle = container.querySelectorAll('circle')[1];
    expect(fgCircle.getAttribute('stroke')).toBe('var(--emerald-base)');
  });

  it('applies amber color for scores 30-59%', () => {
    const { container } = render(<ScoreGauge score={0.45} />);
    const fgCircle = container.querySelectorAll('circle')[1];
    expect(fgCircle.getAttribute('stroke')).toBe('var(--amber-base)');
  });

  it('applies rose color for scores < 30%', () => {
    const { container } = render(<ScoreGauge score={0.15} />);
    const fgCircle = container.querySelectorAll('circle')[1];
    expect(fgCircle.getAttribute('stroke')).toBe('var(--rose-base)');
  });

  it('sets correct strokeDasharray from circumference', () => {
    const CIRCUMFERENCE = 2 * Math.PI * 80;
    const { container } = render(<ScoreGauge score={0.5} />);
    const fgCircle = container.querySelectorAll('circle')[1];
    expect(fgCircle.getAttribute('stroke-dasharray')).toBe(String(CIRCUMFERENCE));
  });
});
