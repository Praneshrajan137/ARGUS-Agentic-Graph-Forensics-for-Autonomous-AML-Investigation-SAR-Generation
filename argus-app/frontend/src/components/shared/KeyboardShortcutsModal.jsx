import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

const SHORTCUTS = [
  { keys: ['?'], desc: 'Show keyboard shortcuts' },
  { keys: ['1'], desc: 'Go to Dashboard' },
  { keys: ['2'], desc: 'Go to Graph Explorer' },
  { keys: ['3'], desc: 'Go to Investigate' },
  { keys: ['4'], desc: 'Go to SAR Viewer' },
  { keys: ['5'], desc: 'Go to Evidence' },
  { keys: ['6'], desc: 'Go to Assessment' },
  { keys: ['7'], desc: 'Go to Benchmark' },
  { keys: ['8'], desc: 'Go to Settings' },
  { keys: ['Esc'], desc: 'Close modal / panel' },
];

export default function KeyboardShortcutsModal({ isOpen, onClose }) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-[9998] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/20 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0, transition: { type: 'spring', stiffness: 400, damping: 30 } }}
            exit={{ opacity: 0, scale: 0.95, y: 8, transition: { duration: 0.15 } }}
            className="relative bg-surface-0 rounded-card border border-surface-3 shadow-xl p-6 w-full max-w-sm"
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-display text-lg text-text-0">Keyboard Shortcuts</h3>
              <button
                onClick={onClose}
                className="p-1 rounded hover:bg-surface-2 transition-colors"
              >
                <X className="w-4 h-4 text-text-3" />
              </button>
            </div>

            <div className="space-y-1.5">
              {SHORTCUTS.map(({ keys, desc }) => (
                <div
                  key={desc}
                  className="flex items-center justify-between py-2 px-2 rounded-lg hover:bg-surface-1 transition-colors"
                >
                  <span className="text-sm text-text-1">{desc}</span>
                  <div className="flex items-center gap-1">
                    {keys.map((k) => (
                      <kbd
                        key={k}
                        className="inline-flex items-center justify-center min-w-[28px] h-7 px-2
                                   text-xs font-mono font-bold text-text-1 bg-surface-2
                                   border border-surface-3 rounded-md shadow-xs"
                      >
                        {k}
                      </kbd>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <p className="text-[10px] text-text-3 mt-4 text-center">
              Shortcuts disabled when typing in input fields
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
