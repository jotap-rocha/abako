import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as leitura from "../api/leitura";
import * as sessao from "../api/sessao";
import * as vale from "../api/vale";
import { deslocarMes, mesAtual } from "../datas";
import { ALERTAS, CORRENTE, GASTO, RECEITA, R2, RESERVA } from "../leitura/dadosDeTeste";
import {
  ALERTA_R5,
  BENEFICIOS,
  CONTA_VA,
  CONTA_VR,
  DECISOES,
  SITUACAO_OK,
  SITUACAO_SEM_CONTA,
  SITUACAO_SEM_CREDITO,
} from "./dadosDeTeste";

// Só a fronteira com o servidor é simulada; o App e as telas rodam de verdade.
vi.mock("../api/sessao");
vi.mock("../api/leitura");
vi.mock("../api/vale");
const apiSessao = vi.mocked(sessao);
const apiLeitura = vi.mocked(leitura);
const apiVale = vi.mocked(vale);

function renderizar(rota: string) {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiLeitura.listarContas.mockResolvedValue({
    tipo: "ok",
    dados: [CORRENTE, CONTA_VR, CONTA_VA],
  });
  apiVale.obterSituacaoVale.mockResolvedValue({ tipo: "ok", dados: SITUACAO_OK });
  apiVale.obterBeneficios.mockResolvedValue({ tipo: "ok", dados: BENEFICIOS });
  apiVale.listarDecisoes.mockResolvedValue({ tipo: "ok", dados: DECISOES });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("página do vale", () => {
  it("mostra_o_que_a_api_devolveu_sem_recalcular", async () => {
    // Resta, sobra, receita total e saldo são incoerentes de propósito.
    renderizar("/vale");
    const trabalho = await screen.findByRole("region", { name: "Bolso Trabalho" });
    expect(within(trabalho).getByText("R$ 333,33")).toBeInTheDocument();
    expect(within(trabalho).getByText("R$ 44,44")).toBeInTheDocument();
    expect(within(trabalho).getByText("R$ 555,55")).toBeInTheDocument();
    expect(within(trabalho).getByText("R$ 666,66")).toBeInTheDocument();
    // Resta negativo destacado como estouro, no bolso certo.
    expect(within(trabalho).getByText("-R$ 777,77")).toBeInTheDocument();
    expect(within(trabalho).getByText("estourado")).toBeInTheDocument();
    const pessoal = screen.getByRole("region", { name: "Bolso Pessoal" });
    expect(within(pessoal).getByText("R$ 432,10")).toBeInTheDocument();
    expect(within(pessoal).queryByText("estourado")).not.toBeInTheDocument();
    // Sobra, crédito, base, saldo e receitas exatamente como vieram.
    expect(screen.getByText("R$ 111,00")).toBeInTheDocument();
    expect(screen.getByText("R$ 1.111,11")).toBeInTheDocument();
    expect(screen.getByText("R$ 222,22")).toBeInTheDocument();
    expect(screen.getByText("R$ 2.468,13")).toBeInTheDocument();
    expect(screen.getByText("R$ 3.000,01")).toBeInTheDocument();
    expect(screen.getByText("R$ 1.500,02")).toBeInTheDocument();
    expect(screen.getByText("R$ 9.999,99")).toBeInTheDocument();
    expect(screen.getByText(/sem compensação/)).toBeInTheDocument();
  });

  it("sem_conta_leva_a_marcar_o_vr", async () => {
    apiVale.obterSituacaoVale.mockResolvedValue({ tipo: "ok", dados: SITUACAO_SEM_CONTA });
    apiVale.gravarParametroVale.mockResolvedValue({
      tipo: "invalido",
      mensagem: "mensagem literal do banco",
    });
    const usuario = userEvent.setup();
    renderizar("/vale");
    expect(await screen.findByText("Nenhuma conta marcada como VR")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Bolso Trabalho" })).not.toBeInTheDocument();
    const form = screen.getByRole("form", { name: "Marcar a conta do VR" });

    // Sem escolher a conta, nada é enviado.
    await usuario.click(within(form).getByRole("button", { name: "Salvar marcação do VR" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Escolha a conta");
    expect(apiVale.gravarParametroVale).not.toHaveBeenCalled();

    await usuario.selectOptions(within(form).getByLabelText("Conta do VR"), "Vale A");
    await usuario.click(within(form).getByRole("button", { name: "Salvar marcação do VR" }));
    // A mensagem do banco aparece como veio.
    expect(await screen.findByText("mensagem literal do banco")).toBeInTheDocument();
    expect(apiVale.gravarParametroVale).toHaveBeenCalledWith({
      contaId: 31,
      baseTrabalho: "200.00",
      destinoPadrao: "nenhum",
      vigenteDesde: `${mesAtual()}-01`,
    });
  });

  it("marcacao_recusada_por_despesas_sem_bolso_mostra_a_mensagem_e_a_orientacao", async () => {
    apiVale.obterSituacaoVale.mockResolvedValue({ tipo: "ok", dados: SITUACAO_SEM_CONTA });
    apiVale.gravarParametroVale.mockResolvedValue({
      tipo: "invalido",
      mensagem: "edite as despesas antigas da conta informando o bolso antes de marcá-la como VR",
    });
    const usuario = userEvent.setup();
    renderizar("/vale");
    const form = await screen.findByRole("form", { name: "Marcar a conta do VR" });
    await usuario.selectOptions(within(form).getByLabelText("Conta do VR"), "Vale A");
    await usuario.click(within(form).getByRole("button", { name: "Salvar marcação do VR" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "edite as despesas antigas da conta informando o bolso antes de marcá-la como VR",
    );
    expect(screen.getByText(/edite cada despesa informando o bolso e tente marcar de novo/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir os lançamentos" })).toHaveAttribute(
      "href",
      "/lancamentos",
    );
  });

  it("sem_credito_explica_e_nao_alerta", async () => {
    apiVale.obterSituacaoVale.mockResolvedValue({ tipo: "ok", dados: SITUACAO_SEM_CREDITO });
    renderizar("/vale");
    expect(await screen.findByText(/não teve crédito no VR/)).toBeInTheDocument();
    expect(screen.getByText(/não há alerta/)).toBeInTheDocument();
  });

  it("estados_carregando_erro_e_sessao_vencida", async () => {
    apiVale.obterSituacaoVale.mockReturnValue(new Promise(() => undefined));
    const a = renderizar("/vale");
    expect(await screen.findByText("Carregando o vale…")).toBeInTheDocument();
    a.unmount();

    apiVale.obterSituacaoVale.mockResolvedValueOnce({ tipo: "erro" });
    const b = renderizar("/vale");
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o vale");
    apiVale.obterSituacaoVale.mockResolvedValue({ tipo: "ok", dados: SITUACAO_OK });
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("region", { name: "Bolso Pessoal" })).toBeInTheDocument();
    b.unmount();

    apiVale.obterSituacaoVale.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar("/vale");
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });

  it("navega_para_meses_anteriores_e_nunca_para_o_futuro", async () => {
    const usuario = userEvent.setup();
    renderizar("/vale");
    await screen.findByRole("region", { name: "Bolso Pessoal" });
    expect(screen.getByRole("button", { name: "Próximo mês" })).toBeDisabled();
    await usuario.click(screen.getByRole("button", { name: "Mês anterior" }));
    await vi.waitFor(() =>
      expect(apiVale.obterSituacaoVale).toHaveBeenLastCalledWith(deslocarMes(mesAtual(), -1)),
    );
    expect(apiVale.obterBeneficios).toHaveBeenLastCalledWith(deslocarMes(mesAtual(), -1));
  });
});

describe("decisão da sobra", () => {
  it("desabilitada_com_mes_encerrado_falso", async () => {
    renderizar("/vale");
    const form = await screen.findByRole("form", { name: "Decisão da sobra" });
    expect(within(form).getByLabelText("Destino da sobra")).toBeDisabled();
    expect(within(form).getByRole("button", { name: "Salvar decisão" })).toBeDisabled();
    expect(screen.getByText(/depois que o mês termina/)).toBeInTheDocument();
    expect(screen.getAllByText(/não move saldo/).length).toBeGreaterThan(0);
  });

  it("habilitada_pre_selecionada_pelo_destino_padrao_e_grava", async () => {
    apiVale.obterSituacaoVale.mockResolvedValue({
      tipo: "ok",
      dados: { ...SITUACAO_OK, mes_encerrado: true },
    });
    apiVale.gravarDecisao.mockResolvedValue({
      tipo: "ok",
      dados: { mes: "2026-11", destino: "trabalho", versao: 3 },
    });
    const usuario = userEvent.setup();
    renderizar("/vale");
    const form = await screen.findByRole("form", { name: "Decisão da sobra" });
    const seletor = within(form).getByLabelText("Destino da sobra");
    expect(seletor).toBeEnabled();
    // Sem decisão gravada, vem o destino padrão do parâmetro.
    expect(seletor).toHaveValue("pessoal");
    await usuario.selectOptions(seletor, "trabalho");
    await usuario.click(within(form).getByRole("button", { name: "Salvar decisão" }));
    expect(await screen.findByText(/Decisão salva: .*trabalho.* \(versão 3\)/)).toBeInTheDocument();
    expect(apiVale.gravarDecisao).toHaveBeenCalledWith("2026-11", "trabalho");
  });

  it("mostra_historico_de_versoes_e_trata_422", async () => {
    apiVale.obterSituacaoVale.mockResolvedValue({
      tipo: "ok",
      dados: { ...SITUACAO_OK, mes_encerrado: true, decisao_destino: "nenhum", decisao_versao: 2 },
    });
    apiVale.gravarDecisao.mockResolvedValue({ tipo: "invalido", mensagem: "texto do banco" });
    const usuario = userEvent.setup();
    renderizar("/vale");
    const historico = await screen.findByRole("list", { name: "Histórico de decisões" });
    expect(historico).toHaveTextContent("Versão 1");
    expect(historico).toHaveTextContent("Versão 2");
    expect(historico).toHaveTextContent("(vigente)");
    expect(screen.getByText(/Decisão vigente:.*\(versão 2\)/)).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Salvar decisão" }));
    expect(await screen.findByText("texto do banco")).toBeInTheDocument();
  });

  it("conflito_409_e_explicado", async () => {
    apiVale.obterSituacaoVale.mockResolvedValue({
      tipo: "ok",
      dados: { ...SITUACAO_OK, mes_encerrado: true },
    });
    apiVale.gravarDecisao.mockResolvedValue({ tipo: "conflito" });
    renderizar("/vale");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Salvar decisão" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/conflito/);
  });
});

describe("benefícios", () => {
  it("va_sem_bolsos_e_vr_com_a_marca", async () => {
    renderizar("/vale");
    const lista = await screen.findByRole("list", { name: "Contas de benefício" });
    const [vr, va] = within(lista).getAllByRole("listitem");
    expect(vr).toHaveTextContent("Vale A");
    expect(vr).toHaveTextContent("vale-refeição");
    expect(vr).toHaveTextContent("R$ 4.444,44");
    expect(va).toHaveTextContent("Vale B");
    expect(va).toHaveTextContent("sem bolsos");
    expect(va).not.toHaveTextContent("vale-refeição");
    expect(va).toHaveTextContent("R$ 500,00");
    expect(va).toHaveTextContent("R$ 50,00");
    expect(va).toHaveTextContent("R$ 5.555,55");
    // Só há bolsos para o VR.
    expect(screen.getAllByRole("region", { name: /^Bolso / })).toHaveLength(2);
  });
});

describe("alerta R5 e tela principal", () => {
  it("r5_aparece_forte_na_tela_de_alertas_sem_botao_de_dispensar", async () => {
    apiLeitura.obterAlertas.mockResolvedValue({
      tipo: "ok",
      dados: { data_referencia: "2026-11-13", itens: [ALERTA_R5] },
    });
    renderizar("/alertas");
    const lista = await screen.findByRole("list", { name: "Alertas" });
    expect(lista).toHaveTextContent("O bolso de trabalho do vale estourou.");
    expect(lista).toHaveTextContent("R5");
    expect(lista).toHaveTextContent("severidade Alta");
    expect(lista).toHaveTextContent("Bolso trabalho");
    expect(lista).toHaveTextContent("R$ 100,00");
    expect(lista).toHaveTextContent("R$ 130,00");
    expect(lista).toHaveTextContent("-R$ 30,00");
    expect(within(lista).getByRole("listitem")).toHaveClass("alerta-forte");
    expect(within(lista).queryByRole("button", { name: /dispensar|ignorar|fechar/i })).toBeNull();
    expect(within(lista).getByRole("link", { name: "Ver o vale" })).toHaveAttribute("href", "/vale");
  });

  it("inicio_nao_consulta_nem_mostra_o_vale", async () => {
    apiLeitura.obterReceita.mockResolvedValue({ tipo: "ok", dados: RECEITA });
    apiLeitura.obterGastoReal.mockResolvedValue({ tipo: "ok", dados: GASTO });
    apiLeitura.obterR2.mockResolvedValue({ tipo: "ok", dados: R2 });
    apiLeitura.obterReserva.mockResolvedValue({ tipo: "ok", dados: RESERVA });
    apiLeitura.obterAlertas.mockResolvedValue({
      tipo: "ok",
      dados: { data_referencia: "2026-11-13", itens: [...ALERTAS, ALERTA_R5] },
    });
    renderizar("/");
    const alertas = await screen.findByRole("list", { name: "Alertas em destaque" });
    expect(alertas).toHaveTextContent("O saldo informado não bate");
    // R5 não vaza para a tela principal; a receita de benefício também não.
    expect(alertas).not.toHaveTextContent("vale");
    const principal = within(screen.getByRole("main"));
    expect(principal.queryByText(/vale/i)).not.toBeInTheDocument();
    expect(screen.queryByText("R$ 600,00")).not.toBeInTheDocument();
    expect(apiVale.obterSituacaoVale).not.toHaveBeenCalled();
    expect(apiVale.obterBeneficios).not.toHaveBeenCalled();
    expect(apiVale.obterParametroVale).not.toHaveBeenCalled();
    expect(apiVale.listarDecisoes).not.toHaveBeenCalled();
  });

  it("inicio_sem_alertas_tambem_leva_a_tela_de_alertas", async () => {
    apiLeitura.obterReceita.mockResolvedValue({ tipo: "ok", dados: RECEITA });
    apiLeitura.obterGastoReal.mockResolvedValue({ tipo: "ok", dados: GASTO });
    apiLeitura.obterR2.mockResolvedValue({ tipo: "ok", dados: R2 });
    apiLeitura.obterReserva.mockResolvedValue({ tipo: "ok", dados: RESERVA });
    apiLeitura.obterAlertas.mockResolvedValue({
      tipo: "ok",
      dados: { data_referencia: "2026-11-13", itens: [] },
    });
    renderizar("/");
    expect(await screen.findByText("Nenhum alerta neste resumo.")).toBeInTheDocument();
    expect(screen.queryByText("Há outros alertas.")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver todos os alertas" })).toHaveAttribute(
      "href",
      "/alertas",
    );
  });

  it("inicio_com_r5_nao_afirma_ausencia_de_alerta", async () => {
    apiLeitura.obterReceita.mockResolvedValue({ tipo: "ok", dados: RECEITA });
    apiLeitura.obterGastoReal.mockResolvedValue({ tipo: "ok", dados: GASTO });
    apiLeitura.obterR2.mockResolvedValue({ tipo: "ok", dados: R2 });
    apiLeitura.obterReserva.mockResolvedValue({ tipo: "ok", dados: RESERVA });
    apiLeitura.obterAlertas.mockResolvedValue({
      tipo: "ok",
      dados: { data_referencia: "2026-11-13", itens: [ALERTA_R5] },
    });
    renderizar("/");
    expect(await screen.findByText("Nenhum alerta neste resumo.")).toBeInTheDocument();
    // Não afirma ausência de alertas e não diz o que são (nada de vale na tela principal).
    expect(screen.queryByText(/Nenhum alerta no momento/)).not.toBeInTheDocument();
    expect(screen.getByText("Há outros alertas.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver os alertas" })).toHaveAttribute("href", "/alertas");
    const principal = within(screen.getByRole("main"));
    expect(principal.queryByText(/vale|estourou/i)).not.toBeInTheDocument();
  });
});

describe("glossário do vale", () => {
  it("explica_vale_bolso_resta_sobra_e_estouro", async () => {
    renderizar("/vale");
    await screen.findByRole("region", { name: "Bolso Pessoal" });
    const glossario = screen.getByText("O que significam estes termos?").closest("details");
    expect(glossario).not.toBeNull();
    for (const nome of ["Vale (VR)", "Bolso", "Resta", "Sobra do vale", "Estouro"]) {
      expect(within(glossario as HTMLElement).getByText(nome)).toBeInTheDocument();
    }
  });
});
