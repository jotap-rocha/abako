import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as apiCartoes from "../api/cartoes";
import type { ContaSaida, LinhaSaida } from "../api/gerado";
import * as apiLeitura from "../api/leitura";
import * as sessao from "../api/sessao";
import * as vigencias from "../api/vigencias";
import { CARTAO, CORRENTE, FATURA, LIMITE, PESSOAS } from "../leitura/dadosDeTeste";

vi.mock("../api/cartoes");
vi.mock("../api/leitura");
vi.mock("../api/sessao");
vi.mock("../api/vigencias");
const cartoes = vi.mocked(apiCartoes);
const leitura = vi.mocked(apiLeitura);
const apiSessao = vi.mocked(sessao);
const vig = vi.mocked(vigencias);

const LINHA_NOVA: LinhaSaida = { linha_id: 11, nome: "Linha verde", limite: "5000.00", versao: 1 };
const CARTAO_NOVO: ContaSaida = {
  conta_id: 21,
  nome: "Cartão verde",
  tipo: "divida",
  conta_beneficio: false,
  conta_mae_id: null,
  linha_credito_id: 11,
  versao: 1,
};

function pagina() {
  return render(
    <MemoryRouter initialEntries={["/cartoes"]}>
      <App />
    </MemoryRouter>,
  );
}

async function formulario() {
  return screen.findByRole("form", { name: "Novo cartão" });
}

