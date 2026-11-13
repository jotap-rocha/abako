import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import type { LancamentoSaida } from "../api/gerado";
import * as api from "../api/lancamentos";
import * as leitura from "../api/leitura";
import * as saldos from "../api/saldos";
import * as sessao from "../api/sessao";
import * as vale from "../api/vale";
import { CONTAS } from "./contasDeTeste";

vi.mock("../api/sessao");
vi.mock("../api/saldos");
vi.mock("../api/lancamentos");
vi.mock("../api/leitura");
vi.mock("../api/vale");
const apiSessao = vi.mocked(sessao);
const apiSaldos = vi.mocked(saldos);
const apiLanc = vi.mocked(api);
const apiLeitura = vi.mocked(leitura);
const apiVale = vi.mocked(vale);

const L1: LancamentoSaida = {
  transacao_id: 10,
  versao: 2,
  tipo: "debito",
  data: "2026-11-04",
  valor: "12345678901234567.89",
  conta_id: 1,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: "mercado",
};

function renderizar() {
  return render(
    <MemoryRouter initialEntries={["/lancamentos"]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  apiVale.obterParametroVale.mockResolvedValue({ tipo: "ok", dados: null });
  apiSaldos.listarSaldos.mockResolvedValue({ tipo: "ok", saldos: CONTAS });
  apiLeitura.listarPessoas.mockResolvedValue({ tipo: "ok", dados: [] });
  apiLanc.listarLancamentos.mockResolvedValue({ tipo: "ok", lancamentos: [L1] });
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("página de lançamentos", () => {
  it("nome_da_pessoa_neutro_se_a_lista_de_pessoas_nao_veio", async () => {
    const compra = { ...L1, tipo: "credito", pessoa_id: 9, descricao: null };
    apiLanc.listarLancamentos.mockResolvedValue({ tipo: "ok", lancamentos: [compra] });
    // Pessoas não carregaram: não dá para afirmar que a pessoa foi removida.
    apiLeitura.listarPessoas.mockResolvedValue({ tipo: "erro" });
    const { unmount } = renderizar();
    const lista = await screen.findByRole("list", { name: "Lançamentos" });
    expect(lista).toHaveTextContent("compra de pessoa");
    expect(lista).not.toHaveTextContent("pessoa removida");
    unmount();

    // Com a lista de pessoas carregada e sem aquela pessoa, aí sim ela foi removida.
    apiLeitura.listarPessoas.mockResolvedValue({ tipo: "ok", dados: [] });
    renderizar();
    expect(await screen.findByRole("list", { name: "Lançamentos" })).toHaveTextContent(
      "compra de pessoa removida",
    );
  });

  it("mostra_estado_vazio_e_erro", async () => {
    apiLanc.listarLancamentos.mockResolvedValueOnce({ tipo: "ok", lancamentos: [] });
    renderizar();
    expect(await screen.findByText("Nenhum lançamento ainda")).toBeInTheDocument();
  });

  it("mostra_erro_e_tenta_de_novo", async () => {
    const usuario = userEvent.setup();
    apiLanc.listarLancamentos.mockResolvedValueOnce({ tipo: "erro" });
    renderizar();
    expect(await screen.findByText("Não foi possível carregar os lançamentos.")).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("mercado", { exact: false })).toBeInTheDocument();
  });

  it("edita_e_exclui_com_versao", async () => {
    const usuario = userEvent.setup();
    apiLanc.editarLancamento.mockResolvedValueOnce({
      tipo: "ok",
      lancamento: { ...L1, versao: 3, valor: "20.00" },
      repetido: false,
    });
    apiLanc.excluirLancamento
      .mockResolvedValueOnce({ tipo: "desatualizado" })
      .mockResolvedValueOnce({ tipo: "ok" });
    renderizar();

    // O valor aparece como o servidor mandou, só formatado (acima de 2^53, sem perder dígitos).
    const lista = await screen.findByRole("list", { name: "Lançamentos" });
    expect(lista).toHaveTextContent("R$ 12.345.678.901.234.567,89");

    // Editar leva a versão lida (2) e busca a lista de novo.
    await usuario.click(within(lista).getByRole("button", { name: /^Editar lançamento/ }));
    const form = await screen.findByRole("form", { name: "Editar lançamento" });
    const valor = within(form).getByLabelText("Valor (R$)");
    await usuario.clear(valor);
    await usuario.type(valor, "20,00");
    await usuario.click(within(form).getByRole("button", { name: "Salvar alteração" }));
    await vi.waitFor(() => expect(apiLanc.editarLancamento).toHaveBeenCalledTimes(1));
    expect(apiLanc.editarLancamento).toHaveBeenCalledWith(10, 2, expect.objectContaining({ valor: "20.00" }));
    await vi.waitFor(() => expect(apiLanc.listarLancamentos).toHaveBeenCalledTimes(2));

    // Excluir pede confirmação e leva a versão; 409 explica e atualiza sem sobrescrever.
    await usuario.click(screen.getAllByRole("button", { name: /^Excluir lançamento/ })[0]!);
    await usuario.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    expect(await screen.findByText(/mudou em outra aba/)).toBeInTheDocument();
    expect(apiLanc.excluirLancamento).toHaveBeenLastCalledWith(10, 2);

    await usuario.click(screen.getAllByRole("button", { name: /^Excluir lançamento/ })[0]!);
    await usuario.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    expect(await screen.findByText(/Lançamento excluído/)).toBeInTheDocument();
    expect(apiLanc.excluirLancamento).toHaveBeenCalledTimes(2);
  });

  it("edicao_usa_a_versao_que_o_usuario_viu", async () => {
    const usuario = userEvent.setup();
    apiLanc.editarLancamento.mockResolvedValueOnce({ tipo: "desatualizado" });
    apiLanc.listarLancamentos.mockResolvedValueOnce({
      tipo: "ok",
      lancamentos: [{ ...L1, valor: "12.00" }],
    });
    renderizar();
    const lista = await screen.findByRole("list", { name: "Lançamentos" });
    await usuario.click(within(lista).getByRole("button", { name: /^Editar lançamento/ }));
    const form = await screen.findByRole("form", { name: "Editar lançamento" });

    // Outra aba editou o lançamento (v3) e a lista foi atualizada com a edição aberta.
    apiLanc.listarLancamentos.mockResolvedValue({
      tipo: "ok",
      lancamentos: [{ ...L1, versao: 3, valor: "99.00" }],
    });
    apiLanc.criarLancamento.mockResolvedValueOnce({
      tipo: "ok",
      lancamento: { ...L1, transacao_id: 11 },
      repetido: false,
    });
    const novo = screen.getByRole("form", { name: "Novo lançamento" });
    await usuario.type(within(novo).getByLabelText("Valor (R$)"), "1,00");
    await usuario.click(within(novo).getByRole("button", { name: "Salvar lançamento" }));
    await vi.waitFor(() => expect(apiLanc.listarLancamentos).toHaveBeenCalledTimes(2));

    // Salvar a edição leva a versão lida (2), não a da lista nova: o servidor responde 409.
    await usuario.click(within(form).getByRole("button", { name: "Salvar alteração" }));
    await vi.waitFor(() => expect(apiLanc.editarLancamento).toHaveBeenCalledTimes(1));
    expect(apiLanc.editarLancamento).toHaveBeenCalledWith(10, 2, expect.anything());
    expect(await screen.findByText(/mudou em outra aba/)).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Editar lançamento" })).not.toBeInTheDocument();
  });

  it("foco_vai_e_volta_na_edicao_e_na_exclusao", async () => {
    const usuario = userEvent.setup();
    apiLanc.listarLancamentos.mockResolvedValue({
      tipo: "ok",
      lancamentos: [{ ...L1, valor: "12.00" }],
    });
    renderizar();
    const lista = await screen.findByRole("list", { name: "Lançamentos" });

    await usuario.click(within(lista).getByRole("button", { name: /^Editar lançamento/ }));
    const form = await screen.findByRole("form", { name: "Editar lançamento" });
    await vi.waitFor(() => expect(within(form).getByLabelText("Tipo")).toHaveFocus());
    await usuario.click(within(form).getByRole("button", { name: "Fechar" }));
    await vi.waitFor(() =>
      expect(within(lista).getByRole("button", { name: /^Editar lançamento/ })).toHaveFocus(),
    );

    await usuario.click(within(lista).getByRole("button", { name: /^Excluir lançamento/ }));
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus());
    await usuario.click(screen.getByRole("button", { name: "Cancelar" }));
    await vi.waitFor(() =>
      expect(within(lista).getByRole("button", { name: /^Excluir lançamento/ })).toHaveFocus(),
    );
  });
});
