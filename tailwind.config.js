/** @type {import('tailwindcss').Config} */
const defaultTheme = require('tailwindcss/defaultTheme');

module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/*.py',
  ],
  safelist: [
    // Classes built at render time (e.g. bg-{{ k.accent }}-100 in dashboard).
    // Explicit enumeration keeps the bundle small vs. a broad regex safelist.
    ...['brand', 'emerald', 'amber', 'sky', 'rose'].flatMap((c) => [
      `bg-${c}-100`,
      `text-${c}-500`,
      `text-${c}-600`,
      `dark:bg-${c}-900/40`,
      `dark:text-${c}-400`,
    ]),
    // These land on <html>/[data-reveal] from static/js/app.js, never from a
    // template — Tailwind content-scan would otherwise purge them and the
    // dashboard cards would stay invisible after the reveal animation landed.
    'js-reveal',
    'is-visible',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter var"', 'Inter', ...defaultTheme.fontFamily.sans],
        mono: ['"JetBrains Mono"', ...defaultTheme.fontFamily.mono],
        display: ['"Inter var"', 'Inter', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          950: '#1e1b4b',
        },
      },
      fontSize: {
        // Display sizes — tighter tracking for large headlines
        'display-sm':  ['2.5rem',  { lineHeight: '1.1',  letterSpacing: '-0.02em', fontWeight: '700' }],
        'display-md':  ['3.25rem', { lineHeight: '1.08', letterSpacing: '-0.025em', fontWeight: '700' }],
        'display-lg':  ['4rem',    { lineHeight: '1.05', letterSpacing: '-0.03em',  fontWeight: '800' }],
        'display-xl':  ['5rem',    { lineHeight: '1.02', letterSpacing: '-0.035em', fontWeight: '800' }],
        'display-2xl': ['6rem',    { lineHeight: '1',    letterSpacing: '-0.04em',  fontWeight: '800' }],
      },
      letterSpacing: {
        'tightest': '-0.04em',
      },
      borderRadius: {
        'card':   '1rem',      // 16px — matches Linear/Vercel card radius
        'button': '0.625rem',  // 10px — softer than default lg (8)
        'pill':   '9999px',
      },
      boxShadow: {
        // Realistic multi-layer shadows (Linear/Stripe style)
        'soft':    '0 1px 2px rgba(15,23,42,0.04), 0 2px 8px rgba(15,23,42,0.04)',
        'card':    '0 1px 3px rgba(15,23,42,0.05), 0 4px 16px -4px rgba(15,23,42,0.08)',
        'elevate': '0 4px 12px rgba(15,23,42,0.06), 0 16px 32px -8px rgba(15,23,42,0.12)',
        'float':   '0 8px 24px rgba(15,23,42,0.08), 0 24px 48px -12px rgba(15,23,42,0.18)',
        'glow-brand':   '0 0 0 1px rgba(99,102,241,0.25), 0 8px 32px -4px rgba(99,102,241,0.35)',
        'glow-emerald': '0 0 0 1px rgba(16,185,129,0.25), 0 8px 32px -4px rgba(16,185,129,0.35)',
        'ring-brand':   '0 0 0 4px rgba(99,102,241,0.18)',
        'inset-top':    'inset 0 1px 0 rgba(255,255,255,0.08)',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #2563eb 100%)',
        'brand-text':     'linear-gradient(120deg, #4f46e5 0%, #7c3aed 35%, #ec4899 100%)',
        'aurora':         'conic-gradient(from 180deg at 50% 50%, #4f46e5 0deg, #7c3aed 120deg, #ec4899 240deg, #4f46e5 360deg)',
        'mesh-1': 'radial-gradient(at 20% 20%, rgba(99,102,241,0.55) 0px, transparent 50%), radial-gradient(at 80% 0%, rgba(56,189,248,0.45) 0px, transparent 50%), radial-gradient(at 0% 80%, rgba(168,85,247,0.45) 0px, transparent 50%), radial-gradient(at 90% 90%, rgba(236,72,153,0.35) 0px, transparent 50%)',
        'grid-lines': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cpath d='M32 0H0v32' fill='none' stroke='%23e2e8f0' stroke-width='0.5'/%3E%3C/svg%3E\")",
        'grid-lines-dark': "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cpath d='M32 0H0v32' fill='none' stroke='%231e293b' stroke-width='0.5'/%3E%3C/svg%3E\")",
        'noise': "url(\"data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.5 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.55'/%3E%3C/svg%3E\")",
      },
      animation: {
        'fade-in':        'fadeIn 0.5s ease-out',
        'fade-up':        'fadeUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-up':       'slideUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-down':     'slideDown 0.4s cubic-bezier(0.22, 1, 0.36, 1) both',
        'slide-in-right': 'slideInRight 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
        'scale-in':       'scaleIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) both',
        'gradient-shift': 'gradientShift 14s ease-in-out infinite',
        'blob-1':         'blob1 22s ease-in-out infinite',
        'blob-2':         'blob2 26s ease-in-out infinite',
        'blob-3':         'blob3 30s ease-in-out infinite',
        'spin-slow':      'spin 8s linear infinite',
        'aurora-spin':    'aurora 12s linear infinite',
        'bounce-soft':    'bounceSoft 2.4s ease-in-out infinite',
        'pulse-soft':     'pulseSoft 2.4s ease-in-out infinite',
        'shimmer':        'shimmer 2.2s linear infinite',
      },
      keyframes: {
        fadeIn:   { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        fadeUp:   { '0%': { opacity: '0', transform: 'translateY(18px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideUp:  { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideDown:{ '0%': { opacity: '0', transform: 'translateY(-8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        slideInRight: { '0%': { opacity: '0', transform: 'translateX(24px)' }, '100%': { opacity: '1', transform: 'translateX(0)' } },
        scaleIn:  { '0%': { opacity: '0', transform: 'scale(0.94)' }, '100%': { opacity: '1', transform: 'scale(1)' } },
        gradientShift: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%':      { backgroundPosition: '100% 50%' },
        },
        blob1: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%':      { transform: 'translate(60px, -40px) scale(1.1)' },
          '66%':      { transform: 'translate(-40px, 20px) scale(0.9)' },
        },
        blob2: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '33%':      { transform: 'translate(-50px, 30px) scale(1.15)' },
          '66%':      { transform: 'translate(30px, -30px) scale(0.95)' },
        },
        blob3: {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)' },
          '50%':      { transform: 'translate(40px, 40px) scale(1.1)' },
        },
        bounceSoft: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%':      { transform: 'translateY(-6px)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%':      { opacity: '0.75', transform: 'scale(1.08)' },
        },
        aurora: {
          '0%':   { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.22, 1, 0.36, 1)',
        'in-out-expo': 'cubic-bezier(0.87, 0, 0.13, 1)',
      },
      transitionDuration: {
        '400': '400ms',
      },
      backdropBlur: {
        'xs': '2px',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
};