async function preencherNova(usuario: ReturnType<typeof userEvent.setup>, dia = "10") {
  const form = await formulario();
  await usuario.type(within(form).getByLabelText("Nome da linha"), "Linha verde");
  await usuario.type(within(form).getByLabelText("Limite (R$)"), "5.000,00");
  await usuario.type(within(form).getByLabelText("Nome do cartão"), "Cartão verde");
  if (dia !== "") await usuario.type(within(form).getByLabelText("Dia de fechamento (opcional)"), dia);
  return form;
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  leitura.listarContas.mockResolvedValue({ tipo: "ok", dados: [CORRENTE, CARTAO] });
  leitura.listarPessoas.mockResolvedValue({ tipo: "ok", dados: PESSOAS });
  leitura.obterFatura.mockResolvedValue({ tipo: "ok", dados: FATURA });
  leitura.obterLimite.mockResolvedValue({ tipo: "ok", dados: LIMITE });
  vig.listarFechamentos.mockResolvedValue({ tipo: "ok", dados: [] });
  vig.listarVencimentos.mockResolvedValue({ tipo: "ok", dados: [] });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("novo cartão", () => {
  it("cria_linha_cartao_e_fechamento_na_ordem_certa", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValue({ tipo: "ok", dados: LINHA_NOVA });
    cartoes.criarCartao.mockResolvedValue({ tipo: "ok", dados: CARTAO_NOVO });
    vig.gravarFechamento.mockResolvedValue({
      tipo: "ok",
      dados: { dia: 10, vigente_desde: "2026-11-01" },
    });
    pagina();
    const form = await preencherNova(usuario);
    // "Vale a partir de" vem preenchido com o 1º dia do mês atual e é editável.
    const desde = within(form).getByLabelText("Vale a partir de") as HTMLInputElement;
    expect(desde.value).toMatch(/^\d{4}-\d{2}-01$/);
    expect(form).toHaveTextContent("Compras anteriores a esta data são recusadas.");
    fireEvent.change(desde, { target: { value: "2026-11-05" } });
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));

    expect(await within(form).findByRole("status")).toHaveTextContent("Cartão \"Cartão verde\" criado");
    // Limite sai como texto no formato do servidor (nada de number); linha_credito_id vai junto.
    expect(cartoes.criarLinha).toHaveBeenCalledWith("Linha verde", "5000.00");
    expect(cartoes.criarCartao).toHaveBeenCalledWith("Cartão verde", 11);
    expect(vig.gravarFechamento).toHaveBeenCalledWith(21, 10, "2026-11-05");
    const ordem = [
      cartoes.criarLinha.mock.invocationCallOrder[0],
      cartoes.criarCartao.mock.invocationCallOrder[0],
      vig.gravarFechamento.mock.invocationCallOrder[0],
    ];
    expect(ordem).toEqual([...ordem].sort((a, b) => (a ?? 0) - (b ?? 0)));
    // O formulário limpa e a lista de cartões é buscada de novo.
    expect(within(form).getByLabelText("Nome do cartão")).toHaveValue("");
    await waitFor(() => expect(leitura.listarContas).toHaveBeenCalledTimes(2));
  });

  it("sem_fechamento_nao_chama_o_fechamento_e_avisa", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValue({ tipo: "ok", dados: LINHA_NOVA });
    cartoes.criarCartao.mockResolvedValue({ tipo: "ok", dados: CARTAO_NOVO });
    pagina();
    const form = await preencherNova(usuario, "");
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    expect(await within(form).findByRole("status")).toHaveTextContent(
      "Sem fechamento, a compra no crédito será recusada.",
    );
    expect(vig.gravarFechamento).not.toHaveBeenCalled();
  });

  it("usa_linha_existente_sem_criar_outra_e_mostra_o_limite_como_veio", async () => {
    const usuario = userEvent.setup();
    // Limite de propósito sem relação com nada: a tela só formata o texto.
    cartoes.listarLinhas.mockResolvedValue({
      tipo: "ok",
      dados: [{ linha_id: 3, nome: "Linha azul", limite: "9.99", versao: 4 }],
    });
    cartoes.criarCartao.mockResolvedValue({ tipo: "ok", dados: CARTAO_NOVO });
    pagina();
    const form = await formulario();
    expect(screen.getByText(/compartilham o limite/)).toBeInTheDocument();
    await usuario.click(within(form).getByLabelText("Usar uma linha que já existe"));
    const escolha = await within(form).findByLabelText("Linha de crédito do cartão");
    expect(within(escolha).getByRole("option", { name: "Linha azul (limite R$ 9,99)" })).toBeInTheDocument();
    await usuario.selectOptions(escolha, "3");
    await usuario.type(within(form).getByLabelText("Nome do cartão"), "Cartão extra");
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    await waitFor(() => expect(cartoes.criarCartao).toHaveBeenCalledWith("Cartão extra", 3));
    expect(cartoes.criarLinha).not.toHaveBeenCalled();
    expect(vig.gravarFechamento).not.toHaveBeenCalled();
  });

  it("linha_existente_vazia_e_erro_ao_carregar_sao_tratados", async () => {
    const usuario = userEvent.setup();
    cartoes.listarLinhas.mockResolvedValueOnce({ tipo: "erro" });
    pagina();
    const form = await formulario();
    await usuario.click(within(form).getByLabelText("Usar uma linha que já existe"));
    expect(await within(form).findByText("Não foi possível carregar as linhas de crédito.")).toBeInTheDocument();
    cartoes.listarLinhas.mockResolvedValueOnce({ tipo: "ok", dados: [] });
    await usuario.click(within(form).getByRole("button", { name: "Tentar de novo" }));
    expect(await within(form).findByText(/Nenhuma linha cadastrada/)).toBeInTheDocument();
  });

  it("nome_repetido_409_e_mensagem_literal_422_aparecem_nos_campos", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValueOnce({ tipo: "conflito" });
    pagina();
    const form = await preencherNova(usuario);
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    const alerta = await within(form).findByRole("alert");
    expect(alerta).toHaveTextContent("Já existe uma linha de crédito com este nome.");
    const campo = within(form).getByLabelText("Nome da linha");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo.getAttribute("aria-describedby")).toBe(alerta.id);
    expect(campo).toHaveFocus();
    expect(cartoes.criarCartao).not.toHaveBeenCalled();

    cartoes.criarLinha.mockResolvedValueOnce({ tipo: "invalido", mensagem: "limite acima do permitido" });
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    await waitFor(() => expect(within(form).getByRole("alert")).toHaveTextContent("limite acima do permitido"));
  });

  it("validacao_local_foca_o_primeiro_campo_com_erro_e_nao_envia", async () => {
    const usuario = userEvent.setup();
    pagina();
    const form = await formulario();
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    expect(within(form).getByLabelText("Nome da linha")).toHaveFocus();
    await usuario.type(within(form).getByLabelText("Nome da linha"), "L");
    await usuario.type(within(form).getByLabelText("Limite (R$)"), "abc");
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    expect(within(form).getByLabelText("Limite (R$)")).toHaveFocus();
    expect(within(form).getByRole("alert")).toHaveTextContent("valor positivo");
    expect(cartoes.criarLinha).not.toHaveBeenCalled();
  });

  it("cartao_criado_e_fechamento_falhou_diz_que_falta_o_fechamento_e_leva_ao_config", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValue({ tipo: "ok", dados: LINHA_NOVA });
    cartoes.criarCartao.mockResolvedValue({ tipo: "ok", dados: CARTAO_NOVO });
    vig.gravarFechamento.mockResolvedValueOnce({
      tipo: "invalido",
      mensagem: "dia inválido para o banco",
    });
    vig.gravarFechamento.mockResolvedValue({
      tipo: "ok",
      dados: { dia: 12, vigente_desde: "2026-11-01" },
    });
    leitura.listarContas
      .mockResolvedValueOnce({ tipo: "ok", dados: [CORRENTE, CARTAO] })
      .mockResolvedValue({ tipo: "ok", dados: [CORRENTE, CARTAO, CARTAO_NOVO] });
    pagina();
    const form = await preencherNova(usuario);
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    const alerta = await within(form).findByRole("alert");
    expect(alerta).toHaveTextContent('Cartão "Cartão verde" criado, falta o fechamento');
    expect(alerta).toHaveTextContent("dia inválido para o banco");
    await usuario.click(within(alerta).getByRole("button", { name: "Cadastrar o fechamento" }));
    // O cartão novo passa a ser o escolhido: a fatura e o ConfigCartao são os dele.
    expect(await screen.findByText("Fatura de Cartão verde")).toBeInTheDocument();
    // O foco vai para o bloco de fechamento e vencimento (não só a rolagem).
    const bloco = screen.getByRole("group", { name: "Fechamento e vencimento do cartão" });
    await waitFor(() => expect(bloco).toHaveFocus());
    // Ao cadastrar o fechamento por lá, o aviso "falta o fechamento" some.
    const formConfig = within(bloco).getByRole("form", { name: "Novo dia de fechamento" });
    await usuario.type(within(formConfig).getByLabelText("Dia do mês"), "12");
    await usuario.click(within(formConfig).getByRole("button", { name: "Salvar dia de fechamento" }));
    await waitFor(() => expect(vig.gravarFechamento).toHaveBeenLastCalledWith(21, 12, expect.any(String)));
    await waitFor(() => expect(screen.queryByText(/falta o fechamento/)).not.toBeInTheDocument());
  });

  it("usar_outra_linha_destrava_o_formulario_depois_de_linha_criada_e_cartao_falho", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValue({ tipo: "ok", dados: LINHA_NOVA });
    cartoes.criarCartao.mockResolvedValue({ tipo: "erro" });
    cartoes.listarLinhas.mockResolvedValue({
      tipo: "ok",
      dados: [{ linha_id: 3, nome: "Linha azul", limite: "9.99", versao: 4 }],
    });
    pagina();
    const form = await preencherNova(usuario, "");
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    expect(await within(form).findByRole("status")).toHaveTextContent("já foi criada e será reaproveitada");
    expect(within(form).getByLabelText("Nome da linha")).toBeDisabled();
    await usuario.click(within(form).getByRole("button", { name: "Usar outra linha" }));
    expect(within(form).getByLabelText("Nome da linha")).toBeEnabled();
    expect(within(form).getByLabelText("Limite (R$)")).toBeEnabled();
    expect(within(form).queryByRole("status")).not.toBeInTheDocument();
    // Já dá para escolher uma linha existente; a linha criada não é mais reaproveitada.
    await usuario.click(within(form).getByLabelText("Usar uma linha que já existe"));
    await usuario.selectOptions(await within(form).findByLabelText("Linha de crédito do cartão"), "3");
    cartoes.criarCartao.mockResolvedValue({ tipo: "ok", dados: CARTAO_NOVO });
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    await waitFor(() => expect(cartoes.criarCartao).toHaveBeenLastCalledWith("Cartão verde", 3));
    expect(cartoes.criarLinha).toHaveBeenCalledTimes(1);
  });

  it("linha_existente_com_lista_vazia_bloqueia_o_envio_sem_campo_fantasma", async () => {
    const usuario = userEvent.setup();
    cartoes.listarLinhas.mockResolvedValue({ tipo: "ok", dados: [] });
    pagina();
    const form = await formulario();
    await usuario.click(within(form).getByLabelText("Usar uma linha que já existe"));
    expect(
      await within(form).findByText("Nenhuma linha cadastrada ainda. Crie uma nova linha."),
    ).toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "Criar cartão" })).toBeDisabled();
    // Nenhum campo aponta para um erro que não existe.
    expect(form.querySelector("[aria-describedby]")).toBeNull();
    expect(form.querySelector("[aria-invalid]")).toBeNull();
    fireEvent.submit(form);
    expect(await within(form).findByRole("alert")).toHaveTextContent("Crie uma nova linha");
    expect(form.querySelector("[aria-describedby]")).toBeNull();
    expect(cartoes.criarCartao).not.toHaveBeenCalled();
  });

  it("linha_criada_e_cartao_falhou_a_nova_tentativa_reaproveita_a_linha", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValue({ tipo: "ok", dados: LINHA_NOVA });
    cartoes.criarCartao.mockResolvedValueOnce({ tipo: "erro" });
    cartoes.criarCartao.mockResolvedValueOnce({ tipo: "ok", dados: CARTAO_NOVO });
    vig.gravarFechamento.mockResolvedValue({
      tipo: "ok",
      dados: { dia: 10, vigente_desde: "2026-11-01" },
    });
    pagina();
    const form = await preencherNova(usuario);
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("será reaproveitada");
    expect(within(form).getByLabelText("Nome da linha")).toBeDisabled();
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    await waitFor(() => expect(cartoes.criarCartao).toHaveBeenCalledTimes(2));
    expect(cartoes.criarLinha).toHaveBeenCalledTimes(1);
    expect(cartoes.criarCartao).toHaveBeenNthCalledWith(1, "Cartão verde", 11);
    expect(cartoes.criarCartao).toHaveBeenNthCalledWith(2, "Cartão verde", 11);
    await waitFor(() => expect(vig.gravarFechamento).toHaveBeenCalledWith(21, 10, expect.any(String)));
  });

  it("duplo_clique_envia_uma_vez_so", async () => {
    const usuario = userEvent.setup();
    let liberar: (v: Awaited<ReturnType<typeof apiCartoes.criarLinha>>) => void = () => undefined;
    cartoes.criarLinha.mockReturnValue(new Promise((r) => (liberar = r)));
    pagina();
    const form = await preencherNova(usuario, "");
    // Dois envios seguidos antes de a resposta chegar (o segundo cai na guarda, não só no botão).
    fireEvent.submit(form);
    fireEvent.submit(form);
    expect(cartoes.criarLinha).toHaveBeenCalledTimes(1);
    expect(within(form).getByRole("button", { name: "Criando…" })).toBeDisabled();
    cartoes.criarCartao.mockResolvedValue({ tipo: "ok", dados: CARTAO_NOVO });
    liberar({ tipo: "ok", dados: LINHA_NOVA });
    await waitFor(() => expect(cartoes.criarCartao).toHaveBeenCalledTimes(1));
  });

  it("sessao_vencida_ao_criar_volta_ao_login", async () => {
    const usuario = userEvent.setup();
    cartoes.criarLinha.mockResolvedValue({ tipo: "sessao_expirada" });
    pagina();
    const form = await preencherNova(usuario);
    await usuario.click(within(form).getByRole("button", { name: "Criar cartão" }));
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});

