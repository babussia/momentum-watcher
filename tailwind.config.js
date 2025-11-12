/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [],
  theme: {
    extend: {},
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js"
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

module.exports = {
  content: ["./app/templates/**/*.html", "./app/static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f14",
        card: "#131a22",
        soft: "#1b2430",
        accent: "#0ea5e9",
        text: "#e5e7eb",
      },
      boxShadow: {
        soft: "0 6px 24px rgba(0,0,0,0.25)",
      },
    },
  },
  plugins: [],
};
