import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as apiEstorno from "../api/estorno";
import type { EstornoSaida, LancamentoSaida } from "../api/gerado";
import * as apiLancamentos from "../api/lancamentos";
import * as apiLeitura from "../api/leitura";
import * as apiSaldos from "../api/saldos";
import * as sessao from "../api/sessao";
import { CONTAS } from "../lancamento/contasDeTeste";
import { Estornar, estornoIntegral } from "./Estornar";

vi.mock("../api/estorno");
vi.mock("../api/lancamentos");
vi.mock("../api/leitura");
vi.mock("../api/saldos");
vi.mock("../api/sessao");
const estornar = vi.mocked(apiEstorno).estornarCompra;
const lanc = vi.mocked(apiLancamentos);
const leitura = vi.mocked(apiLeitura);
const saldos = vi.mocked(apiSaldos);
const apiSessao = vi.mocked(sessao);

const COMPRA: LancamentoSaida = {
  transacao_id: 10,
  versao: 4,
  tipo: "credito",
  data: "2026-11-04",
  valor: "100.00",
  conta_id: 4,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: "geladeira",
  parcelas: 2,
  competencia: "2026-11",
  estorno_de: null,
  estorno_credito: null,
  pessoa_id: null,
};

// Incoerente de propósito: o limite devolvido não é "total menos pago". A tela mostra o que veio.
const INTEGRAL: EstornoSaida = {
  estorno_id: 11,
  competencia_credito: "2026-12",
  total: "100.00",
  pago: "0.00",
  limite_devolvido: "70.00",
};
const COM_PAGO: EstornoSaida = {
  estorno_id: 11,
  competencia_credito: "2026-12",
  total: "100.00",
  pago: "30.00",
  limite_devolvido: "999.00",
};

afterEach(() => {
  vi.resetAllMocks();
});

function painel(extra: Partial<Parameters<typeof Estornar>[0]> = {}) {
  const props = {
    compra: COMPRA,
    aoEstornar: vi.fn(),
    aoSessaoExpirar: vi.fn(),
    aoFechar: vi.fn(),
    aoDesatualizado: vi.fn(),
    ...extra,
  };
  render(<Estornar {...props} />);
  return props;
}

describe("estorno", () => {
  it("reconhece_o_zero_do_servidor_pelo_texto", () => {
    for (const zero of ["0", "0.0", "0.00", "0.0000", "-0.00"]) {
      expect(estornoIntegral(zero)).toBe(true);
    }
    for (const pago of ["10.00", "0.01", "100", "0.10", "-1.00", ""]) {
      expect(estornoIntegral(pago)).toBe(false);
    }
  });

  it("duplo_clique_envia_uma_vez_so", async () => {
    let concluir: (r: Awaited<ReturnType<typeof estornar>>) => void = () => undefined;
    estornar.mockImplementation(
      () => new Promise((resolve) => {
        concluir = resolve;
      }),
    );
    painel();
    const form = screen.getByRole("form", { name: "Estornar compra" });
    // Dois envios seguidos, sem esperar a resposta do primeiro.
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(estornar).toHaveBeenCalledTimes(1);
    concluir({ tipo: "ok", dados: INTEGRAL });
    expect(await screen.findByRole("status", { name: "Resultado do estorno" })).toBeInTheDocument();
    expect(estornar).toHaveBeenCalledTimes(1);
  });

  it("tipos_de_estorno", async () => {
    const usuario = userEvent.setup();

    // Antes de enviar: as regras em texto fixo (ADR 044).
    estornar.mockResolvedValueOnce({ tipo: "ok", dados: INTEGRAL });
    const props = painel();
    const regras = screen.getByRole("form", { name: "Estornar compra" });
    expect(regras).toHaveTextContent("sempre da compra inteira");
    expect(regras).toHaveTextContent("o cartão fica imutável");
    expect(regras).toHaveTextContent("não pode ser editada nem excluída");
    expect(estornar).not.toHaveBeenCalled();

    await usuario.type(screen.getByLabelText("Descrição (opcional)"), " devolvida ");
    await usuario.click(screen.getByRole("button", { name: "Confirmar estorno" }));
    // Leva a versão que o usuário viu (4), a data e a descrição aparada.
    await vi.waitFor(() =>
      expect(estornar).toHaveBeenCalledWith(10, 4, expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/), "devolvida"),
    );

    // pago = 0: estorno integral; o texto não fala em crédito na fatura.
    const resultado = await screen.findByRole("status", { name: "Resultado do estorno" });
    expect(resultado).toHaveTextContent("Estorno integral");
    expect(resultado).toHaveTextContent("o limite voltou por inteiro");
    expect(resultado).not.toHaveTextContent("Estorno com parcelas pagas");
    // Os valores são os da API, sem conta: 70,00 mesmo com total 100,00 e pago 0,00.
    expect(resultado).toHaveTextContent("R$ 70,00");
    expect(resultado).toHaveTextContent("R$ 100,00");
    expect(props.aoEstornar).toHaveBeenCalledTimes(1);
  });

  it("estorno_com_parcelas_pagas", async () => {
    const usuario = userEvent.setup();
    estornar.mockResolvedValueOnce({ tipo: "ok", dados: COM_PAGO });
    painel();
    await usuario.click(screen.getByRole("button", { name: "Confirmar estorno" }));
    const resultado = await screen.findByRole("status", { name: "Resultado do estorno" });
    expect(resultado).toHaveTextContent("Estorno com parcelas pagas");
    expect(resultado).toHaveTextContent("crédito na fatura de dezembro de 2026");
    expect(resultado).toHaveTextContent("R$ 30,00");
    expect(resultado).toHaveTextContent("R$ 999,00");
    expect(resultado).not.toHaveTextContent("Estorno integral");
  });

  it("recusas_do_servidor", async () => {
    const usuario = userEvent.setup();
    const props = painel();
    const confirmar = () => usuario.click(screen.getByRole("button", { name: "Confirmar estorno" }));

    estornar.mockResolvedValueOnce({ tipo: "conflito" });
    await confirmar();
    expect(await screen.findByRole("alert")).toHaveTextContent("já foi estornada");

    estornar.mockResolvedValueOnce({ tipo: "invalido", mensagem: "estorno depois da data de hoje" });
    await confirmar();
    await vi.waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("estorno depois da data de hoje"),
    );

    estornar.mockResolvedValueOnce({ tipo: "erro" });
    await confirmar();
    await vi.waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("confira a lista"),
    );
    // Nada foi reenviado sozinho nem o painel fechou.
    expect(estornar).toHaveBeenCalledTimes(3);
    expect(props.aoEstornar).not.toHaveBeenCalled();

    estornar.mockResolvedValueOnce({ tipo: "desatualizado" });
    await confirmar();
    await vi.waitFor(() => expect(props.aoDesatualizado).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("alert")).toHaveTextContent("mudou desde que você a viu");

    estornar.mockResolvedValueOnce({ tipo: "sessao_expirada" });
    await confirmar();
    await vi.waitFor(() => expect(props.aoSessaoExpirar).toHaveBeenCalledTimes(1));
  });
});

