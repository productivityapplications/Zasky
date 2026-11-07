import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#ECECEF",
        surface: "#F7F7F5",
        paper: "#FFFFFF",
        ink: "#141414",
        "ink-soft": "#242424",
        muted: "#76767D",
        line: "rgba(17,17,17,0.08)",
        rail: "#F2EF69",
        zest: "#F6EA74",
        coral: "#FF6B5E",
        lavender: "#C7A3F3",
        sky: "#8ED7F6",
        mint: "#9DEBB5",
        rose: "#FF8FAE",
        cream: "#F4D58D",
      },
      fontFamily: {
        sans: ["var(--font-manrope)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-manrope)", "Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        shell: "30px",
        panel: "26px",
        card: "22px",
        field: "14px",
      },
      boxShadow: {
        shell: "0 30px 100px -30px rgba(17,17,17,0.45)",
        card: "0 18px 34px -18px rgba(17,17,17,0.34)",
        darkcard: "0 18px 34px -18px rgba(0,0,0,0.65)",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        rise: "rise 500ms ease-out both",
        "pulse-soft": "pulseSoft 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
