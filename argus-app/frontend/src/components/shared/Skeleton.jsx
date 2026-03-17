export function Skeleton({ className = '', width, height }) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height, minHeight: height || 16 }}
    />
  );
}

export function StatCardSkeleton() {
  return (
    <div className="bg-surface-0 rounded-card border border-surface-3 p-6 flex items-start gap-4">
      <Skeleton className="w-12 h-12 rounded-xl" />
      <div className="flex-1 space-y-2">
        <Skeleton width="60%" height={14} />
        <Skeleton width="40%" height={28} />
      </div>
    </div>
  );
}
