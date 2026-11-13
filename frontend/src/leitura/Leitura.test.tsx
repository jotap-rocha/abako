import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import type { GastoRealSaida } from "../api/gerado";
import type { Leitura } from "../api/leitura";
import * as leitura from "../api/leitura";
import * as sessao from "../api/sessao";
import { deslocarMes, mesAtual } from "../datas";
import {
  ALERTAS,
  CARTAO,
  CORRENTE,
  FATURA,
  GASTO,
  LIMITE,
  PESSOAS,
  R2,
  RECEITA,
  RECORRENTES,
  RESERVA,
  RESERVA_SEM_CONFIG,
} from "./dadosDeTeste";

// A fronteira com o servidor é a única coisa simulada; o App e as telas rodam de verdade.
vi.mock("../api/sessao");
vi.mock("../api/leitura");
const api = vi.mocked(leitura);
const apiSessao = vi.mocked(sessao);

function renderizar(rota: string) {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  api.listarContas.mockResolvedValue({ tipo: "ok", dados: [CORRENTE, CARTAO] });
  api.listarPessoas.mockResolvedValue({ tipo: "ok", dados: PESSOAS });
  api.listarRecorrentes.mockResolvedValue({ tipo: "ok", dados: RECORRENTES });
  api.obterFatura.mockResolvedValue({ tipo: "ok", dados: FATURA });
  api.obterLimite.mockResolvedValue({ tipo: "ok", dados: LIMITE });
  api.obterGastoReal.mockResolvedValue({ tipo: "ok", dados: GASTO });
  api.obterReceita.mockResolvedValue({ tipo: "ok", dados: RECEITA });
  api.obterReserva.mockResolvedValue({ tipo: "ok", dados: RESERVA });
  api.obterR2.mockResolvedValue({ tipo: "ok", dados: R2 });
  api.obterAlertas.mockResolvedValue({
    tipo: "ok",
    dados: { data_referencia: "2026-11-12", itens: ALERTAS },
  });
});

afterEach(() => {
  // Desmonta as telas antes de limpar os mocks, para nenhuma busca pendente cair em mock vazio.
  cleanup();
  vi.resetAllMocks();
});

describe("telas de leitura: valores da API", () => {
  it("sem_regra_no_front", async () => {
    // Cada resposta é incoerente de propósito (total que não soma, nível que não combina com a
    // falta, alerta fora da ordem de gravidade). Se a tela recalculasse algo, o texto mudaria.

    // Cartões: total, própria e terceiros exatamente como vieram; limite negativo idem.
    const cartoes = renderizar("/cartoes");
    expect(await screen.findByText("R$ 999,00")).toBeInTheDocument();
    expect(screen.getByText("R$ 111,11")).toBeInTheDocument();
    expect(screen.getByText("R$ 222,22")).toBeInTheDocument();
    expect(await screen.findByText("-R$ 250,00")).toBeInTheDocument();
    cartoes.unmount();

    // Gasto real e receita: total ≠ soma das contas.
    const gasto = renderizar("/gasto-real");
    expect(await screen.findByText("R$ 7.777,77")).toBeInTheDocument();
    expect(screen.getByText("R$ 4.321,09")).toBeInTheDocument();
    // O benefício da receita não aparece (é do vale, task 20).
    expect(screen.queryByText("R$ 600,00")).not.toBeInTheDocument();
    gasto.unmount();

    // Reserva: nível "critica" com falta zero e cobertura 9,99 saem como vieram.
    const reserva = renderizar("/reserva");
    expect(await screen.findByText("Crítica")).toBeInTheDocument();
    // Cobertura em decimal brasileiro (só troca o separador do texto da API).
    expect(screen.getByText("9,99 meses")).toBeInTheDocument();
    expect(screen.getByText("R$ 0,00")).toBeInTheDocument();
    expect(screen.getByText("R$ 12,34")).toBeInTheDocument();
    expect(screen.getByText("R$ 321,00")).toBeInTheDocument();
    expect(screen.getByText("30/06/2027")).toBeInTheDocument();
    reserva.unmount();

    // Sobra: o valor da API, mesmo sem bater com disponível − compromissos.
    const sobra = renderizar("/sobra");
    expect(await screen.findByText("-R$ 8.888,88")).toBeInTheDocument();
    sobra.unmount();

    // Alertas: a ordem da API é mantida (a "baixa" vem antes da "alta").
    renderizar("/alertas");
    const lista = await screen.findByRole("list", { name: "Alertas" });
    const itens = within(lista).getAllByRole("listitem");
    expect(itens[0]).toHaveTextContent("Informe o gasto essencial");
    expect(itens[1]).toHaveTextContent("O saldo informado não bate");
  });
});

