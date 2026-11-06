/** Locked palette. Utilities read the CSS variables in styles.css, so
 *  html[data-theme="morning"|"evening"] still switches the same pair.
 *  There is no light theme and no default blue, green, or slate scale.
 *
 *  Evening: canvas #050403, cream #f3e6d4, cream-dim #c4b29a, card #eddcc6,
 *  ink-card #1a1613, muted-card #655d54, accent #d39a4e, accent-deep #b8833d,
 *  accent-ink #7a4e17 (5.34:1 on card #eddcc6; #8a5a1c was 4.40:1),
 *  success #4a5726 (5.84:1 evening card, 7.54:1 morning card),
 *  success-canvas #c6d09a (12.57:1 evening canvas, 10.77:1 morning canvas),
 *  danger-card #8e3d32, danger-canvas #e7b4a8.
 *  Morning accent-ink stays #8f621f (5.14:1 on #fffaf3).
 *  Body text is 4.5:1. Large text and UI chrome are 3:1.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  corePlugins: {
    preflight: false,
  },
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      canvas: "var(--canvas)",
      cream: "var(--cream)",
      "cream-dim": "var(--cream-dim)",
      card: "var(--card)",
      "ink-card": "var(--ink-card)",
      "muted-card": "var(--muted-card)",
      accent: "var(--accent)",
      "accent-deep": "var(--accent-deep)",
      "accent-ink": "var(--accent-ink)",
      success: "var(--success)",
      "success-canvas": "var(--success-canvas)",
      "danger-card": "var(--danger-card)",
      "danger-canvas": "var(--danger-canvas)",
    },
    extend: {
      fontFamily: {
        sans: ["Inter", '"Avenir Next"', '"Segoe UI"', '"Helvetica Neue"', "sans-serif"],
        serif: ["Newsreader", '"Iowan Old Style"', "Palatino", "Georgia", '"Liberation Serif"', "serif"],
      },
      borderRadius: {
        house: "12px",
      },
    },
  },
  plugins: [],
};
