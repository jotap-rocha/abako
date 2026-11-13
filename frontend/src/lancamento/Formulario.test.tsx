import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";

import type { LancamentoSaida } from "../api/gerado";
import * as api from "../api/lancamentos";
import { CONTAS } from "./contasDeTeste";
import { Formulario } from "./Formulario";

vi.mock("../api/lancamentos");
const apiLanc = vi.mocked(api);

const SALVO: LancamentoSaida = {
  transacao_id: 10,
  versao: 1,
  tipo: "debito",
  data: "2026-11-04",
  valor: "50.00",
  conta_id: 1,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: null,
};

function renderizar() {
  return render(
    <Formulario contas={CONTAS} aoSalvar={vi.fn()} aoSessaoExpirar={vi.fn()} />,
  );
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("formulário de lançamento", () => {
  it("campos_por_tipo", async () => {
    const usuario = userEvent.setup();
    renderizar();
    const tipo = screen.getByLabelText("Tipo");

    // Despesa: um valor só, sem destino.
    expect(screen.getByLabelText("Valor (R$)")).toBeInTheDocument();
    expect(screen.queryByLabelText("Conta de destino")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Rendimento bruto (R$)")).not.toBeInTheDocument();

    // Transferência: destino, sem a conta de benefício nem a de origem.
    await usuario.selectOptions(tipo, "transferencia");
    const destino = screen.getByLabelText("Conta de destino");
    expect(destino).toBeInTheDocument();
    expect(screen.getByLabelText("Conta de origem")).toBeInTheDocument();
    expect(destino).not.toHaveTextContent("Vale");
    expect(destino).not.toHaveTextContent("Banco A");

    // Investimento: só contas de investimento como destino.
    await usuario.selectOptions(tipo, "investimento");
    const destinoInv = screen.getByLabelText("Conta de destino");
    expect(destinoInv).toHaveTextContent("Corretora");
    expect(destinoInv).not.toHaveTextContent("Banco A");

    // Rendimento: bruto e imposto no lugar do valor, sem destino.
    await usuario.selectOptions(tipo, "rendimento");
    expect(screen.getByLabelText("Rendimento bruto (R$)")).toBeInTheDocument();
    expect(screen.getByLabelText("Imposto (R$)")).toBeInTheDocument();
    expect(screen.queryByLabelText("Valor (R$)")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Conta de destino")).not.toBeInTheDocument();

    // Crédito: só cartão, com parcelas e a pessoa (opcional); o valor é o total da compra.
    await usuario.selectOptions(tipo, "credito");
    expect(screen.getByLabelText("Cartão")).toHaveTextContent("Cartão A");
    expect(screen.getByLabelText("Cartão")).not.toHaveTextContent("Banco A");
    expect(screen.getByLabelText("Parcelas")).toBeInTheDocument();
    expect(screen.getByLabelText("De quem é a compra")).toBeInTheDocument();
    expect(screen.getByLabelText("Valor total da compra (R$)")).toBeInTheDocument();

    // Repasse: conta corrente e a pessoa obrigatória, sem parcelas.
    await usuario.selectOptions(tipo, "repasse");
    expect(screen.getByLabelText("Quem repassou")).toBeInTheDocument();
    expect(screen.queryByLabelText("Parcelas")).not.toBeInTheDocument();
    expect(apiLanc.criarLancamento).not.toHaveBeenCalled();
  });

  it("mesma_chave_no_retry", async () => {
    const usuario = userEvent.setup();
    apiLanc.criarLancamento
      .mockResolvedValueOnce({ tipo: "erro" })
      .mockResolvedValueOnce({ tipo: "ok", lancamento: SALVO, repetido: false })
      .mockResolvedValueOnce({ tipo: "ok", lancamento: SALVO, repetido: false });
    renderizar();

    await usuario.type(screen.getByLabelText("Valor (R$)"), "50,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível falar com o servidor");
    // O que foi digitado continua lá, e nada foi reenviado sozinho.
    expect(screen.getByLabelText("Valor (R$)")).toHaveValue("50,00");
    expect(apiLanc.criarLancamento).toHaveBeenCalledTimes(1);

    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Lançamento salvo");
    const [primeira, segunda] = apiLanc.criarLancamento.mock.calls;
    expect(segunda?.[0]).toBe(primeira?.[0]);
    expect(primeira?.[1]).toMatchObject({ tipo: "debito", valor: "50.00", conta_id: 1 });

    // Depois do sucesso, o próximo lançamento é outro: chave nova.
    await usuario.type(screen.getByLabelText("Valor (R$)"), "10,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    await vi.waitFor(() => expect(apiLanc.criarLancamento).toHaveBeenCalledTimes(3));
    expect(apiLanc.criarLancamento.mock.calls[2]?.[0]).not.toBe(primeira?.[0]);
  });
});

describe("chave de idempotência", () => {
  it("chave_nova_se_algo_mudar_depois_do_erro", async () => {
    const usuario = userEvent.setup();
    apiLanc.criarLancamento
      .mockResolvedValueOnce({ tipo: "erro" })
      .mockResolvedValueOnce({ tipo: "erro" })
      .mockResolvedValueOnce({ tipo: "ok", lancamento: SALVO, repetido: false });
    renderizar();
    const enviar = () => usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));

    await usuario.type(screen.getByLabelText("Valor (R$)"), "50,00");
    await enviar();
    await screen.findByRole("alert");
    // Nada mudou: o retry leva a mesma chave (o servidor não duplica se o 1o gravou).
    await enviar();
    await vi.waitFor(() => expect(apiLanc.criarLancamento).toHaveBeenCalledTimes(2));
    // O valor mudou: é outro lançamento, então chave nova.
    await usuario.clear(screen.getByLabelText("Valor (R$)"));
    await usuario.type(screen.getByLabelText("Valor (R$)"), "60,00");
    await enviar();
    await vi.waitFor(() => expect(apiLanc.criarLancamento).toHaveBeenCalledTimes(3));
    const [primeira, segunda, terceira] = apiLanc.criarLancamento.mock.calls;
    expect(segunda?.[0]).toBe(primeira?.[0]);
    expect(terceira?.[0]).not.toBe(primeira?.[0]);
    expect(terceira?.[1]).toMatchObject({ valor: "60.00" });
  });
});

describe("conta escolhida ao trocar de tipo", () => {
  it("volta_a_escolher_se_a_conta_nao_serve_ao_novo_tipo", async () => {
    const usuario = userEvent.setup();
    renderizar();

    // Despesa no vale é permitida; transferência e rendimento recusam conta de benefício.
    const conta = screen.getByLabelText("Conta de onde saiu");
    await usuario.selectOptions(conta, "Vale");
    expect(conta).toHaveValue("3");
    await usuario.selectOptions(screen.getByLabelText("Tipo"), "transferencia");
    expect(screen.getByLabelText("Conta de origem")).toHaveValue("");

    // Uma conta que serve aos dois tipos continua escolhida.
    await usuario.selectOptions(screen.getByLabelText("Conta de origem"), "Banco A");
    await usuario.selectOptions(screen.getByLabelText("Tipo"), "rendimento");
    expect(screen.getByLabelText("Conta que rendeu")).toHaveValue("1");
  });
});
