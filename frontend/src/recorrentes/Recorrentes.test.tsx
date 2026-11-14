import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import type { ContaSaida, LancamentoSaida, OcorrenciaSaida, RecorrenteSaida } from "../api/gerado";
import * as apiLancamentos from "../api/lancamentos";
import * as apiLeitura from "../api/leitura";
import * as apiRecorrentes from "../api/recorrentes";
import * as sessao from "../api/sessao";
import { mesAtual } from "../datas";
import { R2 } from "../leitura/dadosDeTeste";

vi.mock("../api/lancamentos");
vi.mock("../api/leitura");
vi.mock("../api/recorrentes");
vi.mock("../api/sessao");
const lanc = vi.mocked(apiLancamentos);
const leitura = vi.mocked(apiLeitura);
const api = vi.mocked(apiRecorrentes);
const apiSessao = vi.mocked(sessao);

const MES = mesAtual();

const CORRENTE: ContaSaida = {
  conta_id: 1,
  nome: "Conta principal",
  tipo: "corrente",
  conta_beneficio: false,
  conta_mae_id: null,
  linha_credito_id: null,
  versao: 1,
};
const VALE: ContaSaida = { ...CORRENTE, conta_id: 3, nome: "Vale", tipo: "beneficio", conta_beneficio: true };

const ALUGUEL: RecorrenteSaida = {
  recorrente_id: 3,
  nome: "Aluguel",
  tipo: "fixo",
  valor: "1500.00",
  dia: 5,
  conta_id: 1,
  mes_inicio: "2026-01",
  mes_fim: null,
  versao: 2,
};

const OCORRENCIA: OcorrenciaSaida = {
  recorrente_id: 3,
  nome: "Aluguel",
  tipo: "fixo",
  conta_id: 1,
  mes: MES,
  data: `${MES}-05`,
  valor_esperado: "1500.00",
  valor: "1500.00",
  transacao_id: null,
  vinculada: false,
};

const PAGAMENTO: LancamentoSaida = {
  transacao_id: 55,
  versao: 1,
  tipo: "debito",
  data: `${MES}-06`,
  valor: "1480.00",
  conta_id: 1,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: "aluguel pago",
};

const R2_COM_VENCIDA = {
  ...R2,
  vencidas: 1,
  itens: [
    {
      grupo: "vencida",
      tipo: "fixo",
      recorrente_id: 3,
      conta_id: 1,
      competencia: null,
      data: `${MES}-05`,
      valor: "1500.00",
      bruto: null,
      pago: null,
      parcial: null,
    },
  ],
};

