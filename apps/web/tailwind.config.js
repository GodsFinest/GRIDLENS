/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        grid: {
          bg: '#0B0F19',
          surface: '#111827',
          card: '#1A2234',
          border: '#2A364F',
          cyan: '#00F0FF',
          amber: '#FFB800',
          emerald: '#10B981',
          rose: '#F43F5E',
          text: '#F3F4F6',
          muted: '#9CA3AF',
        },
      },
    },
  },
  plugins: [],
};
