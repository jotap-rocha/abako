// Cache da PWA (ADR 031): no logout, tudo o que o app guardou no navegador é apagado.

export async function limparCachesDoApp(): Promise<void> {
  if (typeof caches === "undefined") return;
  const nomes = await caches.keys();
  await Promise.all(nomes.map((nome) => caches.delete(nome)));
}

/** Registra o service worker só no build de produção; em teste e em dev não existe. */
export function registrarServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}
