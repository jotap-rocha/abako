import { render, screen } from "@testing-library/react";
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

function renderizar() {
  return render(
    <MemoryRouter initialEntries={["/alertas"]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("alertas (R4)", () => {
  it("lista_divergencias_da_api", async () => {
    apiSaldos.listarDivergencias.mockResolvedValue({
      tipo: "ok",
      divergencias: [
        {
          conta_id: 1,
          conta_nome: "Conta principal",
          data_snapshot: "2026-11-03",
          valor_snapshot: "900.00",
          saldo_derivado: "950.00",
          divergencia: "50.00",
        },
      ],
    });
    renderizar();

    const lista = await screen.findByRole("list", { name: "Saldos divergentes" });
    expect(lista).toHaveTextContent("Conta principal");
    expect(lista).toHaveTextContent("Diferença: R$ 50,00");
    expect(lista).toHaveTextContent(
      "Em 03/11/2026, o abako calculou R$ 950,00 e você informou R$ 900,00.",
    );
    // O sentido da diferença é explicado em palavras (a conta é do servidor, ADR 041).
    expect(screen.getByText(/calculado menos o informado/)).toBeInTheDocument();
  });

  it("sem_divergencia_mostra_vazio", async () => {
    apiSaldos.listarDivergencias.mockResolvedValue({ tipo: "ok", divergencias: [] });
    renderizar();
    expect(await screen.findByText("Nenhuma divergência")).toBeInTheDocument();
  });

  it("erro_tenta_de_novo_e_sessao_expirada", async () => {
    apiSaldos.listarDivergencias
      .mockResolvedValueOnce({ tipo: "erro" })
      .mockResolvedValueOnce({ tipo: "ok", divergencias: [] });
    const { unmount } = renderizar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar");
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Nenhuma divergência")).toBeInTheDocument();
    expect(apiSaldos.listarDivergencias).toHaveBeenCalledTimes(2);
    unmount();

    apiSaldos.listarDivergencias.mockResolvedValueOnce({ tipo: "sessao_expirada" });
    renderizar();
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});
