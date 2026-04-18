/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Align with app/static/styles.css (light dashboard)
        dash: {
          bg: "#f4f6fa",
          surface: "#ffffff",
          text: "#1a2332",
          muted: "#5c6b82",
          accent: "#5b9fd4",
          border: "rgba(26, 35, 50, 0.12)",
        },
      },
      maxWidth: {
        layout: "1280px",
      },
      borderRadius: {
        dash: "10px",
      },
    },
  },
  plugins: [],
};
