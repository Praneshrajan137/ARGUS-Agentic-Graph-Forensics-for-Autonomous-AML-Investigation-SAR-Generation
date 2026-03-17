import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

/**
 * Reusable animated accordion section with Framer Motion expand/collapse.
 *
 * @param {string}    title        — Section heading
 * @param {number}    count        — Badge count (hidden when 0)
 * @param {boolean}   defaultOpen  — Initial open state
 * @param {Component} icon         — Lucide icon component
 * @param {string}    accentColor  — CSS color for icon & badge tints
 * @param {ReactNode} children     — Collapsible content
 */
export default function AccordionSection({
  title,
  count = 0,
  defaultOpen = false,
  icon: Icon,
  accentColor,
  children,
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className="border border-surface-3 rounded-card overflow-hidden"
      data-testid={`accordion-${title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3.5 bg-surface-0
                   hover:bg-surface-1 transition-colors"
        aria-expanded={open}
        type="button"
      >
        <div className="flex items-center gap-3">
          {Icon && (
            <Icon
              className="w-4 h-4 flex-shrink-0"
              style={{ color: accentColor }}
            />
          )}
          <span className="text-sm font-semibold text-text-0">{title}</span>
          {count > 0 && (
            <span
              className="px-2 py-0.5 rounded-full text-[10px] font-bold"
              style={{
                background: accentColor + '15',
                color: accentColor,
              }}
              data-testid="accordion-count"
            >
              {count}
            </span>
          )}
        </div>
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="w-4 h-4 text-text-3" />
        </motion.div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              duration: 0.3,
              ease: [0.25, 0.46, 0.45, 0.94],
            }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-4 pt-1 space-y-3">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
