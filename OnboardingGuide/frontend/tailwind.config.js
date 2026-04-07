/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        winmark: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#1e60a0',
          600: '#1a5490',
          700: '#154880',
          800: '#103c70',
          900: '#0b3060',
        },
      },
    },
  },
  plugins: [],
}