describe("cartões e faturas", () => {
  it("mostra_fatura_itens_pessoa_e_limite", async () => {
    renderizar("/cartoes");
    const itens = await screen.findByRole("list", { name: "Itens da fatura" });
    const [parcela, terceiro, credito] = within(itens).getAllByRole("listitem");
    expect(parcela).toHaveTextContent("parcela 2 de 3");
    expect(parcela).toHaveTextContent("Própria");
    expect(terceiro).toHaveTextContent("Terceiro: Maria Teste");
    // Crédito de estorno: valor negativo, rotulado e não como parcela.
    expect(credito).toHaveTextContent("crédito de estorno");
    expect(credito).toHaveTextContent("-R$ 15,50");
    expect(credito).not.toHaveTextContent("parcela");
    // Limite usado e disponível negativo, com a explicação.
    expect(await screen.findByText("R$ 5.250,00")).toBeInTheDocument();
    expect(screen.getByText(/O disponível está negativo/)).toBeInTheDocument();
    expect(api.obterFatura).toHaveBeenCalledWith(7, mesAtual());
    expect(api.obterLimite).toHaveBeenCalledWith(3);
  });

  it("fatura_aberta_e_fechada_vem_da_api", async () => {
    const aberta = renderizar("/cartoes");
    expect(await screen.findByText("Aberta")).toBeInTheDocument();
    expect(screen.getByText(/Fecha em 10\/11\/2026/)).toBeInTheDocument();
    aberta.unmount();

    api.obterFatura.mockResolvedValue({ tipo: "ok", dados: { ...FATURA, situacao: "fechada" } });
    const fechada = renderizar("/cartoes");
    expect(await screen.findByText("Fechada")).toBeInTheDocument();
    expect(screen.getByText(/Fechou em 10\/11\/2026/)).toBeInTheDocument();
    fechada.unmount();

    // Sem dia de fechamento cadastrado a API manda nulos: a tela avisa em vez de adivinhar.
    api.obterFatura.mockResolvedValue({
      tipo: "ok",
      dados: { ...FATURA, situacao: null, fechamento: null },
    });
    renderizar("/cartoes");
    expect(await screen.findByText(/ainda não tem dia de fechamento/)).toBeInTheDocument();
  });

  it("navega_entre_competencias", async () => {
    renderizar("/cartoes");
    await screen.findByRole("list", { name: "Itens da fatura" });
    await userEvent.setup().click(screen.getByRole("button", { name: "Mês anterior" }));
    await waitFor(() =>
      expect(api.obterFatura).toHaveBeenLastCalledWith(7, deslocarMes(mesAtual(), -1)),
    );
  });

  it("vazio_sem_cartao_e_fatura_sem_itens", async () => {
    api.listarContas.mockResolvedValue({ tipo: "ok", dados: [CORRENTE] });
    const vazio = renderizar("/cartoes");
    expect(await screen.findByText("Nenhum cartão ainda")).toBeInTheDocument();
    vazio.unmount();

    api.listarContas.mockResolvedValue({ tipo: "ok", dados: [CARTAO] });
    api.obterFatura.mockResolvedValue({ tipo: "ok", dados: { ...FATURA, itens: [] } });
    renderizar("/cartoes");
    expect(await screen.findByText("Fatura sem itens")).toBeInTheDocument();
  });
});

