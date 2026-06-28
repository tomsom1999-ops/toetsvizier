import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "./",
  plugins: [tailwindcss()],
  build: {
    outDir: "../toetsanalyse/dashboard_dist",
    emptyOutDir: true,
  },
});
