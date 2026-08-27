/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        nexus: {
          bg: '#0A0E1A',
          card: '#111827',
          border: '#1E293B',
          cyan: '#00D4FF',
          emerald: '#10B981',
          amber: '#F59E0B',
          red: '#EF4444'
        }
      }
    },
  },
  plugins: [],
}
