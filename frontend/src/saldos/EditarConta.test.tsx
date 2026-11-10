import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as contas from "../api/contas";
import type { ContaSaida, SaldoSaida } from "../api/gerado";
import * as saldos from "../api/saldos";
import * as sessao from "../api/sessao";

vi.mock("../api/sessao");
vi.mock("../api/saldos");
vi.mock("../api/contas");
const apiSessao = vi.mocked(sessao);
const apiSaldos = vi.mocked(saldos);
const apiContas = vi.mocked(contas);

function saldo(parcial: Partial<SaldoSaida> & Pick<SaldoSaida, "conta_id" | "nome">): SaldoSaida {
  return {
    conta_beneficio: false,
    tipo: "corrente",
    conta_mae_id: null,
    saldo: "0.00",
    snapshot_data: null,
    snapshot_valor: null,
    ...parcial,
  };
}

const CAIXINHA: ContaSaida = {
  conta_id: 2,
  nome: "Banco A Caixinha",
  conta_beneficio: false,
  tipo: "corrente",
  conta_mae_id: null,
  versao: 1,
};

function renderizar() {
  return render(
    <MemoryRouter initialEntries={["/contas"]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiSaldos.listarSaldos.mockResolvedValue({
    tipo: "ok",
    saldos: [
      saldo({ conta_id: 1, nome: "Banco A" }),
      saldo({ conta_id: 2, nome: "Banco A Caixinha" }),
    ],
  });
  apiContas.obterConta.mockResolvedValue({ tipo: "ok", conta: CAIXINHA });
});

afterEach(() => {
  vi.resetAllMocks();
});

async function abrirEdicao() {
  renderizar();
  const usuario = userEvent.setup();
  await usuario.click(await screen.findByRole("button", { name: "Editar conta Banco A Caixinha" }));
  const form = await screen.findByRole("form", { name: "Editar conta Banco A Caixinha" });
  return { usuario, form };
}

describe("editar conta", () => {
  it("marca_a_caixinha_como_reserva_do_banco", async () => {
    apiContas.editarConta.mockResolvedValue({
      tipo: "ok",
      conta: { ...CAIXINHA, tipo: "reserva", conta_mae_id: 1, versao: 2 },
    });
    const { usuario, form } = await abrirEdicao();
    expect(within(form).getByLabelText("Nome da conta")).toHaveValue("Banco A Caixinha");
    // "Pertence ao banco" só aparece para reserva ou investimento.
    expect(within(form).queryByLabelText("Pertence ao banco")).not.toBeInTheDocument();

    await usuario.selectOptions(within(form).getByLabelText("Tipo"), "reserva");
    const banco = within(form).getByLabelText("Pertence ao banco");
    // A própria conta não aparece como banco dela mesma.
    expect(within(banco).queryByRole("option", { name: "Banco A Caixinha" })).toBeNull();
    await usuario.selectOptions(banco, "Banco A");
    await usuario.click(within(form).getByRole("button", { name: "Salvar conta" }));

    expect(apiContas.editarConta).toHaveBeenCalledWith(2, 1, "Banco A Caixinha", "reserva", 1);
    expect(await within(form).findByRole("status")).toHaveTextContent("Alteração salva");
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(2);
  });

  it("conflito_pede_para_reabrir", async () => {
    apiContas.editarConta.mockResolvedValue({ tipo: "desatualizada" });
    const { usuario, form } = await abrirEdicao();
    await usuario.click(within(form).getByRole("button", { name: "Salvar conta" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("mudou em outra aba");
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(1);
  });

  it("mensagem_de_regra_vem_do_servidor", async () => {
    apiContas.editarConta.mockResolvedValue({
      tipo: "invalido",
      mensagem: "esta conta tem reserva ou investimento ligado a ela",
    });
    const { usuario, form } = await abrirEdicao();
    await usuario.click(within(form).getByRole("button", { name: "Salvar conta" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("reserva ou investimento");
  });

  it("erro_ao_carregar_tenta_de_novo", async () => {
    apiContas.obterConta
      .mockResolvedValueOnce({ tipo: "erro" })
      .mockResolvedValueOnce({ tipo: "ok", conta: CAIXINHA });
    renderizar();
    const usuario = userEvent.setup();
    await usuario.click(await screen.findByRole("button", { name: "Editar conta Banco A Caixinha" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar a conta");
    await usuario.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("form", { name: "Editar conta Banco A Caixinha" })).toBeInTheDocument();
  });
});

describe("tipo e banco na lista", () => {
  it("mostra_etiqueta_e_a_que_banco_pertence", async () => {
    apiSaldos.listarSaldos.mockResolvedValue({
      tipo: "ok",
      saldos: [
        saldo({ conta_id: 1, nome: "Banco A" }),
        saldo({ conta_id: 2, nome: "Banco A Caixinha", tipo: "reserva", conta_mae_id: 1 }),
        saldo({ conta_id: 3, nome: "Vale", tipo: "beneficio", conta_beneficio: true }),
      ],
    });
    renderizar();
    const lista = await screen.findByRole("list", { name: "Saldos por conta" });
    expect(within(lista).getByText("Reserva")).toBeInTheDocument();
    expect(within(lista).getByText("Benefício")).toBeInTheDocument();
    expect(
      within(lista).getByText("Pertence a Banco A, com saldo separado da conta corrente."),
    ).toBeInTheDocument();
  });
});
