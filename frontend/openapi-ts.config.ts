import { defineConfig } from "@hey-api/openapi-ts";

// O contrato é `openapi.json` (exportado do FastAPI por `python -m scripts.exportar_openapi`).
// A checagem de defasagem (tests/contracts/test_cliente_openapi.py) gera em outra pasta
// via ABAKO_GEN_OUT e compara com o cliente versionado.
export default defineConfig({
  input: "openapi.json",
  output: process.env.ABAKO_GEN_OUT ?? "src/api/gerado",
  plugins: ["@hey-api/client-fetch", "@hey-api/typescript", "@hey-api/sdk"],
});
