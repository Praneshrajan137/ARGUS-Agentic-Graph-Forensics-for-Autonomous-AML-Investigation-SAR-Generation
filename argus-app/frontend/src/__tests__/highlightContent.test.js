import { describe, it, expect } from 'vitest';
import { highlightContent } from '@/utils/highlightContent';

describe('highlightContent', () => {
  it('returns input unchanged when no special tokens present', () => {
    const result = highlightContent('plain text with nothing special');
    expect(result).toEqual(['plain text with nothing special']);
  });

  it('returns array with single string for null/undefined/empty', () => {
    expect(highlightContent(null)).toEqual([null]);
    expect(highlightContent(undefined)).toEqual([undefined]);
    expect(highlightContent('')).toEqual(['']);
  });

  it('highlights USD amounts ($) with amber styling', () => {
    const result = highlightContent('Transfer of $10,000.00 to account');
    expect(result.length).toBeGreaterThan(1);
    // The highlighted element should be a React element (object)
    const highlightedEl = result.find(part => typeof part === 'object' && part !== null);
    expect(highlightedEl).toBeDefined();
    expect(highlightedEl.props.children).toBe('$10,000.00');
    expect(highlightedEl.props.className).toContain('font-mono');
    expect(highlightedEl.props.className).toContain('font-bold');
  });

  it('highlights INR amounts (₹) with amber styling', () => {
    const result = highlightContent('Payment of ₹5,00,000.00 received');
    const highlightedEl = result.find(part => typeof part === 'object' && part !== null);
    expect(highlightedEl).toBeDefined();
    expect(highlightedEl.props.children).toBe('₹5,00,000.00');
  });

  it('highlights ISO dates (YYYY-MM-DD) with violet styling', () => {
    const result = highlightContent('Transaction on 2024-01-15 detected');
    const highlightedEl = result.find(part => typeof part === 'object' && part !== null);
    expect(highlightedEl).toBeDefined();
    expect(highlightedEl.props.children).toBe('2024-01-15');
  });

  it('highlights US-format dates (MM/DD/YYYY) with violet styling', () => {
    const result = highlightContent('Filed on 01/15/2024 by analyst');
    const highlightedEl = result.find(part => typeof part === 'object' && part !== null);
    expect(highlightedEl).toBeDefined();
    expect(highlightedEl.props.children).toBe('01/15/2024');
  });

  it('highlights multiple tokens in the same text', () => {
    const result = highlightContent('$5,000.00 transferred on 2024-03-12');
    const objects = result.filter(part => typeof part === 'object' && part !== null);
    expect(objects.length).toBe(2);
    expect(objects[0].props.children).toBe('$5,000.00');
    expect(objects[1].props.children).toBe('2024-03-12');
  });

  it('preserves surrounding text between highlights', () => {
    const result = highlightContent('Amount $500.00 on 2024-01-01 end');
    const strings = result.filter(part => typeof part === 'string');
    expect(strings).toContain('Amount ');
    expect(strings).toContain(' on ');
    expect(strings).toContain(' end');
  });
});
