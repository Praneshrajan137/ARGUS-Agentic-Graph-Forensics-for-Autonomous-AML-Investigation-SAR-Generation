/**
 * Highlights amounts, entity IDs, and dates in evidence text.
 * Returns an array of React elements (strings and <span> elements).
 * SAFE: uses React elements, NOT dangerouslySetInnerHTML.
 */
export function highlightContent(text, knownEntityIds = []) {
  if (!text) return [text];

  // Pattern: $X,XXX.XX or ₹X,XX,XXX.XX or plain numbers with decimal
  const amountRegex = /[\$₹][\d,]+\.?\d{0,2}/g;
  // Pattern: dates like 2024-01-15 or 01/15/2024
  const dateRegex = /\d{4}-\d{2}-\d{2}|\d{2}\/\d{2}\/\d{4}/g;

  const parts = [];
  let lastIndex = 0;
  const combined = new RegExp(`(${amountRegex.source})|(${dateRegex.source})`, 'g');

  let match;
  while ((match = combined.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[1]) {
      // Amount — amber highlight
      parts.push(
        <span key={match.index} className="font-mono font-bold px-0.5 rounded"
              style={{ background: 'var(--amber-tint)', color: 'var(--amber-base)' }}>
          {match[0]}
        </span>
      );
    } else if (match[2]) {
      // Date — violet highlight
      parts.push(
        <span key={match.index} className="font-mono px-0.5 rounded"
              style={{ background: 'var(--violet-tint)', color: 'var(--violet-base)' }}>
          {match[0]}
        </span>
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}
