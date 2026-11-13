import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import type { AReceberSaida, LancamentoSaida, PessoaSaida } from "../api/gerado";
import * as apiLancamentos from "../api/lancamentos";
import * as apiLeitura from "../api/leitura";
import * as apiPessoas from "../api/pessoas";
import * as sessao from "../api/sessao";
import { Formulario } from "../lancamento/Formulario";
import { CONTAS } from "../lancamento/contasDeTeste";

vi.mock("../api/lancamentos");
vi.mock("../api/leitura");
vi.mock("../api/pessoas");
vi.mock("../api/sessao");
const lanc = vi.mocked(apiLancamentos);
const leitura = vi.mocked(apiLeitura);
const pessoasApi = vi.mocked(apiPessoas);
const apiSessao = vi.mocked(sessao);

const PESSOAS: PessoaSaida[] = [
  { pessoa_id: 7, nome: "Pessoa A", versao: 3 },
  { pessoa_id: 8, nome: "Pessoa B", versao: 1 },
];

const SALVO: LancamentoSaida = {
  transacao_id: 10,
  versao: 1,
  tipo: "credito",
  data: "2026-11-04",
  valor: "100.00",
  conta_id: 4,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: null,
};

afterEach(() => {
  vi.resetAllMocks();
});

function formulario() {
  return render(
    <Formulario contas={CONTAS} pessoas={PESSOAS} aoSalvar={vi.fn()} aoSessaoExpirar={vi.fn()} />,
  );
}

