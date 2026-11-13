import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as sessao from "../api/sessao";
import * as vigencias from "../api/vigencias";

vi.mock("../api/sessao");
vi.mock("../api/vigencias");
const apiSessao = vi.mocked(sessao);
const api = vi.mocked(vigencias);

function pagina(rota = "/parametros") {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  api.listarParametrosReserva.mockResolvedValue({
    tipo: "ok",
    dados: [
      { vigente_desde: "2026-01-01", meses: 3, gasto_essencial: "2000.00", data_alvo: null },
      { vigente_desde: "2026-06-01", meses: 6, gasto_essencial: "3500.50", data_alvo: "2027-12-31" },
    ],
  });
  api.listarHorizontes.mockResolvedValue({
    tipo: "ok",
    dados: [
      { vigente_desde: "2026-01-01", dias: 10 },
      { vigente_desde: "2026-09-01", dias: 15 },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("página de parâmetros", () => {
  it("mostra_o_historico_de_vigencias_e_parte_da_ultima", async () => {
    pagina();
    const reserva = await screen.findByRole("list", { name: "Histórico da meta da reserva" });
    const itens = within(reserva).getAllByRole("listitem");
    // Mais recente primeiro; valores como a API mandou, só formatados.
    expect(itens[0]).toHaveTextContent("A partir de 01/06/2026");
    expect(itens[0]).toHaveTextContent("6 meses");
    expect(itens[0]).toHaveTextContent("R$ 3.500,50");
    expect(itens[0]).toHaveTextContent("alvo em 31/12/2027");
    expect(itens[1]).toHaveTextContent("sem data-alvo");
    const formReserva = screen.getByRole("form", { name: "Meta da reserva" });
    expect(within(formReserva).getByLabelText("Meta (meses de gasto essencial)")).toHaveValue("6");
    expect(within(formReserva).getByLabelText("Gasto essencial por mês (R$)")).toHaveValue("3500,50");

    const horizontes = screen.getByRole("list", { name: "Histórico do horizonte do R2" });
    expect(within(horizontes).getAllByRole("listitem")[0]).toHaveTextContent(
      "15 dias, a partir de 01/09/2026",
    );
  });

  it("grava_a_meta_da_reserva_com_vigencia", async () => {
    const usuario = userEvent.setup();
    api.gravarParametrosReserva.mockResolvedValue({
      tipo: "ok",
      dados: { vigente_desde: "2026-11-01", meses: 8, gasto_essencial: "4000.00", data_alvo: null },
    });
    pagina();
    const form = await screen.findByRole("form", { name: "Meta da reserva" });
    const meses = within(form).getByLabelText("Meta (meses de gasto essencial)");

    // Fora de 1 a 120: a tela explica, com o foco no campo, e não envia.
    await usuario.clear(meses);
    await usuario.type(meses, "121");
    await usuario.click(within(form).getByRole("button", { name: "Salvar meta da reserva" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("de 1 a 120");
    expect(meses).toHaveFocus();
    expect(api.gravarParametrosReserva).not.toHaveBeenCalled();

    await usuario.clear(meses);
    await usuario.type(meses, "8");
    const gasto = within(form).getByLabelText("Gasto essencial por mês (R$)");
    await usuario.clear(gasto);
    await usuario.type(gasto, "4.000,00");
    await usuario.clear(within(form).getByLabelText("Data-alvo (opcional)"));
    fireEvent.change(within(form).getByLabelText("Vigente desde"), { target: { value: "2026-11-01" } });
    await usuario.click(within(form).getByRole("button", { name: "Salvar meta da reserva" }));
    await vi.waitFor(() =>
      expect(api.gravarParametrosReserva).toHaveBeenCalledWith({
        meses: 8,
        gastoEssencial: "4000.00",
        dataAlvo: null,
        vigenteDesde: "2026-11-01",
      }),
    );
    expect(await within(form).findByRole("status")).toHaveTextContent("Meta salva a partir de 01/11/2026");
    // O histórico é buscado de novo no servidor.
    await vi.waitFor(() => expect(api.listarParametrosReserva).toHaveBeenCalledTimes(2));
  });

  it("grava_o_horizonte_e_mostra_a_recusa_do_banco", async () => {
    const usuario = userEvent.setup();
    api.gravarHorizonte
      .mockResolvedValueOnce({ tipo: "invalido", mensagem: "horizonte fora do intervalo permitido" })
      .mockResolvedValueOnce({ tipo: "ok", dados: { vigente_desde: "2026-11-01", dias: 30 } });
    pagina();
    const form = await screen.findByRole("form", { name: "Horizonte do R2" });
    const dias = within(form).getByLabelText("Dias à frente");
    fireEvent.change(within(form).getByLabelText("Vigente desde"), { target: { value: "2026-11-01" } });

    await usuario.clear(dias);
    await usuario.type(dias, "91");
    await usuario.click(within(form).getByRole("button", { name: "Salvar horizonte" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("de 1 a 90 dias");
    expect(api.gravarHorizonte).not.toHaveBeenCalled();

    await usuario.clear(dias);
    await usuario.type(dias, "30");
    await usuario.click(within(form).getByRole("button", { name: "Salvar horizonte" }));
    await vi.waitFor(() =>
      expect(within(form).getByRole("alert")).toHaveTextContent("horizonte fora do intervalo permitido"),
    );
    expect(api.gravarHorizonte).toHaveBeenLastCalledWith(30, "2026-11-01");

    await usuario.click(within(form).getByRole("button", { name: "Salvar horizonte" }));
    expect(await within(form).findByRole("status")).toHaveTextContent("30 dias");
  });

  it("estados_vazio_erro_e_sessao", async () => {
    const usuario = userEvent.setup();
    api.listarParametrosReserva.mockResolvedValueOnce({ tipo: "erro" });
    api.listarHorizontes.mockResolvedValueOnce({ tipo: "ok", dados: [] });
    pagina();
    expect(await screen.findByText("Não foi possível carregar a meta da reserva.")).toBeInTheDocument();
    expect(await screen.findByText("Nenhum horizonte cadastrado ainda.")).toBeInTheDocument();
    api.listarParametrosReserva.mockResolvedValueOnce({ tipo: "ok", dados: [] });
    await usuario.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("A reserva ainda não está configurada.")).toBeInTheDocument();
  });

  it("sessao_vencida_volta_ao_login", async () => {
    api.listarHorizontes.mockResolvedValue({ tipo: "sessao_expirada" });
    pagina();
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});
