import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as leitura from "../api/leitura";
import * as saldos from "../api/saldos";
import * as sessao from "../api/sessao";

vi.mock("../api/sessao");
vi.mock("../api/saldos");
vi.mock("../api/leitura");
const apiSessao = vi.mocked(sessao);
const apiSaldos = vi.mocked(saldos);
const apiLeitura = vi.mocked(leitura);

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
  // As telas de leitura buscam dados ao abrir; aqui basta que fiquem carregando.
  const pendente = () => new Promise<never>(() => undefined);
  apiLeitura.obterReceita.mockImplementation(pendente);
  apiLeitura.obterGastoReal.mockImplementation(pendente);
  apiLeitura.obterR2.mockImplementation(pendente);
  apiLeitura.obterReserva.mockImplementation(pendente);
  apiLeitura.obterAlertas.mockImplementation(pendente);
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("casca do app", () => {
  it("menu_leva_as_paginas", async () => {
    renderizar();
    const menu = await screen.findByRole("navigation", { name: "Principal" });
    const itens = within(menu)
      .getAllByRole("link")
      .map((l) => l.textContent);
    expect(itens).toEqual([
      "Início",
      "Contas",
      "Lançamentos",
      "Cartões",
      "Gasto do mês",
      "Reserva",
      "Sobra (R2)",
      "Alertas",
    ]);

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

  it("inicio_busca_os_numeros_na_api", async () => {
    renderizar();
    expect(await screen.findByRole("heading", { name: "Início" })).toBeInTheDocument();
    expect(apiLeitura.obterR2).toHaveBeenCalled();
    expect(apiLeitura.obterAlertas).toHaveBeenCalled();
  });
});
