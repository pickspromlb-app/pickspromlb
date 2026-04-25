/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        'mlb-blue': '#002D72',
        'mlb-red': '#D50032',
        'pick-green': '#10B981',
        'pick-yellow': '#F59E0B',
        'pick-orange': '#F97316',
        'pick-red': '#EF4444',
      },
    },
  },
  plugins: [],
}