function pagina() {
  return render(
    <MemoryRouter initialEntries={["/recorrentes"]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiSessao.recuperarSessao.mockResolvedValue(true);
  leitura.listarContas.mockResolvedValue({ tipo: "ok", dados: [CORRENTE, VALE] });
  leitura.listarRecorrentes.mockResolvedValue({ tipo: "ok", dados: [ALUGUEL] });
  leitura.obterR2.mockResolvedValue({ tipo: "ok", dados: R2_COM_VENCIDA });
  lanc.listarLancamentos.mockResolvedValue({ tipo: "ok", lancamentos: [PAGAMENTO] });
  api.listarOcorrencias.mockResolvedValue({ tipo: "ok", dados: [OCORRENCIA] });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("página de recorrentes", () => {
  it("mostra_cadastro_ocorrencias_e_vencidas", async () => {
    pagina();
    const cadastro = await screen.findByRole("list", { name: "Recorrentes" });
    // O valor é o texto da API, só formatado.
    expect(cadastro).toHaveTextContent("R$ 1.500,00");
    expect(cadastro).toHaveTextContent("Todo dia 5");
    const ocorrencias = await screen.findByRole("list", { name: "Ocorrências" });
    expect(ocorrencias).toHaveTextContent("vencida");
    expect(ocorrencias).toHaveTextContent("esperado R$ 1.500,00");
    expect(
      screen.getByText(/Há 1 ocorrência\(s\) vencida\(s\) sem vínculo/),
    ).toBeInTheDocument();
  });

  it("avisa_quando_a_lista_de_transacoes_chega_ao_teto", async () => {
    const muitos = Array.from({ length: 200 }, (_, i) => ({ ...PAGAMENTO, transacao_id: 1000 + i }));
    lanc.listarLancamentos.mockResolvedValue({ tipo: "ok", lancamentos: muitos });
    pagina();
    expect(await screen.findByRole("note")).toHaveTextContent("limite de 200 lançamentos");
    expect(screen.getByRole("note")).toHaveTextContent("mais antigos");
    cleanup();

    // Abaixo do teto, nenhum aviso.
    lanc.listarLancamentos.mockResolvedValue({ tipo: "ok", lancamentos: muitos.slice(0, 199) });
    pagina();
    await screen.findByRole("list", { name: "Ocorrências" });
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("estados_vazio_erro_e_sessao", async () => {
    const usuario = userEvent.setup();
    leitura.listarRecorrentes.mockResolvedValueOnce({ tipo: "erro" });
    api.listarOcorrencias.mockResolvedValue({ tipo: "ok", dados: [] });
    pagina();
    expect(await screen.findByText("Não foi possível carregar os recorrentes.")).toBeInTheDocument();
    leitura.listarRecorrentes.mockResolvedValueOnce({ tipo: "ok", dados: [] });
    await usuario.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByText("Nenhum recorrente ainda")).toBeInTheDocument();
    expect(await screen.findByText("Nenhuma ocorrência neste mês")).toBeInTheDocument();
  });

  it("sessao_vencida_volta_ao_login", async () => {
    api.listarOcorrencias.mockResolvedValue({ tipo: "sessao_expirada" });
    pagina();
    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
  });

  it("vincula_e_desvincula_e_mostra_a_recusa", async () => {
    const usuario = userEvent.setup();
    api.vincularOcorrencia
      .mockResolvedValueOnce({ tipo: "conflito" })
      .mockResolvedValueOnce({
        tipo: "ok",
        dados: { ...OCORRENCIA, vinculada: true, transacao_id: 55, valor: "1480.00" },
      });
    api.desvincularOcorrencia.mockResolvedValue({ tipo: "ok", dados: OCORRENCIA });
    pagina();
    await screen.findByRole("list", { name: "Ocorrências" });

    await usuario.click(screen.getByRole("button", { name: "Vincular Aluguel" }));
    const grupo = screen.getByRole("group", { name: "Vincular Aluguel" });
    // Sem escolher, não envia.
    await usuario.click(within(grupo).getByRole("button", { name: "Vincular" }));
    expect(await within(grupo).findByRole("alert")).toHaveTextContent("Escolha a transação");
    expect(api.vincularOcorrencia).not.toHaveBeenCalled();

    await usuario.selectOptions(within(grupo).getByLabelText("Transação"), "55");
    await usuario.click(within(grupo).getByRole("button", { name: "Vincular" }));
    expect(await within(grupo).findByText(/já está ligada a outra ocorrência/)).toBeInTheDocument();
    expect(api.vincularOcorrencia).toHaveBeenLastCalledWith(3, MES, 55);

    // A segunda tentativa passa e a lista de ocorrências é buscada de novo.
    api.listarOcorrencias.mockResolvedValue({
      tipo: "ok",
      dados: [{ ...OCORRENCIA, vinculada: true, transacao_id: 55, valor: "1480.00" }],
    });
    await usuario.click(within(grupo).getByRole("button", { name: "Vincular" }));
    const desvincular = await screen.findByRole("button", { name: "Desvincular Aluguel" });
    expect(screen.getByRole("list", { name: "Ocorrências" })).toHaveTextContent("R$ 1.480,00");
    await usuario.click(desvincular);
    await vi.waitFor(() => expect(api.desvincularOcorrencia).toHaveBeenCalledWith(3, MES));
  });

  it("cria_recorrente_com_validacao_e_recusa_do_banco", async () => {
    const usuario = userEvent.setup();
    api.criarRecorrente
      .mockResolvedValueOnce({ tipo: "invalido", mensagem: "o dia 31 não cabe neste mês" })
      .mockResolvedValueOnce({ tipo: "ok", dados: { ...ALUGUEL, recorrente_id: 4, nome: "Internet" } });
    pagina();
    const form = await screen.findByRole("form", { name: "Novo recorrente" });
    const enviar = () => usuario.click(within(form).getByRole("button", { name: "Cadastrar recorrente" }));
    const nome = within(form).getByLabelText("Nome");

    // Caractere de controle no nome: recusado na tela, com o foco no campo.
    fireEvent.change(nome, { target: { value: "Inter\tnet" } });
    await usuario.type(within(form).getByLabelText("Valor esperado (R$)"), "99,90");
    await usuario.type(within(form).getByLabelText("Dia do mês"), "5");
    await enviar();
    expect(await within(form).findByRole("alert")).toHaveTextContent("caracteres de controle");
    expect(nome).toHaveFocus();
    expect(nome).toHaveAttribute("aria-invalid", "true");
    expect(api.criarRecorrente).not.toHaveBeenCalled();

    // Dia fora de 1 a 31.
    await usuario.clear(nome);
    await usuario.type(nome, "Internet");
    await usuario.clear(within(form).getByLabelText("Dia do mês"));
    await usuario.type(within(form).getByLabelText("Dia do mês"), "32");
    await enviar();
    await vi.waitFor(() => expect(within(form).getByRole("alert")).toHaveTextContent("de 1 a 31"));

    // A conta de benefício não é opção; a recusa do banco aparece literal.
    expect(within(form).getByLabelText("Conta corrente")).not.toHaveTextContent("Vale");
    await usuario.clear(within(form).getByLabelText("Dia do mês"));
    await usuario.type(within(form).getByLabelText("Dia do mês"), "31");
    await enviar();
    await vi.waitFor(() => expect(within(form).getByRole("alert")).toHaveTextContent("o dia 31 não cabe"));
    expect(api.criarRecorrente).toHaveBeenLastCalledWith({
      nome: "Internet",
      tipo: "fixo",
      valor: "99.90",
      dia: 31,
      conta_id: 1,
      mes_inicio: MES,
      mes_fim: null,
    });

    await enviar();
    expect(await within(form).findByText("Recorrente cadastrado.")).toBeInTheDocument();
  });

  it("edita_com_a_versao_lida_e_explica_o_409", async () => {
    const usuario = userEvent.setup();
    api.editarRecorrente.mockResolvedValue({ tipo: "desatualizado" });
    pagina();
    const cadastro = await screen.findByRole("list", { name: "Recorrentes" });
    await usuario.click(within(cadastro).getByRole("button", { name: "Editar Aluguel" }));
    const form = await screen.findByRole("form", { name: "Editar recorrente" });
    await usuario.click(within(form).getByRole("button", { name: "Salvar alteração" }));
    await vi.waitFor(() =>
      expect(api.editarRecorrente).toHaveBeenCalledWith(
        3,
        2,
        expect.objectContaining({ nome: "Aluguel", valor: "1500.00", dia: 5 }),
      ),
    );
    // Versão antiga: a tela explica e fecha a edição (a lista é buscada de novo).
    expect(await screen.findByText(/mudou desde que você o abriu/)).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(screen.queryByRole("form", { name: "Editar recorrente" })).not.toBeInTheDocument(),
    );
  });

  it("exclui_com_confirmacao_e_versao", async () => {
    const usuario = userEvent.setup();
    api.excluirRecorrente.mockResolvedValue({ tipo: "ok", dados: null });
    pagina();
    const cadastro = await screen.findByRole("list", { name: "Recorrentes" });
    await usuario.click(within(cadastro).getByRole("button", { name: "Excluir Aluguel" }));
    expect(api.excluirRecorrente).not.toHaveBeenCalled();
    await usuario.click(screen.getByRole("button", { name: "Confirmar exclusão" }));
    await vi.waitFor(() => expect(api.excluirRecorrente).toHaveBeenCalledWith(3, 2));
    expect(await screen.findByText(/Recorrente excluído/)).toBeInTheDocument();
  });
});
