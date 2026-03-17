import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PipelineTracker, {
  PIPELINE_STEPS,
  STATE_STYLES,
} from '@/components/investigation/PipelineTracker';

describe('PipelineTracker', () => {
  it('renders all 8 pipeline steps', () => {
    render(<PipelineTracker stepStates={{}} />);
    for (const step of PIPELINE_STEPS) {
      expect(
        screen.getByTestId(`pipeline-step-${step.key}`)
      ).toBeInTheDocument();
    }
  });

  it('renders all step labels', () => {
    render(<PipelineTracker stepStates={{}} />);
    for (const step of PIPELINE_STEPS) {
      expect(screen.getByText(step.label)).toBeInTheDocument();
    }
  });

  it('defaults all steps to pending state', () => {
    render(<PipelineTracker stepStates={{}} />);
    for (const step of PIPELINE_STEPS) {
      const el = screen.getByTestId(`pipeline-step-${step.key}`);
      expect(el).toHaveAttribute('data-state', 'pending');
    }
  });

  it('renders active state for specified step', () => {
    render(
      <PipelineTracker stepStates={{ receive: 'complete', analyze: 'active' }} />
    );
    expect(screen.getByTestId('pipeline-step-receive')).toHaveAttribute(
      'data-state',
      'complete'
    );
    expect(screen.getByTestId('pipeline-step-analyze')).toHaveAttribute(
      'data-state',
      'active'
    );
  });

  it('renders failed state correctly', () => {
    render(<PipelineTracker stepStates={{ detect: 'failed' }} />);
    expect(screen.getByTestId('pipeline-step-detect')).toHaveAttribute(
      'data-state',
      'failed'
    );
  });

  it('renders skipped state correctly', () => {
    render(<PipelineTracker stepStates={{ draft: 'skipped' }} />);
    expect(screen.getByTestId('pipeline-step-draft')).toHaveAttribute(
      'data-state',
      'skipped'
    );
  });

  it('renders warning state correctly', () => {
    render(<PipelineTracker stepStates={{ validate: 'warning' }} />);
    expect(screen.getByTestId('pipeline-step-validate')).toHaveAttribute(
      'data-state',
      'warning'
    );
  });

  it('shows duration when stepDetails are provided', () => {
    render(
      <PipelineTracker
        stepStates={{ receive: 'complete' }}
        stepDetails={{ receive: { duration_ms: 42, detail: 'OK' } }}
      />
    );
    expect(screen.getByText('42ms')).toBeInTheDocument();
  });

  it('STATE_STYLES has entries for all 6 states', () => {
    const expectedStates = [
      'pending',
      'active',
      'complete',
      'failed',
      'skipped',
      'warning',
    ];
    for (const state of expectedStates) {
      expect(STATE_STYLES[state]).toBeDefined();
      expect(STATE_STYLES[state].bg).toBeTruthy();
      expect(STATE_STYLES[state].iconColor).toBeTruthy();
      expect(STATE_STYLES[state].labelColor).toBeTruthy();
    }
  });

  it('PIPELINE_STEPS has exactly 8 entries', () => {
    expect(PIPELINE_STEPS).toHaveLength(8);
  });

  it('each step has key, label, icon, and desc', () => {
    for (const step of PIPELINE_STEPS) {
      expect(step.key).toBeTruthy();
      expect(step.label).toBeTruthy();
      expect(step.icon).toBeTruthy();
      expect(step.desc).toBeTruthy();
    }
  });
});
