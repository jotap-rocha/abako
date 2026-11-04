import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import type { SnapshotSaida } from "../api/gerado";
import * as saldos from "../api/saldos";
import * as sessao from "../api/sessao";

vi.mock("../api/sessao");
vi.mock("../api/saldos");
vi.mock("../api/contas");
const apiSessao = vi.mocked(sessao);
const apiSaldos = vi.mocked(saldos);

const CONTA = {
  conta_id: 3,
  nome: "Conta principal",
  conta_beneficio: false,
  saldo: "1000.00",
  snapshot_data: "2026-11-01",
  snapshot_valor: "1000.00",
};

function snapshot(parcial: Partial<SnapshotSaida>): SnapshotSaida {
  return {
    snapshot_id: 9,
    conta_id: 3,
    data: "2026-11-04",
    valor: "950.00",
    saldo_inicial: false,
    saldo_derivado: null,
    divergencia: null,
    ...parcial,
  };
}

async function abrirEInformar(valor: string) {
  render(
    <MemoryRouter initialEntries={["/contas"]}>
      <App />
    </MemoryRouter>,
  );
  const usuario = userEvent.setup();
  await usuario.click(await screen.findByRole("button", { name: "Informar saldo de Conta principal" }));
  const form = screen.getByRole("form", { name: "Informar saldo de Conta principal" });
  await usuario.type(within(form).getByLabelText("Saldo no banco (R$)"), valor);
  await usuario.click(within(form).getByRole("button", { name: "Salvar saldo" }));
  return form;
}

beforeEach(() => {
  // Relógio fixo (só a data; os timers seguem reais para o userEvent): 15h UTC = 12h em SP.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-04T15:00:00Z"));
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiSaldos.listarSaldos.mockResolvedValue({ tipo: "ok", saldos: [CONTA] });
});

afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("informar saldo (snapshot)", () => {
  it("mostra_divergencia", async () => {
    // Os três valores vêm da API; a tela não os calcula (divergência = derivado − snapshot).
    apiSaldos.registrarSnapshot.mockResolvedValue({
      tipo: "ok",
      snapshot: snapshot({
        valor: "950.00",
        saldo_derivado: "1000.00",
        divergencia: "50.00",
      }),
    });
    const form = await abrirEInformar("950,00");

    const resultado = await within(form).findByRole("status");
    expect(resultado).toHaveTextContent("Divergência de R$ 50,00.");
    expect(resultado).toHaveTextContent(
      "Em 04/11/2026, o abako calculou R$ 1.000,00, mas o banco mostra R$ 950,00.",
    );
    expect(resultado).toHaveTextContent("Nada foi corrigido sozinho");
    // Valor digitado no jeito brasileiro vai no formato da API; a data padrão é hoje.
    expect(apiSaldos.registrarSnapshot).toHaveBeenCalledWith(3, "2026-11-04", "950.00");
    // Depois de salvar, a lista é buscada de novo no servidor, e o resultado continua na tela.
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(2);
  });

  it("mostra_saldo_inicial", async () => {
    apiSaldos.registrarSnapshot.mockResolvedValue({
      tipo: "ok",
      snapshot: snapshot({ saldo_inicial: true, valor: "1234.56" }),
    });
    const form = await abrirEInformar("1.234,56");

    expect(await within(form).findByRole("status")).toHaveTextContent(
      "Saldo inicial registrado: R$ 1.234,56 em 04/11/2026.",
    );
    expect(apiSaldos.registrarSnapshot).toHaveBeenCalledWith(3, "2026-11-04", "1234.56");
  });

  it("mostra_que_confere", async () => {
    apiSaldos.registrarSnapshot.mockResolvedValue({
      tipo: "ok",
      snapshot: snapshot({ valor: "1000.00" }),
    });
    const form = await abrirEInformar("1000");

    expect(await within(form).findByRole("status")).toHaveTextContent("Confere.");
  });

  it("valor_invalido_nao_chama_a_api", async () => {
    const form = await abrirEInformar("dez reais");

    expect(await within(form).findByRole("alert")).toHaveTextContent("Valor não reconhecido");
    expect(apiSaldos.registrarSnapshot).not.toHaveBeenCalled();
  });

  it("recusa_do_servidor_vira_mensagem", async () => {
    apiSaldos.registrarSnapshot.mockResolvedValue({ tipo: "invalido" });
    const form = await abrirEInformar("10,00");

    expect(await within(form).findByRole("alert")).toHaveTextContent("A data não pode ser futura");
  });

  it("conta_sumida_e_falha_de_rede_viram_mensagem", async () => {
    apiSaldos.registrarSnapshot
      .mockResolvedValueOnce({ tipo: "conta_nao_encontrada" })
      .mockResolvedValueOnce({ tipo: "erro" });
    const form = await abrirEInformar("10,00");
    expect(await within(form).findByRole("alert")).toHaveTextContent("conta não foi encontrada");

    // O valor fica no campo depois de um erro: basta salvar de novo.
    const usuario = userEvent.setup();
    expect(within(form).getByLabelText("Saldo no banco (R$)")).toHaveValue("10,00");
    await usuario.click(within(form).getByRole("button", { name: "Salvar saldo" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent(
      "Não foi possível falar com o servidor",
    );
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(1);
  });

  it("data_padrao_e_hoje_em_sao_paulo_e_futuro_e_bloqueado", async () => {
    render(
      <MemoryRouter initialEntries={["/contas"]}>
        <App />
      </MemoryRouter>,
    );
    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: "Informar saldo de Conta principal" }));
    const campo = screen.getByLabelText("Data do saldo");
    expect(campo).toHaveValue("2026-11-04");
    expect(campo).toHaveAttribute("max", "2026-11-04");
    expect(campo).toHaveAttribute("min", "2000-01-01");
  });

  it("sessao_expirada_volta_ao_login", async () => {
    apiSaldos.registrarSnapshot.mockResolvedValue({ tipo: "sessao_expirada" });
    await abrirEInformar("10,00");

    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});
