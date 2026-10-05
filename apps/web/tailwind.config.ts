import type { Config } from "tailwindcss";

/**
 * "Financial terminal" dark-first theme (docs/10-ux-design.md §2).
 * Semantic colors: green=up/bullish, red=down/bearish, amber=caution, blue=info.
 */
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0a0e14",
          panel: "#0f1520",
          border: "#1c2432",
          muted: "#8b98a9",
        },
        up: "#22c55e",
        down: "#ef4444",
        caution: "#f59e0b",
        info: "#3b82f6",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