describe("estorno na lista de lançamentos", () => {
  beforeEach(() => {
    apiSessao.recuperarSessao.mockResolvedValue(true);
    saldos.listarSaldos.mockResolvedValue({ tipo: "ok", saldos: CONTAS });
    leitura.listarPessoas.mockResolvedValue({ tipo: "ok", dados: [] });
  });

  it("so_a_compra_a_credito_tem_estornar", async () => {
    const usuario = userEvent.setup();
    const estorno: LancamentoSaida = {
      ...COMPRA,
      transacao_id: 11,
      versao: 1,
      valor: "-100.00",
      estorno_de: 10,
      estorno_credito: "30.00",
      parcelas: null,
    };
    const debito: LancamentoSaida = { ...COMPRA, transacao_id: 12, tipo: "debito", parcelas: null };
    lanc.listarLancamentos.mockResolvedValue({ tipo: "ok", lancamentos: [estorno, COMPRA, debito] });
    estornar.mockResolvedValue({ tipo: "ok", dados: COM_PAGO });
    render(
      <MemoryRouter initialEntries={["/lancamentos"]}>
        <App />
      </MemoryRouter>,
    );

    const lista = await screen.findByRole("list", { name: "Lançamentos" });
    // Um botão só: o estorno e o débito não se estornam.
    const botoes = within(lista).getAllByRole("button", { name: /^Estornar compra/ });
    expect(botoes).toHaveLength(1);
    // A linha do estorno não tem Editar nem Excluir de compra.
    const itens = within(lista).getAllByRole("listitem");
    expect(itens[0]).toHaveTextContent("Estorno de compra");
    expect(within(itens[0]!).queryByRole("button", { name: /^Editar/ })).not.toBeInTheDocument();

    await usuario.click(botoes[0]!);
    await usuario.click(screen.getByRole("button", { name: "Confirmar estorno" }));
    await vi.waitFor(() => expect(estornar).toHaveBeenCalledWith(10, 4, expect.any(String), null));
    expect(await screen.findByRole("status", { name: "Resultado do estorno" })).toHaveTextContent(
      "Estorno com parcelas pagas",
    );
    // A lista é buscada de novo no servidor.
    await vi.waitFor(() => expect(lanc.listarLancamentos).toHaveBeenCalledTimes(2));
  });
});
