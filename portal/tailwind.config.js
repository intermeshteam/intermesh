/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    // src/lib manquait : les jetons de design y vivent, et Tailwind ne
    // generait donc aucune des classes qu'ils declarent. Les surfaces du
    // Control Plane tombaient sur le fond clair du body, ce qui donnait une
    // barre laterale blanche sous un contenu sombre.
    './src/lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        intermesh: {
          bg: '#0A0E1A',
          card: '#111827',
          border: '#1E293B',
          cyan: '#00D4FF',
          emerald: '#10B981',
          amber: '#F59E0B',
          red: '#EF4444'
        }
      },
      fontFamily: {
        sans: ['var(--font-inter)', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
