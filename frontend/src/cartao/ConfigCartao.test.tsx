import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as apiLeitura from "../api/leitura";
import * as sessao from "../api/sessao";
import * as vigencias from "../api/vigencias";
import {
  CARTAO,
  CORRENTE,
  FATURA,
  LIMITE,
  PESSOAS,
} from "../leitura/dadosDeTeste";

vi.mock("../api/leitura");
vi.mock("../api/sessao");
vi.mock("../api/vigencias");
const leitura = vi.mocked(apiLeitura);
const apiSessao = vi.mocked(sessao);
const api = vi.mocked(vigencias);

function pagina() {
  return render(
    <MemoryRouter initialEntries={["/cartoes"]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  leitura.listarContas.mockResolvedValue({ tipo: "ok", dados: [CORRENTE, CARTAO] });
  leitura.listarPessoas.mockResolvedValue({ tipo: "ok", dados: PESSOAS });
  leitura.obterFatura.mockResolvedValue({ tipo: "ok", dados: FATURA });
  leitura.obterLimite.mockResolvedValue({ tipo: "ok", dados: LIMITE });
  api.listarFechamentos.mockResolvedValue({
    tipo: "ok",
    dados: [{ dia: 10, vigente_desde: "2026-01-01" }],
  });
  api.listarVencimentos.mockResolvedValue({ tipo: "ok", dados: [] });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("fechamento e vencimento do cartão", () => {
  it("grava_fechamento_com_vigencia_e_atualiza_a_fatura", async () => {
    const usuario = userEvent.setup();
    api.gravarFechamento.mockResolvedValue({
      tipo: "ok",
      dados: { dia: 31, vigente_desde: "2026-12-01" },
    });
    pagina();
    const historico = await screen.findByRole("list", { name: "Histórico: Dia de fechamento" });
    expect(historico).toHaveTextContent("Dia 10, a partir de 01/01/2026");
    // O vencimento ainda não tem nada: vazio tratado.
    expect(await screen.findByText("Nenhum dia cadastrado ainda.")).toBeInTheDocument();

    const form = screen.getByRole("form", { name: "Novo dia de fechamento" });
    // A explicação do dia inexistente está na tela.
    expect(form).toHaveTextContent("último dia do mês");
    const chamadasDaFatura = leitura.obterFatura.mock.calls.length;

    // Dia fora de 1 a 31 não é enviado.
    await usuario.type(within(form).getByLabelText("Dia do mês"), "0");
    await usuario.click(within(form).getByRole("button", { name: "Salvar dia de fechamento" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("de 1 a 31");
    expect(api.gravarFechamento).not.toHaveBeenCalled();

    await usuario.clear(within(form).getByLabelText("Dia do mês"));
    await usuario.type(within(form).getByLabelText("Dia do mês"), "31");
    fireEvent.change(within(form).getByLabelText("Vigente desde"), { target: { value: "2026-12-01" } });
    await usuario.click(within(form).getByRole("button", { name: "Salvar dia de fechamento" }));
    await vi.waitFor(() => expect(api.gravarFechamento).toHaveBeenCalledWith(7, 31, "2026-12-01"));
    expect(await within(form).findByRole("status")).toHaveTextContent("dia 31, a partir de 01/12/2026");
    // Histórico e fatura (situação aberta/fechada) são buscados de novo no servidor.
    await vi.waitFor(() => expect(api.listarFechamentos).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(leitura.obterFatura.mock.calls.length).toBeGreaterThan(chamadasDaFatura));
  });

  it("grava_vencimento_e_mostra_a_recusa_do_banco", async () => {
    const usuario = userEvent.setup();
    api.gravarVencimento.mockResolvedValue({
      tipo: "invalido",
      mensagem: "vigente_desde antes de 2000-01-01",
    });
    pagina();
    const form = await screen.findByRole("form", { name: "Novo dia de vencimento" });
    await usuario.type(within(form).getByLabelText("Dia do mês"), "20");
    await usuario.click(within(form).getByRole("button", { name: "Salvar dia de vencimento" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("vigente_desde antes de 2000-01-01");
    expect(api.gravarVencimento).toHaveBeenCalledWith(7, 20, expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/));
  });

  it("sessao_vencida_ao_gravar_volta_ao_login", async () => {
    const usuario = userEvent.setup();
    api.gravarVencimento.mockResolvedValue({ tipo: "sessao_expirada" });
    pagina();
    const form = await screen.findByRole("form", { name: "Novo dia de vencimento" });
    await usuario.type(within(form).getByLabelText("Dia do mês"), "20");
    await usuario.click(within(form).getByRole("button", { name: "Salvar dia de vencimento" }));
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });

  it("erro_ao_carregar_o_historico_tem_nova_tentativa", async () => {
    const usuario = userEvent.setup();
    api.listarVencimentos.mockResolvedValueOnce({ tipo: "erro" });
    pagina();
    expect(await screen.findByText("Não foi possível carregar o dia de vencimento.")).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Nenhum dia cadastrado ainda.")).toBeInTheDocument();
  });
});
