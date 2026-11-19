import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SARDocument from '@/components/sar/SARDocument';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

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
    it('renders a draft header, not a filed report', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByRole('heading', { level: 1, name: 'Draft investigation narrative' })).toBeInTheDocument();
      expect(screen.getByText('Not submitted to FinCEN.')).toBeInTheDocument();
      expect(screen.getByText('Draft — for review')).toBeInTheDocument();
    });

    it('displays BSA as preparation context without claiming legal compliance', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('Prepared under Bank Secrecy Act (31 U.S.C. § 5318) for review—not filed.')).toBeInTheDocument();
      expect(screen.getByText(/this draft does not establish legal compliance/)).toBeInTheDocument();
    });

    it('renders the case ID in metadata', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByText('ARGUS-TEST-001')).toBeInTheDocument();
    });

    it('omits confidence percentages and affirmative filing labels', () => {
      const { container } = render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.queryByText('Confidence')).not.toBeInTheDocument();
      expect(screen.queryByText('Filing Date')).not.toBeInTheDocument();
      expect(screen.queryByText(/^Filed/)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /approve|submit|file report/i })).not.toBeInTheDocument();
      expect(container.textContent).not.toMatch(/\d+%|Filed pursuant to/);
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
    it('keeps FIU-IND preparation a draft with no submission claim', () => {
      render(<SARDocument investigation={fiuIndInvestigation} />);
      expect(screen.getByRole('heading', { level: 1, name: 'Draft investigation narrative' })).toBeInTheDocument();
      expect(screen.getByText('Not submitted to FinCEN. Not submitted to FIU-IND.')).toBeInTheDocument();
      expect(screen.queryByText('Filing Date')).not.toBeInTheDocument();
      expect(screen.queryByText(/^Filed/)).not.toBeInTheDocument();
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
      expect(doc).toHaveAttribute('aria-label', 'Draft investigation narrative ARGUS-TEST-001');
    });
  });

  describe('Persisted artifact metadata', () => {
    it('prefers epoch seconds and keeps historical metadata stable across later views', () => {
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date('2026-11-01T00:00:00Z'));
      const investigation = {
        ...fincenInvestigation,
        investigation_timestamp: Date.parse('2020-02-03T04:05:06Z') / 1000,
      };
      const { rerender } = render(<SARDocument investigation={investigation} />);
      expect(screen.getByText('Created (UTC)')).toBeInTheDocument();
      expect(screen.getByTestId('investigation-created-at')).toHaveAttribute('datetime', '2020-02-03T04:05:06.000Z');
      expect(screen.getByTestId('investigation-created-at')).toHaveTextContent('Mon, 03 Feb 2020 04:05:06 GMT');
      const originalText = screen.getByRole('document').textContent;
      vi.setSystemTime(new Date('2035-12-31T23:59:59Z'));
      rerender(<SARDocument investigation={{ ...investigation }} />);
      expect(screen.getByRole('document').textContent).toBe(originalText);
      expect(originalText).not.toMatch(/2026|2035|ARGUS v1\.0\.0|TRACER v7\.0\.0|Generated by/);
    });

    it('falls back to persisted investigation_start when epoch is absent', () => {
      render(<SARDocument investigation={fincenInvestigation} />);
      expect(screen.getByTestId('investigation-created-at')).toHaveAttribute('datetime', '2024-06-15T10:30:00.000Z');
    });

    it.each([NaN, Infinity, 1e100, 'not-a-timestamp'])(
      'falls back to persisted start for invalid epoch %s', (investigation_timestamp) => {
        render(<SARDocument investigation={{ ...fincenInvestigation, investigation_timestamp }} />);
        expect(screen.getByTestId('investigation-created-at')).toHaveAttribute('datetime', '2024-06-15T10:30:00.000Z');
      }
    );

    it('preserves epoch zero instead of treating it as missing', () => {
      render(<SARDocument investigation={{ ...fincenInvestigation, investigation_timestamp: 0 }} />);
      expect(screen.getByTestId('investigation-created-at')).toHaveAttribute('datetime', '1970-01-01T00:00:00.000Z');
    });

    it.each([undefined, null, '', 'invalid-date'])(
      'does not invent a creation date when persisted timestamps are unavailable: %s', (investigation_start) => {
        render(<SARDocument investigation={{ ...fincenInvestigation, investigation_start }} />);
        expect(screen.getByText('Not available')).toBeInTheDocument();
        expect(screen.queryByTestId('investigation-created-at')).not.toBeInTheDocument();
        expect(screen.queryByText(/Invalid Date|Generated by/)).not.toBeInTheDocument();
      }
    );

    it('does not assign activity timestamps a timezone based on jurisdiction', () => {
      render(<SARDocument investigation={fiuIndInvestigation} />);
      expect(screen.getByText(fiuIndInvestigation.sar_draft.when)).toBeInTheDocument();
      expect(screen.queryByText(/All timestamps in/)).not.toBeInTheDocument();
      expect(screen.getByTestId('investigation-created-at')).toHaveAttribute('datetime', '2024-03-20T14:00:00.000Z');
    });
  });

  describe('Unknown geography', () => {
    it.each(['fincen', 'fiu_ind', undefined])(
      'does not infer an activity location from reporting jurisdiction %s', (jurisdiction) => {
        render(<SARDocument investigation={{ ...fincenInvestigation, jurisdiction, sar_draft: {} }} />);
        expect(screen.getByText('Unknown — geographic information not provided')).toBeInTheDocument();
      }
    );

    it('treats blank geography as unknown', () => {
      render(<SARDocument investigation={{ ...fincenInvestigation, sar_draft: { where: '   ' } }} />);
      expect(screen.getByText('Unknown — geographic information not provided')).toBeInTheDocument();
    });

    it('preserves an explicitly unknown source location', () => {
      render(<SARDocument investigation={{ ...fincenInvestigation, sar_draft: { where: 'Unknown' } }} />);
      expect(screen.getByText('Unknown')).toBeInTheDocument();
    });

    it('does not assume US regulatory context for missing jurisdiction', () => {
      render(<SARDocument investigation={{ ...fincenInvestigation, jurisdiction: undefined, sar_draft: {} }} />);
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('Prepared for review—not filed. Regulatory context not provided.')).toBeInTheDocument();
      expect(screen.queryByText('United States')).not.toBeInTheDocument();
      expect(screen.queryByText(/Bank Secrecy Act/)).not.toBeInTheDocument();
    });
  });

  describe('Draft copy', () => {
    it.each([fincenInvestigation, fiuIndInvestigation])(
      'copies a clearly labeled draft for $jurisdiction without submission or approval actions', async (investigation) => {
        const user = userEvent.setup();
        const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
        render(<SARDocument investigation={investigation} />);
        await user.click(screen.getByRole('button', { name: 'Copy draft' }));
        const notice = investigation.jurisdiction === 'fiu_ind'
          ? 'Not submitted to FinCEN. Not submitted to FIU-IND.'
          : 'Not submitted to FinCEN.';
        expect(writeText).toHaveBeenCalledWith(
          `Draft investigation narrative\n${notice} For review only.\n\n${investigation.sar_narrative}`
        );
        expect(screen.getByRole('button', { name: 'Draft copied' })).toHaveAttribute('aria-live', 'polite');
        expect(screen.queryByRole('button', { name: /approve|submit|file report/i })).not.toBeInTheDocument();
      }
    );

    it('has no copy action when no draft narrative is supplied', () => {
      render(<SARDocument investigation={{ ...fincenInvestigation, sar_narrative: '' }} />);
      expect(screen.getByText('No draft narrative available.')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Copy draft' })).not.toBeInTheDocument();
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