describe("compra de terceiro e repasse no formulário de lançamento", () => {
  it("cem_por_cento", async () => {
    const usuario = userEvent.setup();
    lanc.criarLancamento.mockResolvedValue({ tipo: "ok", lancamento: SALVO, repetido: false });
    formulario();
    const tipo = screen.getByLabelText("Tipo");

    // Despesa comum não leva pessoa.
    expect(screen.queryByLabelText("De quem é a compra")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Quem repassou")).not.toBeInTheDocument();

    // Compra a crédito: ou é toda sua ou é toda de uma pessoa. Não há campo de divisão.
    await usuario.selectOptions(tipo, "credito");
    expect(screen.queryByLabelText(/divis|rateio|percentual|%/i)).not.toBeInTheDocument();
    expect(screen.getAllByLabelText(/De quem é a compra/)).toHaveLength(1);
    await usuario.selectOptions(screen.getByLabelText("Cartão"), "Cartão A");
    await usuario.selectOptions(screen.getByLabelText("Parcelas"), "3x");
    await usuario.selectOptions(screen.getByLabelText("De quem é a compra"), "Pessoa B");
    await usuario.type(screen.getByLabelText("Valor total da compra (R$)"), "100,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    await vi.waitFor(() => expect(lanc.criarLancamento).toHaveBeenCalledTimes(1));
    const compra = lanc.criarLancamento.mock.calls[0]?.[1];
    expect(compra).toMatchObject({
      tipo: "credito",
      conta_id: 4,
      valor: "100.00",
      parcelas: 3,
      pessoa_id: 8,
    });
    // O corpo só tem campos conhecidos: nada de partes, rateio ou divisão.
    const permitidos = [
      "tipo", "data", "valor", "conta_id", "conta_destino_id", "descricao", "parcelas", "pessoa_id",
    ];
    expect(Object.keys(compra ?? {}).filter((k) => !permitidos.includes(k))).toEqual([]);

    // A mesma tela, agora compra própria: pessoa nula.
    await screen.findByRole("status");
    await usuario.selectOptions(screen.getByLabelText("De quem é a compra"), "Minha (compra própria)");
    await usuario.type(screen.getByLabelText("Valor total da compra (R$)"), "40,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    await vi.waitFor(() => expect(lanc.criarLancamento).toHaveBeenCalledTimes(2));
    expect(lanc.criarLancamento.mock.calls[1]?.[1]).toMatchObject({ pessoa_id: null, parcelas: 3 });
  });

  it("repasse_exige_pessoa_e_conta_corrente", async () => {
    const usuario = userEvent.setup();
    lanc.criarLancamento.mockResolvedValue({
      tipo: "ok",
      lancamento: { ...SALVO, tipo: "repasse", conta_id: 1, pessoa_id: 7 },
      repetido: false,
    });
    formulario();
    await usuario.selectOptions(screen.getByLabelText("Tipo"), "repasse");

    // Só conta corrente: nem vale, nem investimento, nem cartão.
    const conta = screen.getByLabelText("Conta corrente que recebeu");
    expect(conta).toHaveTextContent("Banco A");
    for (const fora of ["Vale", "Corretora", "Cartão A"]) {
      expect(conta).not.toHaveTextContent(fora);
    }
    await usuario.type(screen.getByLabelText("Valor (R$)"), "25,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));

    // Sem a pessoa, o formulário não envia e leva o foco ao campo.
    expect(await screen.findByRole("alert")).toHaveTextContent("Escolha quem fez o repasse");
    expect(screen.getByLabelText("Quem repassou")).toHaveFocus();
    expect(lanc.criarLancamento).not.toHaveBeenCalled();

    await usuario.selectOptions(screen.getByLabelText("Quem repassou"), "Pessoa A");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    await vi.waitFor(() => expect(lanc.criarLancamento).toHaveBeenCalledTimes(1));
    const corpo = lanc.criarLancamento.mock.calls[0]?.[1];
    expect(corpo).toMatchObject({ tipo: "repasse", conta_id: 1, valor: "25.00", pessoa_id: 7 });
    expect(corpo).not.toHaveProperty("parcelas");
  });

  it("recusa_do_banco_aparece_literal", async () => {
    const usuario = userEvent.setup();
    lanc.criarLancamento.mockResolvedValue({
      tipo: "invalido",
      mensagem: "repasse só entra em conta corrente",
    });
    formulario();
    await usuario.selectOptions(screen.getByLabelText("Tipo"), "repasse");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "25,00");
    await usuario.selectOptions(screen.getByLabelText("Quem repassou"), "Pessoa A");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("repasse só entra em conta corrente");
  });
});

// ------------------------------------------------------------------ página Pessoas

// Valores incoerentes de propósito: "a receber" não é dívida menos repassado. A tela tem de
// mostrar o que veio.
const A_RECEBER: AReceberSaida[] = [
  {
    pessoa_id: 7,
    nome: "Pessoa A",
    divida: "50.00",
    repassado: "20.00",
    a_receber: "999.00",
    credito_da_pessoa: "3.00",
  },
];

function pagina() {
  return render(
    <MemoryRouter initialEntries={["/pessoas"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("página de pessoas", () => {
  beforeEach(() => {
    apiSessao.recuperarSessao.mockResolvedValue(true);
    leitura.listarPessoas.mockResolvedValue({ tipo: "ok", dados: [PESSOAS[0]!] });
    pessoasApi.listarAReceber.mockResolvedValue({ tipo: "ok", dados: A_RECEBER });
  });

  it("mostra_a_receber_como_a_api_devolveu", async () => {
    pagina();
    const lista = await screen.findByRole("list", { name: "Pessoas" });
    expect(lista).toHaveTextContent("Pessoa A");
    expect(lista).toHaveTextContent("R$ 50,00");
    expect(lista).toHaveTextContent("R$ 20,00");
    expect(lista).toHaveTextContent("R$ 999,00");
    expect(lista).toHaveTextContent("R$ 3,00");
  });

  it("estados_vazio_erro_e_sessao", async () => {
    const usuario = userEvent.setup();
    leitura.listarPessoas.mockResolvedValueOnce({ tipo: "erro" });
    pagina();
    expect(await screen.findByText("Não foi possível carregar as pessoas.")).toBeInTheDocument();
    leitura.listarPessoas.mockResolvedValueOnce({ tipo: "ok", dados: [] });
    pessoasApi.listarAReceber.mockResolvedValueOnce({ tipo: "ok", dados: [] });
    await usuario.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Nenhuma pessoa ainda")).toBeInTheDocument();
  });

  it("sessao_vencida_volta_ao_login", async () => {
    leitura.listarPessoas.mockResolvedValue({ tipo: "sessao_expirada" });
    pagina();
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });

  it("cria_pessoa_e_explica_nome_repetido", async () => {
    const usuario = userEvent.setup();
    pessoasApi.criarPessoa
      .mockResolvedValueOnce({ tipo: "conflito" })
      .mockResolvedValueOnce({ tipo: "ok", dados: { pessoa_id: 9, nome: "Pessoa C", versao: 1 } });
    pagina();
    await screen.findByRole("list", { name: "Pessoas" });
    const nome = screen.getByLabelText("Nome");

    await usuario.type(nome, "Pessoa A");
    await usuario.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Já existe uma pessoa com esse nome");
    // O erro está ligado ao campo e o foco volta para ele.
    expect(nome).toHaveAttribute("aria-invalid", "true");
    expect(nome).toHaveAttribute("aria-describedby", alerta.id);
    expect(nome).toHaveFocus();

    await usuario.clear(nome);
    await usuario.type(nome, "Pessoa C");
    await usuario.click(screen.getByRole("button", { name: "Cadastrar pessoa" }));
    expect(await screen.findByText("Pessoa cadastrada.")).toBeInTheDocument();
    expect(pessoasApi.criarPessoa).toHaveBeenLastCalledWith("Pessoa C");
    // A lista é buscada de novo no servidor.
    await vi.waitFor(() => expect(leitura.listarPessoas).toHaveBeenCalledTimes(2));
  });

  it("renomeia_com_a_versao_que_o_usuario_viu", async () => {
    const usuario = userEvent.setup();
    pessoasApi.renomearPessoa.mockResolvedValue({ tipo: "desatualizado" });
    pagina();
    await screen.findByRole("list", { name: "Pessoas" });
    await usuario.click(screen.getByRole("button", { name: "Renomear Pessoa A" }));

    // Outra aba renomeou (versão 4) e a lista foi atualizada com a edição aberta.
    leitura.listarPessoas.mockResolvedValue({
      tipo: "ok",
      dados: [{ pessoa_id: 7, nome: "Pessoa A2", versao: 4 }],
    });
    const form = screen.getByRole("form", { name: "Renomear Pessoa A" });
    const campo = within(form).getByLabelText("Novo nome");
    await usuario.clear(campo);
    await usuario.type(campo, "Pessoa X");
    await usuario.click(within(form).getByRole("button", { name: "Salvar nome" }));
    // Vai a versão lida ao abrir (3), e o 409 é explicado sem sobrescrever.
    await vi.waitFor(() => expect(pessoasApi.renomearPessoa).toHaveBeenCalledWith(7, 3, "Pessoa X"));
    expect(await screen.findByRole("alert")).toHaveTextContent("mudou desde que você a viu");
  });

  it("exclui_com_confirmacao_e_mostra_a_recusa_do_banco", async () => {
    const usuario = userEvent.setup();
    pessoasApi.excluirPessoa
      .mockResolvedValueOnce({ tipo: "invalido", mensagem: "pessoa com compra vigente" })
      .mockResolvedValueOnce({ tipo: "ok", dados: null });
    pagina();
    await screen.findByRole("list", { name: "Pessoas" });
    await usuario.click(screen.getByRole("button", { name: "Excluir Pessoa A" }));
    // Nada foi apagado ainda; o foco está em Cancelar.
    expect(pessoasApi.excluirPessoa).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();

    await usuario.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("pessoa com compra vigente");
    expect(pessoasApi.excluirPessoa).toHaveBeenLastCalledWith(7, 3);

    await usuario.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    await vi.waitFor(() => expect(pessoasApi.excluirPessoa).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(leitura.listarPessoas.mock.calls.length).toBeGreaterThan(1));
  });
});
