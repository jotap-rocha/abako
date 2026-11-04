import { vi } from "vitest";

import codigoSw from "../../public/sw.js?raw";

type Ouvinte = (evento: unknown) => void;

// Executa o sw.js de verdade num "self" simulado e dispara eventos `fetch` nele.
function carregarSw() {
  const ouvintes = new Map<string, Ouvinte>();
  const cache = { match: vi.fn().mockResolvedValue(undefined), put: vi.fn() };
  const self = {
    location: { origin: "http://abako.localhost:8080" },
    addEventListener: (tipo: string, fn: Ouvinte) => ouvintes.set(tipo, fn),
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  };
  const caches = { open: vi.fn().mockResolvedValue(cache), keys: vi.fn(), delete: vi.fn() };
  const rede = vi.fn().mockResolvedValue(new Response("ok"));
  new Function("self", "caches", "fetch", codigoSw)(self, caches, rede);
  return { ouvintes, caches, rede };
}

function disparar(ouvintes: Map<string, Ouvinte>, metodo: string, url: string) {
  const respondWith = vi.fn();
  ouvintes.get("fetch")?.({ request: { method: metodo, url }, respondWith });
  return respondWith;
}

describe("service worker", () => {
  it("nunca_toca_na_api", () => {
    const { ouvintes, caches, rede } = carregarSw();
    const base = "http://abako.localhost:8080";
    for (const caminho of ["/api/contas", "/api/auth/eu", "/api/openapi.json", "/api"]) {
      expect(disparar(ouvintes, "GET", base + caminho)).not.toHaveBeenCalled();
    }
    expect(caches.open).not.toHaveBeenCalled();
    expect(rede).not.toHaveBeenCalled();
  });

  it("ignora_escrita_e_outras_origens", () => {
    const { ouvintes } = carregarSw();
    const base = "http://abako.localhost:8080";
    expect(disparar(ouvintes, "POST", base + "/assets/app.js")).not.toHaveBeenCalled();
    expect(disparar(ouvintes, "GET", "https://outro.exemplo/assets/app.js")).not.toHaveBeenCalled();
  });

  it("cuida_so_da_casca_estatica", () => {
    const { ouvintes } = carregarSw();
    const base = "http://abako.localhost:8080";
    expect(disparar(ouvintes, "GET", base + "/assets/app.js")).toHaveBeenCalledTimes(1);
    expect(disparar(ouvintes, "GET", base + "/")).toHaveBeenCalledTimes(1);
    expect(disparar(ouvintes, "GET", base + "/icone-192.png")).toHaveBeenCalledTimes(1);
    expect(disparar(ouvintes, "GET", base + "/manifest.webmanifest")).toHaveBeenCalledTimes(1);
  });

  it("telas_e_outras_rotas_vao_direto_para_a_rede", () => {
    const { ouvintes } = carregarSw();
    const base = "http://abako.localhost:8080";
    for (const caminho of ["/saldos", "/lancamentos/novo", "/apix", "/sw.js"]) {
      expect(disparar(ouvintes, "GET", base + caminho)).not.toHaveBeenCalled();
    }
  });

  it("sem_rede_com_cache_serve_o_cache_sem_erro_solto", async () => {
    const { ouvintes, caches, rede } = carregarSw();
    const guardada = new Response("casca guardada");
    caches.open.mockResolvedValue({ match: vi.fn().mockResolvedValue(guardada), put: vi.fn() });
    rede.mockRejectedValue(new TypeError("sem rede"));

    const respondWith = disparar(ouvintes, "GET", "http://abako.localhost:8080/assets/app.js");
    const servida = await (respondWith.mock.calls[0]?.[0] as Promise<Response>);
    expect(await servida.text()).toBe("casca guardada");
  });
});
