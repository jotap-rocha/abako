import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as saldos from "../api/saldos";
import * as sessao from "../api/sessao";

vi.mock("../api/sessao");
vi.mock("../api/saldos");
const apiSessao = vi.mocked(sessao);
const apiSaldos = vi.mocked(saldos);

function renderizar(rota = "/") {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiSaldos.listarSaldos.mockResolvedValue({ tipo: "ok", saldos: [] });
  apiSaldos.listarDivergencias.mockResolvedValue({ tipo: "ok", divergencias: [] });
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
