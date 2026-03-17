const STATUS_MAP = {
  complete: { label: 'Complete', bg: 'var(--emerald-tint)', text: 'var(--emerald-base)' },
  failed: { label: 'Failed', bg: 'var(--rose-tint)', text: 'var(--rose-base)' },
  running: { label: 'Running', bg: 'var(--cyan-tint)', text: 'var(--cyan-base)' },
  pending: { label: 'Pending', bg: 'var(--surface-2)', text: 'var(--text-3)' },
  warning: { label: 'Warning', bg: 'var(--amber-tint)', text: 'var(--amber-base)' },
};

export default function StatusBadge({ status }) {
  const s = STATUS_MAP[status?.toLowerCase()] || STATUS_MAP.pending;
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-badge text-xs font-semibold tracking-wide uppercase"
      style={{ background: s.bg, color: s.text }}
    >
      {s.label}
    </span>
  );
}
