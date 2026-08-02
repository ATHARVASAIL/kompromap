/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          0: "rgb(var(--surface-0) / <alpha-value>)",
          1: "rgb(var(--surface-1) / <alpha-value>)",
          2: "rgb(var(--surface-2) / <alpha-value>)",
          3: "rgb(var(--surface-3) / <alpha-value>)",
        },
        border: {
          subtle: "rgb(var(--border-subtle) / <alpha-value>)",
          DEFAULT: "rgb(var(--border-default) / <alpha-value>)",
          strong: "rgb(var(--border-strong) / <alpha-value>)",
        },
        text: {
          primary: "rgb(var(--text-primary) / <alpha-value>)",
          secondary: "rgb(var(--text-secondary) / <alpha-value>)",
          tertiary: "rgb(var(--text-tertiary) / <alpha-value>)",
          disabled: "rgb(var(--text-disabled) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          hover: "rgb(var(--accent-hover) / <alpha-value>)",
        },
        severity: {
          critical: "rgb(var(--severity-critical) / <alpha-value>)",
          high: "rgb(var(--severity-high) / <alpha-value>)",
          medium: "rgb(var(--severity-medium) / <alpha-value>)",
          low: "rgb(var(--severity-low) / <alpha-value>)",
          info: "rgb(var(--severity-info) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "'SFMono-Regular'", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "10px",
        xl: "14px",
      },
      boxShadow: {
        elevated: "0 8px 30px -8px rgb(0 0 0 / 0.5)",
        glow: "0 0 0 1px rgb(var(--accent) / 0.4), 0 0 20px -4px rgb(var(--accent) / 0.5)",
        // Layered shadow — a single flat shadow reads as a sticker; two
        // offsets (tight contact + soft ambient) is how real elevation looks.
        card: "0 1px 2px rgb(0 0 0 / 0.3), 0 8px 24px -12px rgb(0 0 0 / 0.6)",
        "card-hover": "0 2px 4px rgb(0 0 0 / 0.35), 0 16px 40px -16px rgb(0 0 0 / 0.7)",
        "inner-top": "inset 0 1px 0 0 rgb(255 255 255 / 0.04)",
      },
      backgroundImage: {
        // Subtle depth behind the graph canvas so it doesn't read as a flat
        // void — a very low-opacity radial, not a decorative gradient.
        "canvas-depth":
          "radial-gradient(ellipse 80% 60% at 50% 40%, rgb(var(--accent) / 0.045), transparent 70%)",
        "surface-sheen":
          "linear-gradient(180deg, rgb(255 255 255 / 0.03) 0%, transparent 40%)",
      },
      transitionTimingFunction: {
        // Slight overshoot — makes interactive elements feel responsive
        // rather than merely animated.
        snap: "cubic-bezier(0.34, 1.56, 0.64, 1)",
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        "fade-in-scale": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "slide-in-right": {
          "0%": { opacity: "0", transform: "translateX(12px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "toast-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "rise-in": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.95)", opacity: "0.7" },
          "70%": { transform: "scale(1.3)", opacity: "0" },
          "100%": { transform: "scale(1.3)", opacity: "0" },
        },
        "draw-arc": {
          "0%": { strokeDashoffset: "var(--arc-length)" },
          "100%": { strokeDashoffset: "var(--arc-offset)" },
        },
      },
      animation: {
        "fade-in-scale": "fade-in-scale 150ms ease-out",
        "slide-in-right": "slide-in-right 200ms ease-out",
        "fade-in": "fade-in 150ms ease-out backwards",
        "toast-in": "toast-in 180ms ease-out",
        "rise-in": "rise-in 320ms cubic-bezier(0.22, 1, 0.36, 1) backwards",
        shimmer: "shimmer 1.8s infinite",
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.24, 0, 0.38, 1) infinite",
        "draw-arc": "draw-arc 1s cubic-bezier(0.22, 1, 0.36, 1) forwards",
      },
    },
  },
  plugins: [],
};
