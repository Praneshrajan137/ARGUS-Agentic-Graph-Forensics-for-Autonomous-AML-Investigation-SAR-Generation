import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SARDocument from '@/components/sar/SARDocument';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => {
      const { variants, initial, animate, whileHover, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
}));

const fincenInvestigation = {
  case_id: 'ARGUS-TEST-001',
  sar_narrative: 'Subject conducted multiple structuring transactions below the $10,000 CTR threshold.',
  sar_draft: {
    who: 'Entity A (individual) — high risk',
    what: 'Structuring deposits below CTR threshold',
    where: 'New York, United States',
    when: 'June 2024 — 15 transactions over 48 hours',
    why: 'Pattern consistent with BSA structuring indicators',
    cited_tx_ids: ['TX-001', 'TX-002', 'TX-003'],
  },
  jurisdiction: 'fincen',
  confidence_score: 0.87,
  detected_typology: 'STRUCTURING',
  investigation_start: '2024-06-15T10:30:00Z',
  involved_entities: [],
  detection_results: {},
};

const fiuIndInvestigation = {
  case_id: 'ARGUS-TEST-002',
  sar_narrative: 'Multi-hop layering chain identified through shell companies.',
  sar_draft: {
    who: 'Entity B (business) — medium risk',
    what: 'Complex layering through multiple intermediaries',
    where: 'Mumbai, India',
    when: 'March 2024 — 30-day window',
    why: 'PMLA Section 3 violation indicators',
    cited_tx_ids: ['TX-100'],
  },
  jurisdiction: 'fiu_ind',
  confidence_score: 0.65,
  detected_typology: 'LAYERING',
  investigation_start: '2024-03-20T14:00:00Z',
  involved_entities: [],
  detection_results: {},
};

describe('SARDocument', () => {
  it('returns null when no investigation provided', () => {
    const { container } = render(<SARDocument investigation={null} />);
    expect(container.innerHTML).toBe('');
  });

  describe('FinCEN SAR (US jurisdiction)', () => {
    it('renders the FinCEN header', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('FinCEN Suspicious Activity Report')).toBeInTheDocument();
    });

    it('displays BSA citation', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/Bank Secrecy Act/)).toBeInTheDocument();
    });

    it('renders the case ID in metadata', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('ARGUS-TEST-001')).toBeInTheDocument();
    });

    it('renders confidence as percentage', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('87%')).toBeInTheDocument();
    });

    it('renders United States as jurisdiction', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('United States')).toBeInTheDocument();
    });

    it('renders FinCEN regulatory body in footer', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/Financial Crimes Enforcement Network/)).toBeInTheDocument();
    });
  });

  describe('FIU-IND STR (India jurisdiction)', () => {
    it('renders FIU-IND header', () => {
      render(<SARDocument investigation={fiuIndInvestigation} />);
      expect(screen.getByText('FIU-IND Suspicious Transaction Report')).toBeInTheDocument();
    });

    it('displays PMLA citation', () => {
      render(<SARDocument investigation={fiuIndInvestigation} />);
      expect(screen.getByText(/Prevention of Money Laundering Act/)).toBeInTheDocument();
    });

    it('renders India as jurisdiction', () => {
      render(<SARDocument investigation={fiuIndInvestigation} />);
      expect(screen.getByText('India')).toBeInTheDocument();
    });

    it('renders FIU-IND regulatory body in footer', () => {
      render(<SARDocument investigation={fiuIndInvestigation} />);
      expect(screen.getByText(/Financial Intelligence Unit — India/)).toBeInTheDocument();
    });
  });

  describe('Five Ws Sections', () => {
    it('renders WHO section', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/WHO — Subjects Under Investigation/)).toBeInTheDocument();
      expect(screen.getByText(fincenInvestigation.sar_draft.who)).toBeInTheDocument();
    });

    it('renders WHAT section', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/WHAT — Description of Suspicious Activity/)).toBeInTheDocument();
      expect(screen.getByText(fincenInvestigation.sar_draft.what)).toBeInTheDocument();
    });

    it('renders WHERE section', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/WHERE — Geographic Information/)).toBeInTheDocument();
      expect(screen.getByText(fincenInvestigation.sar_draft.where)).toBeInTheDocument();
    });

    it('renders WHEN section', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/WHEN — Timeframe of Activity/)).toBeInTheDocument();
      expect(screen.getByText(fincenInvestigation.sar_draft.when)).toBeInTheDocument();
    });

    it('renders WHY section', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/WHY — Indicators of Suspicious Activity/)).toBeInTheDocument();
      expect(screen.getByText(fincenInvestigation.sar_draft.why)).toBeInTheDocument();
    });
  });

  describe('Narrative and Transactions', () => {
    it('renders the full narrative', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(fincenInvestigation.sar_narrative)).toBeInTheDocument();
    });

    it('renders cited transaction IDs as badges', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('TX-001')).toBeInTheDocument();
      expect(screen.getByText('TX-002')).toBeInTheDocument();
      expect(screen.getByText('TX-003')).toBeInTheDocument();
    });

    it('shows transaction count', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText(/Referenced Transactions \(3\)/)).toBeInTheDocument();
    });
  });

  describe('CONFIDENTIAL Watermark', () => {
    it('renders confidential watermark text', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('CONFIDENTIAL')).toBeInTheDocument();
    });

    it('watermark has pointer-events-none', () => {
      const { container } = render(<SARDocument investigation={fincenInvestigation} />);
      const watermarkContainer = container.querySelector('.pointer-events-none');
      expect(watermarkContainer).toBeTruthy();
    });
  });

  describe('Accessibility', () => {
    it('has role="document" with aria-label', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      const doc = screen.getByRole('document');
      expect(doc).toHaveAttribute('aria-label', 'SAR Report ARGUS-TEST-001');
    });
  });

  describe('Fallback / missing Five Ws', () => {
    it('uses fallback text when sar_draft fields are missing', () => {
      const inv = {
        ...fincenInvestigation,
        sar_draft: {},
      };
      render(<SARDocument investigation={inv} />);
      expect(screen.getByText('Entities not identified')).toBeInTheDocument();
    });

    it('handles missing sar_draft entirely', () => {
      const inv = {
        ...fincenInvestigation,
        sar_draft: undefined,
      };
      render(<SARDocument investigation={inv} />);
      expect(screen.getByText('Entities not identified')).toBeInTheDocument();
    });
  });
});
