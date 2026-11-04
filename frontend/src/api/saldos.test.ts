import { afterEach, beforeEach, vi } from "vitest";

import { criarConta } from "./contas";
import { client } from "./gerado/client.gen";
import { listarDivergencias, listarSaldos, registrarSnapshot } from "./saldos";

// Só o `fetch` do navegador é simulado; os módulos e o cliente gerado rodam de verdade.
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
  client.setConfig({ baseUrl: "http://abako.localhost:8080" });
});

afterEach(() => {
  fetchSimulado.mockReset();
  vi.unstubAllGlobals();
});

const SNAPSHOT = {
  snapshot_id: 1,
  conta_id: 5,
  data: "2026-11-04",
  valor: "10.00",
  saldo_inicial: true,
  saldo_derivado: null,
  divergencia: null,
};

describe("api de saldos", () => {
  it("listar_saldos_mapeia_os_status", async () => {
    const saldos = [
      {
        conta_id: 1,
        nome: "A",
        conta_beneficio: false,
        saldo: "12345678901234567.89",
        snapshot_data: null,
        snapshot_valor: null,
      },
    ];
    fetchSimulado.mockResolvedValueOnce(resposta(200, saldos));
    // O texto da API chega intacto (sem virar `number`).
    expect(await listarSaldos()).toEqual({ tipo: "ok", saldos });
    expect(ultimaRequisicao().url).toContain("/api/saldos");

    fetchSimulado.mockResolvedValueOnce(resposta(401, { detail: "x" }));
    expect(await listarSaldos()).toEqual({ tipo: "sessao_expirada" });
    fetchSimulado.mockResolvedValueOnce(resposta(500, { detail: "x" }));
    expect(await listarSaldos()).toEqual({ tipo: "erro" });
    fetchSimulado.mockRejectedValueOnce(new TypeError("rede"));
    expect(await listarSaldos()).toEqual({ tipo: "erro" });
  });

  it("listar_divergencias_mapeia_os_status", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(200, []));
    expect(await listarDivergencias()).toEqual({ tipo: "ok", divergencias: [] });
    expect(ultimaRequisicao().url).toContain("/api/r4");

    fetchSimulado.mockResolvedValueOnce(resposta(401, { detail: "x" }));
    expect(await listarDivergencias()).toEqual({ tipo: "sessao_expirada" });
    fetchSimulado.mockRejectedValueOnce(new TypeError("rede"));
    expect(await listarDivergencias()).toEqual({ tipo: "erro" });
  });

  it("registrar_snapshot_envia_texto_e_mapeia_os_status", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(201, SNAPSHOT));
    expect(await registrarSnapshot(5, "2026-11-04", "1234.56")).toEqual({
      tipo: "ok",
      snapshot: SNAPSHOT,
    });
    const req = ultimaRequisicao();
    expect(req.method).toBe("POST");
    expect(req.url).toContain("/api/contas/5/snapshots");
    // O valor vai como texto no JSON, nunca como número (INV-14).
    expect(await req.text()).toBe('{"data":"2026-11-04","valor":"1234.56"}');

    const casos: [number, string][] = [
      [401, "sessao_expirada"],
      [404, "conta_nao_encontrada"],
      [422, "invalido"],
      [403, "erro"],
      [500, "erro"],
    ];
    for (const [status, tipo] of casos) {
      fetchSimulado.mockResolvedValueOnce(resposta(status, { detail: "x" }));
      expect([status, await registrarSnapshot(5, "2026-11-04", "1.00")]).toEqual([
        status,
        { tipo },
      ]);
    }
    fetchSimulado.mockRejectedValueOnce(new TypeError("rede"));
    expect(await registrarSnapshot(5, "2026-11-04", "1.00")).toEqual({ tipo: "erro" });
  });
});

describe("api de contas", () => {
  it("criar_conta_mapeia_os_status", async () => {
    const conta = { conta_id: 9, nome: "Nova", conta_beneficio: true };
    fetchSimulado.mockResolvedValueOnce(resposta(201, conta));
    expect(await criarConta("Nova", true)).toEqual({ tipo: "ok", conta });
    const req = ultimaRequisicao();
    expect(req.method).toBe("POST");
    expect(await req.text()).toBe('{"nome":"Nova","conta_beneficio":true}');

    const casos: [number, string][] = [
      [401, "sessao_expirada"],
      [409, "nome_repetido"],
      [422, "invalido"],
      [500, "erro"],
    ];
    for (const [status, tipo] of casos) {
      fetchSimulado.mockResolvedValueOnce(resposta(status, { detail: "x" }));
      expect([status, await criarConta("X", false)]).toEqual([status, { tipo }]);
    }
    fetchSimulado.mockRejectedValueOnce(new TypeError("rede"));
    expect(await criarConta("X", false)).toEqual({ tipo: "erro" });
  });
});
