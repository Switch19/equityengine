/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#14163A",
          50: "#F1F1F7",
          100: "#E1E2EF",
          400: "#5C5F8C",
          600: "#33355E",
          900: "#0D0E24",
        },
        paper: "#FAF8F3",
        beacon: {
          DEFAULT: "#F2B705",
          50: "#FEF9E7",
          600: "#C79300",
        },
        verified: {
          DEFAULT: "#2F9E6E",
          50: "#E9F7F0",
        },
        gap: {
          DEFAULT: "#D64545",
          50: "#FBEAEA",
        },
        slate: {
          DEFAULT: "#6B6F8A",
          50: "#F4F4F7",
        },
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        body: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        DEFAULT: "10px",
        lg: "16px",
      },
    },
  },
  plugins: [],
};
