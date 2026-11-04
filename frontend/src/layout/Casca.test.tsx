import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as contas from "../api/contas";
import * as sessao from "../api/sessao";

vi.mock("../api/sessao");
vi.mock("../api/contas");
const apiSessao = vi.mocked(sessao);
const apiContas = vi.mocked(contas);

function renderizar(rota = "/") {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiContas.listarContas.mockResolvedValue({ tipo: "ok", contas: [] });
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("casca do app", () => {
  it("menu_leva_as_quatro_paginas", async () => {
    renderizar();
    const menu = await screen.findByRole("navigation", { name: "Principal" });
    const itens = within(menu)
      .getAllByRole("link")
      .map((l) => l.textContent);
    expect(itens).toEqual(["Início", "Contas", "Lançamentos", "Alertas"]);

    const usuario = userEvent.setup();
    await usuario.click(within(menu).getByRole("link", { name: "Lançamentos" }));
    expect(await screen.findByRole("heading", { name: "Lançamentos" })).toBeInTheDocument();
    expect(within(menu).getByRole("link", { name: "Lançamentos" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("rota_desconhecida_mostra_pagina_nao_encontrada", async () => {
    renderizar("/nao-existe");
    expect(await screen.findByRole("heading", { name: "Página não encontrada" })).toBeInTheDocument();
  });

  it("inicio_mostra_cartoes_em_breve_sem_numeros", async () => {
    renderizar();
    expect(await screen.findByRole("heading", { name: "Início" })).toBeInTheDocument();
    expect(screen.getAllByText("Em breve").length).toBeGreaterThan(0);
  });
});

describe("pagina de contas (modelo dos estados)", () => {
  it("mostra_carregando_depois_a_lista", async () => {
    apiContas.listarContas.mockResolvedValue({
      tipo: "ok",
      contas: [
        { conta_id: 1, nome: "Conta corrente", conta_beneficio: false },
        { conta_id: 2, nome: "Vale", conta_beneficio: true },
      ],
    });
    renderizar("/contas");

    expect(await screen.findByText("Conta corrente")).toBeInTheDocument();
    expect(screen.getByText("Vale")).toBeInTheDocument();
    expect(screen.getAllByText("Benefício")).toHaveLength(1);
  });

  it("mostra_estado_vazio", async () => {
    renderizar("/contas");
    expect(await screen.findByText("Nenhuma conta ainda")).toBeInTheDocument();
  });

  it("mostra_erro_e_tenta_de_novo", async () => {
    apiContas.listarContas.mockResolvedValueOnce({ tipo: "erro" });
    renderizar("/contas");
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar");

    apiContas.listarContas.mockResolvedValueOnce({
      tipo: "ok",
      contas: [{ conta_id: 1, nome: "Poupança", conta_beneficio: false }],
    });
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Poupança")).toBeInTheDocument();
    expect(apiContas.listarContas).toHaveBeenCalledTimes(2);
  });

  it("sessao_expirada_volta_ao_login", async () => {
    apiContas.listarContas.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar("/contas");
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});
