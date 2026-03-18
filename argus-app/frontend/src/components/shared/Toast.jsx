import { AnimatePresence, motion } from 'framer-motion';
import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { useToast } from '@/contexts/ToastContext';

const TOAST_CONFIG = {
  success: { border: 'var(--emerald-base)', bg: 'var(--emerald-tint)', Icon: CheckCircle2 },
  error:   { border: 'var(--rose-base)',    bg: 'var(--rose-tint)',    Icon: AlertCircle },
  warning: { border: 'var(--amber-base)',   bg: 'var(--amber-tint)',   Icon: AlertTriangle },
  info:    { border: 'var(--accent-base)',  bg: 'var(--accent-tint)',  Icon: Info },
};

export default function ToastContainer() {
  const { toasts, removeToast } = useToast();

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none max-w-sm w-full">
      <AnimatePresence>
        {toasts.map((toast) => {
          const cfg = TOAST_CONFIG[toast.type] || TOAST_CONFIG.info;
          const Icon = cfg.Icon;
          return (
            <motion.div
              key={toast.id}
              layout
              initial={{ opacity: 0, x: 40, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.95 }}
              transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="pointer-events-auto flex items-start gap-3 px-4 py-3.5 rounded-card shadow-lg border"
              style={{
                background: cfg.bg,
                borderColor: cfg.border + '30',
                borderLeft: `4px solid ${cfg.border}`,
              }}
              role="alert"
              aria-live="polite"
            >
              <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: cfg.border }} />
              <p className="text-sm text-text-0 flex-1 leading-relaxed">{toast.message}</p>
              <button
                onClick={() => removeToast(toast.id)}
                className="flex-shrink-0 p-0.5 rounded hover:bg-black/5 transition-colors"
                aria-label="Dismiss"
              >
                <X className="w-3.5 h-3.5 text-text-3" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
