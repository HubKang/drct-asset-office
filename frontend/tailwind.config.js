/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef5ff",
          100: "#dbe9ff",
          500: "#245db3",
          700: "#1b4584",
          900: "#112746"
        }
      },
      boxShadow: {
        soft: "0 10px 30px -18px rgba(15, 23, 42, 0.35)"
      }
    }
  },
  plugins: []
};
