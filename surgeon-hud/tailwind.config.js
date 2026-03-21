/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'hud-black': 'rgba(0, 0, 0, 0.6)', // Glassmorphism base
      }
    },
  },
  plugins: [],
}

