import { apagar, escrever } from "./escrita";

function resposta(status: number, cabecalhos: Record<string, string> = {}): Response {
  return new Response(null, { status, headers: cabecalhos });
}

describe("escrita pelo cliente gerado", () => {
  it("traduz_cada_status", async () => {
    expect(await escrever(async () => ({ data: { x: 1 }, response: resposta(201) }))).toEqual({
      tipo: "ok",
      dados: { x: 1 },
    });
    expect(await escrever(async () => ({ response: resposta(401) }))).toEqual({
      tipo: "sessao_expirada",
    });
    expect(await escrever(async () => ({ response: resposta(404) }))).toEqual({
      tipo: "nao_encontrado",
    });
    expect(await escrever(async () => ({ response: resposta(500) }))).toEqual({ tipo: "erro" });
    expect(
      await escrever(async () => {
        throw new TypeError("sem rede");
      }),
    ).toEqual({ tipo: "erro" });
  });

  it("distingue_os_dois_409_pelo_codigo_e_nao_pelo_texto", async () => {
    // AB409 = mudou desde a leitura; AB410 = nome repetido, vínculo usado, já estornada.
    const mudou = await escrever(async () => ({
      error: { detail: "texto qualquer" },
      response: resposta(409, { "X-Abako-Erro": "AB409" }),
    }));
    const repetido = await escrever(async () => ({
      error: { detail: "texto qualquer" },
      response: resposta(409, { "X-Abako-Erro": "AB410" }),
    }));
    expect(mudou).toEqual({ tipo: "desatualizado" });
    expect(repetido).toEqual({ tipo: "conflito" });
    // Sem o cabeçalho, trata como "mudou": o caminho seguro (recarregar).
    expect(await escrever(async () => ({ response: resposta(409) }))).toEqual({
      tipo: "desatualizado",
    });
  });

  it("422_leva_a_mensagem_literal_do_banco", async () => {
    const r = await escrever(async () => ({
      error: { detail: "pessoa com compra vigente" },
      response: resposta(422, { "X-Abako-Erro": "AB422" }),
    }));
    expect(r).toEqual({ tipo: "invalido", mensagem: "pessoa com compra vigente" });
    // Corpo de validação do FastAPI (lista): sem texto único, a tela usa o texto padrão.
    const lista = await escrever(async () => ({
      error: { detail: [{ msg: "x" }] },
      response: resposta(422),
    }));
    expect(lista).toEqual({ tipo: "invalido", mensagem: null });
  });

  it("exclusao_so_vale_com_204", async () => {
    expect(await apagar(async () => ({ response: resposta(204) }))).toEqual({
      tipo: "ok",
      dados: null,
    });
    expect(await apagar(async () => ({ response: resposta(200) }))).toEqual({ tipo: "erro" });
    expect(await apagar(async () => ({ response: resposta(409) }))).toEqual({
      tipo: "desatualizado",
    });
  });
});
