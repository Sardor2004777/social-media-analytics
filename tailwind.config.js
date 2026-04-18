/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/*.py',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
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
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'gradient-shift': 'gradientShift 12s ease infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        gradientShift: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%':      { backgroundPosition: '100% 50%' },
        },
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #2563eb 100%)',
        'mesh-1': 'radial-gradient(at 20% 20%, rgba(99,102,241,0.55) 0px, transparent 50%), radial-gradient(at 80% 0%, rgba(56,189,248,0.45) 0px, transparent 50%), radial-gradient(at 0% 80%, rgba(168,85,247,0.45) 0px, transparent 50%), radial-gradient(at 90% 90%, rgba(236,72,153,0.35) 0px, transparent 50%)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
};
