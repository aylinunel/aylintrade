import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  root: "web",
  plugins: [react()],
  build: {
    outDir: "../site",
    emptyOutDir: true,
    sourcemap: true,
  },
});