describe("tela de cartões", () => {
  it("estado_vazio_convida_ao_formulario_e_avisa_da_divida_inicial", async () => {
    leitura.listarContas.mockResolvedValue({ tipo: "ok", dados: [CORRENTE] });
    pagina();
    expect(await screen.findByText("Nenhum cartão ainda")).toBeInTheDocument();
    expect(screen.queryByText(/conta do tipo dívida em Contas/)).not.toBeInTheDocument();
    const form = await formulario();
    expect(form).toBeInTheDocument();
    expect(screen.getByText(/começamos do zero/)).toHaveTextContent("lançadas uma a uma");
  });

  it("cartao_sem_fechamento_tem_aviso_persistente_na_fatura", async () => {
    leitura.obterFatura.mockResolvedValue({
      tipo: "ok",
      dados: { ...FATURA, fechamento: null, situacao: null },
    });
    pagina();
    expect(
      await screen.findByText("Sem fechamento, a compra no crédito será recusada."),
    ).toBeInTheDocument();
  });

  it("formulario_de_conta_continua_sem_o_tipo_cartao", async () => {
    const { TIPOS_CONTA } = await import("../saldos/tiposConta");
    expect(JSON.stringify(TIPOS_CONTA)).not.toContain("divida");
  });
});

describe("editar a linha de crédito", () => {
  const LINHA_3: LinhaSaida = { linha_id: 3, nome: "Linha azul", limite: "5000.00", versao: 4 };

  it("envia_a_versao_lida_o_limite_como_texto_e_avisa_que_vale_para_tudo", async () => {
    const usuario = userEvent.setup();
    cartoes.listarLinhas.mockResolvedValue({ tipo: "ok", dados: [LINHA_3] });
    cartoes.editarLinha.mockResolvedValue({
      tipo: "ok",
      dados: { ...LINHA_3, limite: "7000.00", versao: 5 },
    });
    pagina();
    // Texto fixo, sempre visível.
    expect(await screen.findByText(/vale para tudo, inclusive o passado/)).toBeInTheDocument();
    await usuario.click(await screen.findByRole("button", { name: "Editar nome e limite da linha" }));
    const form = await screen.findByRole("form", { name: "Editar linha de crédito" });
    expect(within(form).getByLabelText("Limite (R$)")).toHaveValue("5000.00");
    await usuario.clear(within(form).getByLabelText("Limite (R$)"));
    await usuario.type(within(form).getByLabelText("Limite (R$)"), "7.000,00");
    await usuario.click(within(form).getByRole("button", { name: "Salvar linha" }));
    await waitFor(() => expect(cartoes.editarLinha).toHaveBeenCalledWith(3, 4, "Linha azul", "7000.00"));
    expect(await screen.findByText('Linha "Linha azul" salva.')).toBeInTheDocument();
    // A fatura e o limite são buscados de novo.
    await waitFor(() => expect(leitura.obterLimite.mock.calls.length).toBeGreaterThan(1));
  });

  it("versao_velha_409_mostra_mudou_desde_a_leitura_e_recarrega", async () => {
    const usuario = userEvent.setup();
    cartoes.listarLinhas.mockResolvedValue({ tipo: "ok", dados: [LINHA_3] });
    cartoes.editarLinha.mockResolvedValue({ tipo: "desatualizado" });
    pagina();
    await usuario.click(await screen.findByRole("button", { name: "Editar nome e limite da linha" }));
    const form = await screen.findByRole("form", { name: "Editar linha de crédito" });
    await usuario.click(within(form).getByRole("button", { name: "Salvar linha" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("mudou desde a leitura");
    await waitFor(() => expect(cartoes.listarLinhas).toHaveBeenCalledTimes(2));
  });

  it("nome_repetido_409_aparece_no_campo_e_o_aviso_some_ao_digitar", async () => {
    const usuario = userEvent.setup();
    cartoes.listarLinhas.mockResolvedValue({ tipo: "ok", dados: [LINHA_3] });
    cartoes.editarLinha.mockResolvedValueOnce({ tipo: "conflito" });
    cartoes.editarLinha.mockResolvedValueOnce({ tipo: "desatualizado" });
    pagina();
    await usuario.click(await screen.findByRole("button", { name: "Editar nome e limite da linha" }));
    const form = await screen.findByRole("form", { name: "Editar linha de crédito" });
    await usuario.click(within(form).getByRole("button", { name: "Salvar linha" }));
    const alerta = await within(form).findByRole("alert");
    expect(alerta).toHaveTextContent("Já existe uma linha de crédito com este nome.");
    const campo = within(form).getByLabelText("Nome da linha");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo.getAttribute("aria-describedby")).toBe(alerta.id);
    expect(campo).toHaveFocus();

    // 409 de versão: o aviso aparece depois da recarga e some quando o usuário volta a digitar.
    await usuario.click(within(form).getByRole("button", { name: "Salvar linha" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("mudou desde a leitura");
    const novo = await screen.findByRole("form", { name: "Editar linha de crédito" });
    await usuario.type(within(novo).getByLabelText("Nome da linha"), "x");
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("nao_oferece_trocar_a_linha_nem_excluir", async () => {
    pagina();
    await screen.findByText("Fatura de Cartão azul");
    expect(screen.queryByRole("button", { name: /excluir|trocar/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/trocar a linha/i)).not.toBeInTheDocument();
  });
});
