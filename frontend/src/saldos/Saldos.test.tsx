import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as contas from "../api/contas";
import type { SaldoSaida } from "../api/gerado";
import * as saldos from "../api/saldos";
import * as sessao from "../api/sessao";

// A fronteira com o servidor é a única coisa simulada; o App e as telas rodam de verdade.
vi.mock("../api/sessao");
vi.mock("../api/saldos");
vi.mock("../api/contas");
const apiSessao = vi.mocked(sessao);
const apiSaldos = vi.mocked(saldos);
const apiContas = vi.mocked(contas);

function conta(parcial: Partial<SaldoSaida> & Pick<SaldoSaida, "conta_id" | "nome">): SaldoSaida {
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

/** O saldo exibido de uma conta (o texto para leitor de tela nomeia a conta). */
async function saldoDe(nome: string): Promise<HTMLElement> {
  const rotulo = await screen.findByText(`Saldo de ${nome}:`);
  const saldo = rotulo.parentElement;
  if (saldo === null) throw new Error("saldo sem elemento pai");
  return saldo;
}

function renderizar() {
  return render(
    <MemoryRouter initialEntries={["/contas"]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiSaldos.listarSaldos.mockResolvedValue({ tipo: "ok", saldos: [] });
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("tela de saldos", () => {
  it("mostra_saldo_da_api", async () => {
    // Valores que um `number` estragaria: acima de 2^53 e centavos que não fecham em binário.
    // O esperado é o texto da API só reagrupado; a tela não soma nem arredonda.
    apiSaldos.listarSaldos.mockResolvedValue({
      tipo: "ok",
      saldos: [
        conta({
          conta_id: 1,
          nome: "Conta principal",
          saldo: "12345678901234567.89",
          snapshot_data: "2026-11-01",
          snapshot_valor: "1000.10",
        }),
        conta({
          conta_id: 2,
          nome: "Vale",
          conta_beneficio: true,
          tipo: "beneficio",
          saldo: "-0.30",
        }),
      ],
    });
    renderizar();

    expect(await saldoDe("Conta principal")).toHaveTextContent(
      "Saldo de Conta principal: R$ 12.345.678.901.234.567,89",
    );
    expect(await saldoDe("Vale")).toHaveTextContent("Saldo de Vale: -R$ 0,30");
    expect(
      screen.getByText("Último saldo informado: R$ 1.000,10 em 01/11/2026."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Nenhum saldo informado ainda/)).toBeInTheDocument();
    expect(screen.getAllByText("Benefício")).toHaveLength(1);
    // Só a lista da API: nenhuma outra chamada que pudesse trazer um número calculado.
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(1);
  });

  it("mostra_carregando_ate_a_api_responder", async () => {
    let responder: (r: saldos.ResultadoSaldos) => void = () => {};
    apiSaldos.listarSaldos.mockReturnValue(
      new Promise((r) => {
        responder = r;
      }),
    );
    renderizar();
    expect(await screen.findByText("Carregando saldos…")).toBeInTheDocument();

    responder({ tipo: "ok", saldos: [conta({ conta_id: 1, nome: "A", saldo: "1.00" })] });
    expect(await saldoDe("A")).toHaveTextContent("R$ 1,00");
    expect(screen.queryByText("Carregando saldos…")).not.toBeInTheDocument();
  });

  it("falha_ao_atualizar_mantem_a_lista", async () => {
    apiSaldos.listarSaldos.mockResolvedValueOnce({
      tipo: "ok",
      saldos: [conta({ conta_id: 1, nome: "A", saldo: "1.00" })],
    });
    apiContas.criarConta.mockResolvedValue({
      tipo: "ok",
      conta: {
        conta_id: 2,
        nome: "B",
        conta_beneficio: false,
        tipo: "corrente",
        conta_mae_id: null,
        versao: 1,
      },
    });
    renderizar();
    const form = await screen.findByRole("form", { name: "Nova conta" });
    apiSaldos.listarSaldos.mockResolvedValueOnce({ tipo: "erro" });

    const usuario = userEvent.setup();
    await usuario.type(within(form).getByLabelText("Nome da conta"), "B");
    await usuario.click(within(form).getByRole("button", { name: "Criar conta" }));

    expect(await screen.findByText(/não deu para atualizar a lista/)).toBeInTheDocument();
    expect(await saldoDe("A")).toHaveTextContent("R$ 1,00");
    expect(within(form).getByRole("status")).toHaveTextContent("Conta “B” criada");
  });

  it("mostra_estado_vazio", async () => {
    renderizar();
    expect(await screen.findByText("Nenhuma conta ainda")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Nova conta" })).toBeInTheDocument();
  });

  it("mostra_erro_e_tenta_de_novo", async () => {
    apiSaldos.listarSaldos.mockResolvedValueOnce({ tipo: "erro" });
    renderizar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar");

    apiSaldos.listarSaldos.mockResolvedValueOnce({
      tipo: "ok",
      saldos: [conta({ conta_id: 1, nome: "Poupança", saldo: "10.00" })],
    });
    await userEvent.setup().click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Poupança")).toBeInTheDocument();
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(2);
  });

  it("sessao_expirada_volta_ao_login", async () => {
    apiSaldos.listarSaldos.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar();
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});

describe("nova conta", () => {
  it("cria_conta_e_recarrega_a_lista", async () => {
    apiContas.criarConta.mockResolvedValue({
      tipo: "ok",
      conta: {
        conta_id: 7,
        nome: "Vale-refeição",
        conta_beneficio: true,
        tipo: "beneficio",
        conta_mae_id: null,
        versao: 1,
      },
    });
    renderizar();
    const form = await screen.findByRole("form", { name: "Nova conta" });
    apiSaldos.listarSaldos.mockResolvedValue({
      tipo: "ok",
      saldos: [
        conta({
          conta_id: 7,
          nome: "Vale-refeição",
          conta_beneficio: true,
          tipo: "beneficio",
        }),
      ],
    });

    const usuario = userEvent.setup();
    await usuario.type(within(form).getByLabelText("Nome da conta"), "Vale-refeição");
    await usuario.selectOptions(within(form).getByLabelText("Tipo"), "beneficio");
    await usuario.click(within(form).getByRole("button", { name: "Criar conta" }));

    expect(apiContas.criarConta).toHaveBeenCalledWith("Vale-refeição", "beneficio", null);
    expect(await saldoDe("Vale-refeição")).toHaveTextContent("R$ 0,00");
    expect(within(form).getByRole("status")).toHaveTextContent("Conta “Vale-refeição” criada");
    expect(within(form).getByLabelText("Nome da conta")).toHaveValue("");
  });

  it("avisa_nome_repetido_sem_recarregar", async () => {
    apiContas.criarConta.mockResolvedValue({ tipo: "nome_repetido" });
    renderizar();
    const form = await screen.findByRole("form", { name: "Nova conta" });

    const usuario = userEvent.setup();
    await usuario.type(within(form).getByLabelText("Nome da conta"), "Repetida");
    await usuario.click(within(form).getByRole("button", { name: "Criar conta" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent("Já existe uma conta");
    expect(within(form).getByLabelText("Nome da conta")).toHaveValue("Repetida");
    expect(apiSaldos.listarSaldos).toHaveBeenCalledTimes(1);
  });

  it("mensagens_de_nome_invalido_e_falha_de_rede", async () => {
    apiContas.criarConta
      .mockResolvedValueOnce({ tipo: "invalido", mensagem: null })
      .mockResolvedValueOnce({ tipo: "erro" });
    renderizar();
    const form = await screen.findByRole("form", { name: "Nova conta" });
    const usuario = userEvent.setup();
    await usuario.type(within(form).getByLabelText("Nome da conta"), "   ");
    await usuario.click(within(form).getByRole("button", { name: "Criar conta" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("não pode ficar vazio");

    await usuario.click(within(form).getByRole("button", { name: "Criar conta" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent(
      "Não foi possível falar com o servidor",
    );
  });

  it("sessao_expirada_ao_criar_volta_ao_login", async () => {
    apiContas.criarConta.mockResolvedValue({ tipo: "sessao_expirada" });
    renderizar();
    const form = await screen.findByRole("form", { name: "Nova conta" });

    const usuario = userEvent.setup();
    await usuario.type(within(form).getByLabelText("Nome da conta"), "Qualquer");
    await usuario.click(within(form).getByRole("button", { name: "Criar conta" }));

    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });
});
