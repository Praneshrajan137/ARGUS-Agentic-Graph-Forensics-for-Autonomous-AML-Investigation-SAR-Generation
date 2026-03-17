export default function LoadingSpinner({ size = 24, className = '' }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="var(--surface-3)" strokeWidth="3" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="var(--accent-base)"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}
