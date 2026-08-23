import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";


export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../web",
    emptyOutDir: true,
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
