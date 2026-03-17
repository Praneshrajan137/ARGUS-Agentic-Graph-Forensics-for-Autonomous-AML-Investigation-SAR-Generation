import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Settings from '@/pages/Settings';

// Use vi.hoisted to define mock data that vi.mock factories can reference
const { mockHealth, mockConfig } = vi.hoisted(() => ({
  mockHealth: {
    status: 'healthy',
    forge_version: '1.0.0',
    tracer_version: '1.0.0',
    unified_version: '1.0.0',
    node_count: 1000,
    edge_count: 5000,
    uptime_seconds: 3600,
    graph_loaded: true,
  },
  mockConfig: {
    seed: 42,
    difficulty: 5,
    node_count: 1000,
  },
}));

vi.mock('@/api/client', () => ({
  getConfig: vi.fn().mockResolvedValue(mockConfig),
  getHealth: vi.fn().mockResolvedValue(mockHealth),
  generateWorld: vi.fn().mockResolvedValue({ status: 'ok' }),
  resetState: vi.fn().mockResolvedValue({ status: 'ok' }),
}));

// Mock AnimatePresence to skip exit animations (jsdom has no animation loop)
vi.mock('framer-motion', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    AnimatePresence: ({ children }) => <>{children}</>,
  };
});

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>
  );

describe('Settings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ═══ PAGE HEADER ═══
  it('renders the page header', () => {
    renderPage();
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Dataset generation, system info, and configuration')).toBeInTheDocument();
  });

  // ═══ GENERATE SECTION ═══
  it('renders the Generate New Dataset section', () => {
    renderPage();
    expect(screen.getByText('Generate New Dataset')).toBeInTheDocument();
  });

  it('renders seed input with default value 42', () => {
    renderPage();
    const seedInput = screen.getByTestId('seed-input');
    expect(seedInput).toBeInTheDocument();
    expect(seedInput).toHaveValue(42);
  });

  it('renders random seed button', () => {
    renderPage();
    expect(screen.getByTestId('random-seed-btn')).toBeInTheDocument();
  });

  it('changes seed when random button is clicked', () => {
    renderPage();
    const seedInput = screen.getByTestId('seed-input');
    fireEvent.click(screen.getByTestId('random-seed-btn'));
    expect(Number(seedInput.value)).not.toBeNaN();
  });

  it('renders difficulty slider with default value 5', () => {
    renderPage();
    const slider = screen.getByTestId('difficulty-slider');
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveValue('5');
  });

  it('shows difficulty label "Standard" for value 5', () => {
    renderPage();
    expect(screen.getByText(/Standard/)).toBeInTheDocument();
  });

  it('updates difficulty label when slider changes', () => {
    renderPage();
    const slider = screen.getByTestId('difficulty-slider');
    fireEvent.change(slider, { target: { value: '9' } });
    expect(screen.getByText(/Extreme/)).toBeInTheDocument();
  });

  it('renders node count input with default value 1000', () => {
    renderPage();
    const nodeInput = screen.getByTestId('node-count-input');
    expect(nodeInput).toBeInTheDocument();
    expect(nodeInput).toHaveValue(1000);
  });

  it('renders Generate Financial World button', () => {
    renderPage();
    expect(screen.getByTestId('generate-btn')).toBeInTheDocument();
    expect(screen.getByText('Generate Financial World')).toBeInTheDocument();
  });

  // ═══ SYSTEM INFO ═══
  it('renders System Information section', () => {
    renderPage();
    expect(screen.getByText('System Information')).toBeInTheDocument();
  });

  it('displays health data after loading', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('healthy')).toBeInTheDocument();
      expect(screen.getByText('1,000')).toBeInTheDocument();
      expect(screen.getByText('5,000')).toBeInTheDocument();
    });
  });

  // ═══ DANGER ZONE ═══
  it('renders Danger Zone section', () => {
    renderPage();
    expect(screen.getByText('Danger Zone')).toBeInTheDocument();
  });

  it('renders Reset All Data button', () => {
    renderPage();
    expect(screen.getByTestId('reset-btn')).toBeInTheDocument();
  });

  it('shows confirmation dialog when Reset is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('reset-btn'));
    expect(screen.getByText('Are you sure? This will destroy all data.')).toBeInTheDocument();
    expect(screen.getByTestId('confirm-reset-btn')).toBeInTheDocument();
    expect(screen.getByTestId('cancel-reset-btn')).toBeInTheDocument();
  });

  it('hides confirmation dialog when Cancel is clicked', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('reset-btn'));
    fireEvent.click(screen.getByTestId('cancel-reset-btn'));
    expect(screen.queryByText('Are you sure? This will destroy all data.')).not.toBeInTheDocument();
  });

  it('calls resetState and navigates when confirm reset is clicked', async () => {
    const { resetState } = await import('@/api/client');
    renderPage();
    fireEvent.click(screen.getByTestId('reset-btn'));
    fireEvent.click(screen.getByTestId('confirm-reset-btn'));

    await waitFor(() => {
      expect(resetState).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });
});
