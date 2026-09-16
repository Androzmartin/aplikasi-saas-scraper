/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Formal, office-toned palette: white / navy / slate / neutral grey.
        navy: {
          50: '#f1f5f9', 100: '#e2e8f0', 200: '#cbd5e1', 300: '#94a3b8',
          400: '#64748b', 500: '#475569', 600: '#334155', 700: '#1e293b',
          800: '#152033', 900: '#0f172a', 950: '#080f1d',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        panel: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
      },
    },
  },
  plugins: [],
}