describe("gasto real e receita do mês", () => {
  it("nomeia_as_contas_e_navega_para_meses_anteriores", async () => {
    renderizar("/gasto-real");
    const lista = await screen.findByRole("list", { name: "Gasto real por conta" });
    const linhas = within(lista).getAllByRole("listitem");
    expect(linhas[0]).toHaveTextContent("Conta principal");
    expect(linhas[1]).toHaveTextContent("Cartão azul");
    expect(api.obterGastoReal).toHaveBeenCalledWith(mesAtual());

    // Mês corrente: não dá para ir ao futuro; o anterior chama a API com o mês anterior.
    expect(screen.getByRole("button", { name: "Próximo mês" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("button", { name: "Mês anterior" }));
    await waitFor(() =>
      expect(api.obterGastoReal).toHaveBeenLastCalledWith(deslocarMes(mesAtual(), -1)),
    );
    expect(api.obterReceita).toHaveBeenLastCalledWith(deslocarMes(mesAtual(), -1));
  });

  it("mes_sem_gasto_mostra_vazio_e_mes_invalido_mostra_erro", async () => {
    api.obterGastoReal.mockResolvedValue({
      tipo: "ok",
      dados: { ...GASTO, total: "0.00", por_conta: [] },
    });
    const vazio = renderizar("/gasto-real");
    expect(await screen.findByText("Nenhum gasto neste mês")).toBeInTheDocument();
    vazio.unmount();

    api.obterGastoReal.mockResolvedValue({ tipo: "invalido" });
    renderizar("/gasto-real");
    expect(await screen.findByRole("alert")).toHaveTextContent("mês inválido");
  });
});

describe("reserva", () => {
  it("config_pendente_e_pedido_de_configuracao_nao_alerta", async () => {
    api.obterReserva.mockResolvedValue({ tipo: "ok", dados: RESERVA_SEM_CONFIG });
    renderizar("/reserva");
    const aviso = await screen.findByRole("note");
    expect(aviso).toHaveTextContent("Falta configurar a reserva");
    expect(within(aviso).getByRole("link", { name: "Configurar a reserva" })).toHaveAttribute(
      "href",
      "/parametros",
    );
    // Sem nível nem meta: a tela não inventa um.
    expect(screen.getByText("Sem nível (falta configurar)")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("sobra do R2", () => {
  it("agrupa_itens_com_nomes_e_marca_fatura_parcial", async () => {
    renderizar("/sobra");
    const fixas = await screen.findByRole("region", { name: "Contas fixas" });
    expect(fixas).toHaveTextContent("Aluguel");
    expect(fixas).toHaveTextContent("R$ 800,00");
    const faturas = screen.getByRole("region", { name: "Faturas próprias" });
    expect(faturas).toHaveTextContent("Fatura de Cartão azul (2026-11)");
    expect(faturas).toHaveTextContent("fatura aberta (parcial)");
    expect(faturas).toHaveTextContent("fatura de R$ 450,00");
    // Vencida: lista à parte, com o nome do recorrente.
    const vencidas = screen.getByRole("region", { name: /Vencidas/ });
    expect(vencidas).toHaveTextContent("Internet");
    expect(screen.getByText(/A sobra está negativa/)).toBeInTheDocument();
    expect(screen.queryByText(/há cartão com dívida sem vencimento/)).not.toBeInTheDocument();
  });

  it("sobra_nao_confiavel_avisa_com_clareza", async () => {
    api.obterR2.mockResolvedValue({
      tipo: "ok",
      dados: { ...R2, pendencias_vencimento: 1, alerta: false, sobra: "10.00" },
    });
    renderizar("/sobra");
    expect(await screen.findByText(/há cartão com dívida sem vencimento/)).toBeInTheDocument();
    expect(screen.getAllByText("Sobra não confiável").length).toBeGreaterThan(0);
    expect(screen.queryByText(/A sobra está negativa/)).not.toBeInTheDocument();
  });
});

describe("alertas", () => {
  it("mostra_mensagem_acao_e_conta_do_r4_sem_botao_de_dispensar", async () => {
    renderizar("/alertas");
    const lista = await screen.findByRole("list", { name: "Alertas" });
    const [config, r4] = within(lista).getAllByRole("listitem");
    if (config === undefined || r4 === undefined) throw new Error("faltam itens");
    // CONFIG é pedido de configuração, não alerta.
    expect(config).toHaveTextContent("pedido de configuração");
    expect(config).toHaveTextContent("Informe o gasto essencial mensal");
    expect(within(config).getByRole("link", { name: "Configurar" })).toBeInTheDocument();
    // R4: nome da conta resolvido pelo id, números da API e ação sugerida.
    expect(r4).toHaveTextContent("Conta principal");
    expect(r4).toHaveTextContent("calculou R$ 950,00 e você informou R$ 900,00");
    expect(r4).toHaveTextContent("R$ 50,00");
    expect(r4).toHaveTextContent("Confira o saldo informado");
    expect(r4).toHaveTextContent("severidade Alta");
    expect(
      screen.queryByRole("button", { name: /dispensar|ignorar|fechar/i }),
    ).not.toBeInTheDocument();
  });

  it("sem_alertas_mostra_vazio", async () => {
    api.obterAlertas.mockResolvedValue({
      tipo: "ok",
      dados: { data_referencia: "2026-11-12", itens: [] },
    });
    renderizar("/alertas");
    expect(await screen.findByText("Nenhum alerta")).toBeInTheDocument();
  });
});

describe("estados comuns", () => {
  it("mostra_carregando_ate_a_api_responder", async () => {
    api.obterAlertas.mockReturnValue(new Promise(() => undefined));
    renderizar("/alertas");
    expect(await screen.findByText("Carregando alertas…")).toBeInTheDocument();
  });

  it("erro_tenta_de_novo_e_sessao_expirada_volta_ao_login", async () => {
    api.obterReserva
      .mockResolvedValueOnce({ tipo: "erro" })
      .mockResolvedValueOnce({ tipo: "ok", dados: RESERVA });
    const { unmount } = renderizar("/reserva");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar a reserva",
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Crítica")).toBeInTheDocument();
    unmount();

    api.obterAlertas.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar("/alertas");
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});

describe("início", () => {
  it("resume_receita_gasto_sobra_reserva_e_alertas_sem_o_vale", async () => {
    renderizar("/");
    expect(await screen.findByText("R$ 4.321,09")).toBeInTheDocument();
    expect(await screen.findByText("R$ 7.777,77")).toBeInTheDocument();
    expect(await screen.findByText("-R$ 8.888,88")).toBeInTheDocument();
    expect(await screen.findByText("Crítica")).toBeInTheDocument();
    const alertas = await screen.findByRole("list", { name: "Alertas em destaque" });
    expect(alertas).toHaveTextContent("O saldo informado não bate");
    expect(screen.queryByText(/\bvale\b/i)).not.toBeInTheDocument();
  });

  it("um_cartao_com_erro_nao_derruba_os_outros", async () => {
    api.obterGastoReal.mockResolvedValue({ tipo: "erro" });
    renderizar("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("gasto real");
    expect(await screen.findByText("R$ 4.321,09")).toBeInTheDocument();
  });
});

describe("troca de mês e de competência", () => {
  const anterior = deslocarMes(mesAtual(), -1);
  const retrasado = deslocarMes(mesAtual(), -2);

  /** Gasto real do mês corrente responde na hora; os outros meses ficam esperando `resolver`. */
  function gastoPendente() {
    const esperando = new Map<string, (r: Leitura<GastoRealSaida>) => void>();
    api.obterGastoReal.mockImplementation((mes) =>
      mes === mesAtual()
        ? Promise.resolve({ tipo: "ok", dados: GASTO })
        : new Promise((resolver) => esperando.set(mes, resolver)),
    );
    return esperando;
  }

  it("resposta_antiga_nao_sobrescreve_a_nova", async () => {
    const esperando = gastoPendente();
    renderizar("/gasto-real");
    await screen.findByText("R$ 7.777,77");
    const usuario = userEvent.setup();
    // Dois cliques seguidos: pede o mês anterior e, antes de ele responder, o retrasado.
    await usuario.click(screen.getByRole("button", { name: "Mês anterior" }));
    await usuario.click(screen.getByRole("button", { name: "Mês anterior" }));
    await waitFor(() => expect(esperando.size).toBe(2));

    // A resposta nova chega primeiro; a antiga chega depois e não pode tomar o lugar dela.
    await act(async () => {
      esperando.get(retrasado)?.({ tipo: "ok", dados: { ...GASTO, total: "222.22" } });
    });
    expect(await screen.findByText("R$ 222,22")).toBeInTheDocument();
    await act(async () => {
      esperando.get(anterior)?.({ tipo: "ok", dados: { ...GASTO, total: "111.11" } });
    });
    expect(screen.getByText("R$ 222,22")).toBeInTheDocument();
    expect(screen.queryByText("R$ 111,11")).not.toBeInTheDocument();
  });

  it("nunca_mostra_valor_do_mes_antigo_sob_o_titulo_do_novo", async () => {
    gastoPendente();
    renderizar("/gasto-real");
    await screen.findByText("R$ 7.777,77");
    await userEvent.setup().click(screen.getByRole("button", { name: "Mês anterior" }));
    // Logo após o clique, sem resposta ainda: some o valor velho e aparece "carregando".
    expect(screen.queryByText("R$ 7.777,77")).not.toBeInTheDocument();
    expect(screen.getByText("Carregando o mês…")).toBeInTheDocument();
  });

  it("fatura_antiga_some_ao_trocar_de_competencia", async () => {
    api.obterFatura.mockImplementation((_conta, competencia) =>
      competencia === mesAtual()
        ? Promise.resolve({ tipo: "ok", dados: FATURA })
        : new Promise(() => undefined),
    );
    renderizar("/cartoes");
    await screen.findByText("R$ 999,00");
    await userEvent.setup().click(screen.getByRole("button", { name: "Mês anterior" }));
    expect(screen.queryByText("R$ 999,00")).not.toBeInTheDocument();
    expect(screen.getByText("Carregando fatura…")).toBeInTheDocument();
  });
});

describe("prioridade de erro: sessão vencida vence", () => {
  it("gasto_real_com_401_e_500_volta_ao_login", async () => {
    api.obterGastoReal.mockResolvedValue({ tipo: "erro" });
    api.listarContas.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar("/gasto-real");
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });

  it("sobra_com_500_antes_e_401_depois_volta_ao_login", async () => {
    api.obterR2.mockResolvedValue({ tipo: "erro" });
    api.listarRecorrentes.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar("/sobra");
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });

  it("cartoes_com_500_e_401_volta_ao_login", async () => {
    api.listarContas.mockResolvedValue({ tipo: "erro" });
    api.listarPessoas.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar("/cartoes");
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});
