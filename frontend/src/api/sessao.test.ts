import { afterEach, beforeEach, vi } from "vitest";

import { client } from "./gerado/client.gen";
import { entrar, recuperarSessao, sair } from "./sessao";

// Só o `fetch` do navegador é simulado; o módulo e o cliente gerado rodam de verdade.
const fetchSimulado = vi.fn<typeof fetch>();

function resposta(status: number, corpo?: unknown): Response {
  return new Response(corpo === undefined ? null : JSON.stringify(corpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function ultimaRequisicao(): Request {
  const chamada = fetchSimulado.mock.calls.at(-1);
  if (chamada === undefined) throw new Error("nenhuma requisição feita");
  return chamada[0] as Request;
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSimulado);
  // No navegador a URL relativa vale; o Request do Node exige uma base absoluta.
  client.setConfig({ baseUrl: "http://abako.localhost:8080" });
});

afterEach(async () => {
  // Zera o token CSRF guardado em memória entre os testes.
  fetchSimulado.mockResolvedValue(resposta(204));
  await sair();
  fetchSimulado.mockReset();
  vi.unstubAllGlobals();
});

describe("sessao", () => {
  it("entrar_ok_guarda_o_token_e_o_manda_so_em_escrita", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(200, { csrf_token: "tok-123" }));
    expect(await entrar("joao", "senha")).toBe("ok");
    const login = ultimaRequisicao();
    expect(login.url).toContain("/api/auth/login");
    expect(login.headers.get("X-CSRF-Token")).toBeNull(); // o login ainda não tem token

    fetchSimulado.mockResolvedValueOnce(resposta(204));
    await sair();
    const logout = ultimaRequisicao();
    expect(logout.method).toBe("POST");
    expect(logout.headers.get("X-CSRF-Token")).toBe("tok-123");

    fetchSimulado.mockResolvedValueOnce(resposta(200, { csrf_token: "tok-123" }));
    await recuperarSessao();
    expect(ultimaRequisicao().method).toBe("GET");
    expect(ultimaRequisicao().headers.get("X-CSRF-Token")).toBeNull(); // leitura não leva token
  });

  it("entrar_mapeia_os_status", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(401, { detail: "x" }));
    expect(await entrar("a", "b")).toBe("credenciais");
    fetchSimulado.mockResolvedValueOnce(resposta(429, { detail: "x" }));
    expect(await entrar("a", "b")).toBe("bloqueado");
    fetchSimulado.mockResolvedValueOnce(resposta(500, { detail: "x" }));
    expect(await entrar("a", "b")).toBe("erro");
    fetchSimulado.mockRejectedValueOnce(new TypeError("sem rede"));
    expect(await entrar("a", "b")).toBe("erro");
  });

  it("recuperar_sessao", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(401, { detail: "x" }));
    expect(await recuperarSessao()).toBe(false);
    fetchSimulado.mockRejectedValueOnce(new TypeError("sem rede"));
    expect(await recuperarSessao()).toBe(false);
    fetchSimulado.mockResolvedValueOnce(resposta(200, { csrf_token: "tok-9" }));
    expect(await recuperarSessao()).toBe(true);
  });

  it("sair_esquece_o_token_mesmo_com_falha", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(200, { csrf_token: "tok-1" }));
    await entrar("a", "b");

    fetchSimulado.mockRejectedValueOnce(new TypeError("sem rede"));
    await sair(); // o cliente gerado devolve o erro de rede sem lançar

    fetchSimulado.mockResolvedValueOnce(resposta(403, { detail: "x" }));
    await sair();
    expect(ultimaRequisicao().headers.get("X-CSRF-Token")).toBeNull();
  });
});
