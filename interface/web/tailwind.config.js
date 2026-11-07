/** Jetons de design MEDIMCOM IA : neutres froids, un bleu d'action, couleurs de verdict sémantiques. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"IBM Plex Sans Arabic"', "system-ui", "sans-serif"],
      },
      colors: {
        canvas: "#F3F5F8",
        surface: "#FFFFFF",
        ink: { DEFAULT: "#132033", soft: "#3A4A5E", muted: "#64748B", faint: "#94A3B8" },
        line: { DEFAULT: "#E3E8EF", strong: "#CBD3DE" },
        brand: { DEFAULT: "#0E3A66", 50: "#EEF4FB" },
        action: { DEFAULT: "#1F63E0", hover: "#1852BE", 50: "#EDF3FE", 100: "#D9E6FD" },
        ok: { DEFAULT: "#13784A", 50: "#E8F5EE" },
        warn: { DEFAULT: "#9A5B00", 50: "#FDF4E3" },
        review: { DEFAULT: "#BB4A0C", 50: "#FDEEE5" },
        danger: { DEFAULT: "#C2281C", 50: "#FDECEA", 600: "#A82016" },
        held: { DEFAULT: "#5B45B8", 50: "#F1EEFB" },
      },
      boxShadow: {
        panel: "0 1px 2px rgba(16,24,40,.04), 0 0 0 1px rgba(16,24,40,.06)",
        pop: "0 12px 32px -8px rgba(16,24,40,.22), 0 0 0 1px rgba(16,24,40,.08)",
        tile: "0 1px 0 rgba(16,24,40,.06)",
      },
      fontSize: { "2xs": ["11px", "14px"] },
      keyframes: {
        fondu: { from: { opacity: "0" }, to: { opacity: "1" } },
        entree: { from: { opacity: "0", transform: "translateY(6px) scale(.98)" }, to: { opacity: "1", transform: "none" } },
        arrivee: { "0%": { boxShadow: "0 0 0 0 rgba(31,99,224,.35)" }, "100%": { boxShadow: "0 0 0 16px rgba(31,99,224,0)" } },
        envol: { "0%": { opacity: "1", transform: "scale(.7)" }, "60%": { opacity: "1", transform: "scale(1.05)" }, "100%": { opacity: "0", transform: "scale(1.15)" } },
        battement: { "0%,100%": { transform: "scale(1)" }, "50%": { transform: "scale(1.08)" } },
      },
      animation: {
        fondu: "fondu .15s ease-out", entree: "entree .18s ease-out", arrivee: "arrivee 1.1s ease-out 2",
        envol: "envol 1s ease-out forwards", battement: "battement 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
