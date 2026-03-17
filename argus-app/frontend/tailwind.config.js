const path = require('path');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    path.join(__dirname, 'index.html'),
    path.join(__dirname, 'src/**/*.{js,jsx}'),
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Consolas', 'monospace'],
      },
      colors: {
        surface: {
          0: 'var(--surface-0)',
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        text: {
          0: 'var(--text-0)',
          1: 'var(--text-1)',
          2: 'var(--text-2)',
          3: 'var(--text-3)',
        },
        accent: {
          DEFAULT: 'var(--accent-base)',
          hover: 'var(--accent-hover)',
          tint: 'var(--accent-tint)',
        },
        status: {
          amber: 'var(--amber-base)',
          'amber-tint': 'var(--amber-tint)',
          violet: 'var(--violet-base)',
          'violet-tint': 'var(--violet-tint)',
          rose: 'var(--rose-base)',
          'rose-tint': 'var(--rose-tint)',
          emerald: 'var(--emerald-base)',
          'emerald-tint': 'var(--emerald-tint)',
          cyan: 'var(--cyan-base)',
          'cyan-tint': 'var(--cyan-tint)',
        },
      },
      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },
      borderRadius: {
        card: '12px',
        badge: '6px',
        btn: '8px',
      },
      animation: {
        'shimmer': 'shimmer 1.5s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
        'fade-in': 'fade-in 0.4s ease-out',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(1)', opacity: '0.6' },
          '100%': { transform: 'scale(2.5)', opacity: '0' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};

