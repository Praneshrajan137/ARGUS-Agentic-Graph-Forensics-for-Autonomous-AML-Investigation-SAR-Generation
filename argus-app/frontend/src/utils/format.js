/** Format number with locale separators: 1234567 → "1,234,567" */
export function formatNumber(n) {
  if (n == null || isNaN(n)) return '\u2014';
  return Number(n).toLocaleString('en-US');
}

/** Format USD currency: 12345.67 → "$12,345.67" */
export function formatUSD(amount) {
  if (amount == null || isNaN(amount)) return '\u2014';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(amount);
}

/** Format INR currency: 12345.67 → "₹12,345.67" */
export function formatINR(amount) {
  if (amount == null || isNaN(amount)) return '\u2014';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(amount);
}

/** Format ratio as percentage: 0.856 → "85.6%" */
export function formatPercent(ratio, decimals = 1) {
  if (ratio == null || isNaN(ratio)) return '\u2014';
  return `${(ratio * 100).toFixed(decimals)}%`;
}

/** Format milliseconds to human-readable: 12345 → "12.3s", 500 → "500ms" */
export function formatDuration(ms) {
  if (ms == null || isNaN(ms)) return '\u2014';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

/** Format Unix timestamp (seconds) to locale datetime string */
export function formatTimestamp(epochSeconds) {
  if (!epochSeconds) return '\u2014';
  return new Date(epochSeconds * 1000).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
