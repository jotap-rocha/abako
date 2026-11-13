import { afterEach, vi } from "vitest";

import indexHtml from "../../index.html?raw";
import manifestoBruto from "../../public/manifest.webmanifest?raw";
import codigoSw from "../../public/sw.js?raw";
import { limparCachesDoApp } from "./cache";

// Todo código de produção do front, exceto o cliente gerado, testes e a configuração dos testes.
const fontes = import.meta.glob(
  ["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../api/gerado/**", "!../setupTests.ts"],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

// Arquivos da pasta public (só os nomes importam aqui).
const publicos = Object.keys(import.meta.glob("../../public/*.png"));

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
  return { ouvintes, cache, caches, rede };
}

function disparar(ouvintes: Map<string, Ouvinte>, url: string, cabecalhos: Record<string, string> = {}) {
  const respondWith = vi.fn();
  ouvintes.get("fetch")?.({
    request: { method: "GET", url, headers: new Headers(cabecalhos) },
    respondWith,
  });
  return respondWith;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PWA", () => {
  it("instalavel", () => {
    // Para o Chrome oferecer a instalação: manifesto ligado na página, nome, início, modo
    // independente e ícones de 192 e 512 que existem de verdade.
    expect(indexHtml).toContain('rel="manifest" href="/manifest.webmanifest"');
    const manifesto = JSON.parse(manifestoBruto) as {
      name: string;
      start_url: string;
      scope: string;
      display: string;
      icons: { src: string; sizes: string; type: string }[];
    };
    expect(manifesto.name).toBe("abako");
    expect(manifesto.start_url).toBe("/");
    expect(manifesto.scope).toBe("/");
    expect(manifesto.display).toBe("standalone");
    for (const tamanho of ["192x192", "512x512"]) {
      const icone = manifesto.icons.find((i) => i.sizes === tamanho);
      expect(icone?.type).toBe("image/png");
      expect(publicos).toContain(`../../public${icone?.src ?? "/ausente"}`);
    }
    // O service worker é registrado pelo app.
    expect(fontes["../main.tsx"]).toContain("registrarServiceWorker()");
    expect(fontes["./cache.ts"]).toContain('register("/sw.js")');
  });

  it("sem_cache_autenticado", async () => {
    // 1. O service worker nunca toca na API, nem com credencial, nem com cabeçalho de autorização.
    const { ouvintes, cache, caches, rede } = carregarSw();
    const base = "http://abako.localhost:8080";
    for (const caminho of ["/api/contas", "/api/lancamentos?de=2026-01-01", "/api/pessoas/a-receber"]) {
      const resposta = disparar(ouvintes, base + caminho, { Authorization: "Bearer x", Cookie: "s=1" });
      expect(resposta).not.toHaveBeenCalled();
    }
    expect(caches.open).not.toHaveBeenCalled();
    expect(rede).not.toHaveBeenCalled();
    expect(cache.put).not.toHaveBeenCalled();

    // 2. Telas (rotas do app) também vão direto à rede: só a casca pública é guardada.
    for (const caminho of ["/lancamentos", "/pessoas", "/parametros", "/recorrentes"]) {
      expect(disparar(ouvintes, base + caminho)).not.toHaveBeenCalled();
    }

    // 3. O que é guardado é só a casca estática pública (e só se a resposta for ok).
    const respondWith = disparar(ouvintes, base + "/assets/app-abc123.js");
    await (respondWith.mock.calls[0]?.[0] as Promise<Response>);
    await vi.waitFor(() => expect(cache.put).toHaveBeenCalledTimes(1));

    // 4. O código do service worker não menciona rotas autenticadas.
    expect(codigoSw).not.toMatch(/\/api\/(?!\s*$)[a-z]/);

    // 5. No logout, todos os caches do app são apagados.
    const apagar = vi.fn().mockResolvedValue(true);
    vi.stubGlobal("caches", { keys: vi.fn().mockResolvedValue(["abako-shell-v1", "outro"]), delete: apagar });
    await limparCachesDoApp();
    expect(apagar).toHaveBeenCalledWith("abako-shell-v1");
    expect(apagar).toHaveBeenCalledWith("outro");
  });

  it("nada_pessoal_no_navegador", () => {
    // Nenhum armazenamento do navegador, cookie escrito à mão nem console no código do app:
    // dado financeiro e nome de pessoa só vivem na tela, durante a sessão (ADR 031, 050).
    const proibido = /\b(localStorage|sessionStorage|indexedDB|document\.cookie|console\.)/;
    const achados = Object.entries(fontes)
      .filter(([, codigo]) => proibido.test(codigo))
      .map(([arquivo]) => arquivo);
    expect(Object.keys(fontes).length).toBeGreaterThan(0);
    expect(achados).toEqual([]);
  });
});
