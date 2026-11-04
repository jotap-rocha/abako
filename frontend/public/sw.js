// Service worker do abako (ADR 031). Só guarda a casca estática (HTML, JS, CSS, ícones).
// NUNCA toca em /api: nenhuma resposta autenticada da API é lida, guardada ou servida daqui.
// O logout apaga todos os caches (frontend/src/pwa/cache.ts). Sem uso offline na v1.

const CACHE = "abako-shell-v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    (async () => {
      const nomes = await caches.keys();
      await Promise.all(nomes.filter((n) => n !== CACHE).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (evento) => {
  const requisicao = evento.request;
  const url = new URL(requisicao.url);
  // Lista fechada da casca pública: página inicial, ativos com hash, ícones e manifesto.
  // Qualquer outra rota (inclusive /api e as telas) segue direto para a rede.
  const ehCasca =
    url.pathname === "/" ||
    url.pathname.startsWith("/assets/") ||
    url.pathname.startsWith("/icone-") ||
    url.pathname === "/manifest.webmanifest";
  const ehEstatico =
    requisicao.method === "GET" && url.origin === self.location.origin && ehCasca;
  if (!ehEstatico) return; // o navegador segue o caminho normal

  evento.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      const guardada = await cache.match(requisicao);
      const rede = fetch(requisicao).then((resposta) => {
        if (resposta.ok) void cache.put(requisicao, resposta.clone());
        return resposta;
      });
      if (guardada) {
        // Revalida em segundo plano; sem rede, o que está guardado continua valendo.
        rede.catch(() => {});
        return guardada;
      }
      return rede;
    })(),
  );
});
