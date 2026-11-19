/** @type {import('tailwindcss').Config} */
const c = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"],
      },
      colors: {
        bg: c("bg"),
        surface: c("surface"),
        subtle: c("subtle"),
        line: c("line"),
        ink: c("ink"),
        muted: c("muted"),
        accent: c("accent"),
        "accent-fg": c("accent-fg"),
        pos: c("pos"),
        "pos-bg": c("pos-bg"),
        neg: c("neg"),
        "neg-bg": c("neg-bg"),
        warn: c("warn"),
        "warn-bg": c("warn-bg"),
        off: c("off"),
        "off-bg": c("off-bg"),
      },
      boxShadow: {
        card: "0 1px 2px rgb(var(--shadow) / 0.06), 0 1px 3px rgb(var(--shadow) / 0.05)",
      },
    },
  },
  plugins: [],
};
