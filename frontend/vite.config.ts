import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// O build vai para `dist/`, que o FastAPI serve na mesma origem da API (ADR 035).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    // Telas inteiras com vários arquivos em paralelo passam de 5 s no PC do dev; sozinhas levam ~2 s.
    testTimeout: 20_000,
  },
});
