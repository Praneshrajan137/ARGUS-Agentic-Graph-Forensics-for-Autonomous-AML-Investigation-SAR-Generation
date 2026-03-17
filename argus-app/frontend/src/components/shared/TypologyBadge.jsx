const TYPOLOGY_MAP = {
  STRUCTURING: { label: 'Structuring', bg: 'var(--amber-tint)', text: 'var(--amber-base)', dot: 'var(--amber-base)' },
  LAYERING: { label: 'Layering', bg: 'var(--violet-tint)', text: 'var(--violet-base)', dot: 'var(--violet-base)' },
  BOTH: { label: 'Both', bg: 'var(--rose-tint)', text: 'var(--rose-base)', dot: 'var(--rose-base)' },
  NONE: { label: 'Clean', bg: 'var(--emerald-tint)', text: 'var(--emerald-base)', dot: 'var(--emerald-base)' },
};

export default function TypologyBadge({ typology }) {
  const t = TYPOLOGY_MAP[typology] || TYPOLOGY_MAP.NONE;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-badge text-xs font-bold tracking-wider uppercase"
      style={{ background: t.bg, color: t.text }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.dot }} />
      {t.label}
    </span>
  );
}
