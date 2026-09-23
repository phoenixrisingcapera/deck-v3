/** @type {import('tailwindcss').Config} */
export default {
  content: [],
  theme: {
    extend: {
      colors: {
        // Primary palette from MemoPop brand
        primary: {
          DEFAULT: '#1a3a52',
          50: '#f0f5f8',
          100: '#dae5ed',
          200: '#b5cbdb',
          300: '#8fb1c9',
          400: '#6a97b7',
          500: '#1a3a52',
          600: '#162f43',
          700: '#112434',
          800: '#0d1925',
          900: '#080e16',
        },
        secondary: {
          DEFAULT: '#1dd3d3',
          50: '#e6fafa',
          100: '#ccf5f5',
          200: '#99ebeb',
          300: '#66e1e1',
          400: '#33d7d7',
          500: '#1dd3d3',
          600: '#17a9a9',
          700: '#127f7f',
          800: '#0c5555',
          900: '#062b2b',
        },
        accent: {
          DEFAULT: '#f59e0b',
          50: '#fefce8',
          100: '#fef9c3',
          200: '#fef08a',
          300: '#fde047',
          400: '#facc15',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        // Semantic colors
        background: {
          DEFAULT: '#ffffff',
          alt: '#f8fafc',
        },
        foreground: {
          DEFAULT: '#1a2332',
          muted: '#64748b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
