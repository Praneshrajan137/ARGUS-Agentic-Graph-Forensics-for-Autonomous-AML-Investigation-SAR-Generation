import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function ErrorCard({ error, onRetry, className = '' }) {
  return (
    <div className={`bg-surface-0 border border-surface-3 rounded-card p-6 ${className}`}
      style={{ borderLeftColor: 'var(--rose-base)', borderLeftWidth: '3px' }}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--rose-base)' }} />
        <div className="flex-1">
          <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--rose-base)' }}>Something went wrong</h3>
          <p className="text-sm text-text-2">{error?.message || 'An unexpected error occurred.'}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-hover transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
