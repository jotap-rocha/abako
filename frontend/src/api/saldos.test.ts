import { afterEach, beforeEach, vi } from "vitest";

import { criarConta, editarConta, obterConta } from "./contas";
import { client } from "./gerado/client.gen";
import { listarDivergencias, listarSaldos, registrarSnapshot } from "./saldos";

// Só o `fetch` do navegador é simulado; os módulos e o cliente gerado rodam de verdade.
const fetchSimulado = vi.fn<typeof fetch>();

function resposta(status: number, corpo?: unknown, codigo?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (codigo !== undefined) headers["X-Abako-Erro"] = codigo;
  return new Response(corpo === undefined ? null : JSON.stringify(corpo), { status, headers });
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
        tipo: "corrente",
        conta_mae_id: null,
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
    const conta = {
      conta_id: 9,
      nome: "Nova",
      conta_beneficio: true,
      tipo: "beneficio",
      conta_mae_id: null,
      versao: 1,
    };
    fetchSimulado.mockResolvedValueOnce(resposta(201, conta));
    expect(await criarConta("Nova", "beneficio", null)).toEqual({ tipo: "ok", conta });
    const req = ultimaRequisicao();
    expect(req.method).toBe("POST");
    expect(await req.text()).toBe(
      '{"nome":"Nova","tipo":"beneficio","conta_beneficio":true,"conta_mae_id":null}',
    );

    const casos: [number, unknown][] = [
      [401, { tipo: "sessao_expirada" }],
      [409, { tipo: "nome_repetido" }],
      // A mensagem de regra do servidor chega para a tela mostrar.
      [422, { tipo: "invalido", mensagem: "x" }],
      [500, { tipo: "erro" }],
    ];
    for (const [status, esperado] of casos) {
      fetchSimulado.mockResolvedValueOnce(resposta(status, { detail: "x" }));
      expect([status, await criarConta("X", "corrente", null)]).toEqual([status, esperado]);
    }
    fetchSimulado.mockRejectedValueOnce(new TypeError("rede"));
    expect(await criarConta("X", "corrente", null)).toEqual({ tipo: "erro" });
  });
});

describe("api de edição de conta", () => {
  const conta = {
    conta_id: 3,
    nome: "Caixinha",
    conta_beneficio: false,
    tipo: "reserva",
    conta_mae_id: 1,
    versao: 2,
  };

  it("obter_e_editar_mapeiam_os_status", async () => {
    fetchSimulado.mockResolvedValueOnce(resposta(200, conta));
    expect(await obterConta(3)).toEqual({ tipo: "ok", conta });
    fetchSimulado.mockResolvedValueOnce(resposta(404, { detail: "x" }));
    expect(await obterConta(3)).toEqual({ tipo: "nao_encontrada" });

    fetchSimulado.mockResolvedValueOnce(resposta(200, conta));
    expect(await editarConta(3, 1, "Caixinha", "reserva", 1)).toEqual({ tipo: "ok", conta });
    const req = ultimaRequisicao();
    expect(req.method).toBe("PUT");
    expect(req.url).toContain("/api/contas/3");
    expect(await req.text()).toBe(
      '{"nome":"Caixinha","tipo":"reserva","conta_mae_id":1,"versao":1}',
    );

    // O código no cabeçalho decide entre os dois 409; o texto da mensagem não importa.
    const casos: [number, unknown, string | undefined, unknown][] = [
      [409, { detail: "qualquer texto" }, "AB409", { tipo: "desatualizada" }],
      [409, { detail: "qualquer texto" }, "AB410", { tipo: "nome_repetido" }],
      [422, { detail: "regra x" }, "AB422", { tipo: "invalido", mensagem: "regra x" }],
      [422, { detail: [{ msg: "pydantic" }] }, undefined, { tipo: "invalido", mensagem: null }],
      [401, { detail: "x" }, undefined, { tipo: "sessao_expirada" }],
      [404, { detail: "x" }, "AB404", { tipo: "nao_encontrada" }],
      [500, { detail: "x" }, undefined, { tipo: "erro" }],
    ];
    for (const [status, corpo, codigo, esperado] of casos) {
      fetchSimulado.mockResolvedValueOnce(resposta(status, corpo, codigo));
      expect([status, await editarConta(3, 1, "C", "reserva", null)]).toEqual([status, esperado]);
    }
    fetchSimulado.mockRejectedValueOnce(new TypeError("rede"));
    expect(await editarConta(3, 1, "C", "reserva", null)).toEqual({ tipo: "erro" });
  });
});
