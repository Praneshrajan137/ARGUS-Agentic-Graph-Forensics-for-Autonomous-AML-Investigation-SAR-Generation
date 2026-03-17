import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import EvidenceCard from '@/components/evidence/EvidenceCard';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }) => {
      const { whileHover, transition, variants, initial, animate, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
}));

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('EvidenceCard', () => {
  const sarDoc = {
    evidence_id: 'EV-001',
    doc_type: 'sar_narrative',
    subject_id: '42',
    content: 'Suspicious activity report narrative for entity with $10,000.00 transferred on 2024-01-15.',
  };

  const emailDoc = {
    evidence_id: 'EV-002',
    doc_type: 'email',
    subject_id: '7',
    body: 'Wire transfer notification for ₹5,00,000.00 processed.',
  };

  const kycDoc = {
    evidence_id: 'EV-003',
    doc_type: 'kyc_document',
    subject_id: null,
    content: 'KYC verification completed for individual account holder.',
  };

  const unknownDoc = {
    evidence_id: 'EV-004',
    doc_type: 'unknown_type',
    content: 'Generic document content.',
  };

  it('renders SAR Narrative type badge', () => {
    renderWithRouter(<EvidenceCard document={sarDoc} />);
    expect(screen.getByText('SAR Narrative')).toBeInTheDocument();
  });

  it('renders Email type badge', () => {
    renderWithRouter(<EvidenceCard document={emailDoc} />);
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('renders KYC Document type badge', () => {
    renderWithRouter(<EvidenceCard document={kycDoc} />);
    expect(screen.getByText('KYC Document')).toBeInTheDocument();
  });

  it('falls back to Document badge for unknown types', () => {
    renderWithRouter(<EvidenceCard document={unknownDoc} />);
    expect(screen.getByText('Document')).toBeInTheDocument();
  });

  it('renders entity link when subject_id exists', () => {
    renderWithRouter(<EvidenceCard document={sarDoc} />);
    const link = screen.getByText('Entity 42');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', '/graph?node=42');
  });

  it('does not render entity link when subject_id is null', () => {
    renderWithRouter(<EvidenceCard document={kycDoc} />);
    expect(screen.queryByText(/Entity/)).not.toBeInTheDocument();
  });

  it('renders content preview from "content" field', () => {
    renderWithRouter(<EvidenceCard document={sarDoc} />);
    expect(screen.getByText(/Suspicious activity report/)).toBeInTheDocument();
  });

  it('renders content preview from "body" field when no "content"', () => {
    renderWithRouter(<EvidenceCard document={emailDoc} />);
    expect(screen.getByText(/Wire transfer notification/)).toBeInTheDocument();
  });

  it('renders evidence ID in footer', () => {
    renderWithRouter(<EvidenceCard document={sarDoc} />);
    expect(screen.getByText('EV-001')).toBeInTheDocument();
  });

  it('truncates long content with ellipsis', () => {
    const longDoc = {
      evidence_id: 'EV-LONG',
      doc_type: 'bank_statement',
      content: 'A'.repeat(300),
    };
    renderWithRouter(<EvidenceCard document={longDoc} />);
    expect(screen.getByText('...')).toBeInTheDocument();
  });

  it('renders bank_statement type badge', () => {
    const bankDoc = {
      evidence_id: 'EV-005',
      doc_type: 'bank_statement',
      content: 'Monthly statement summary.',
    };
    renderWithRouter(<EvidenceCard document={bankDoc} />);
    expect(screen.getByText('Bank Statement')).toBeInTheDocument();
  });
});
