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
import { CONTAS } from "../lancamento/contasDeTeste";
import { Formulario } from "../lancamento/Formulario";

vi.mock("../api/lancamentos");
vi.mock("../api/leitura");
vi.mock("../api/saldos");
vi.mock("../api/sessao");
vi.mock("../api/vale");
const apiLanc = vi.mocked(api);

// A conta 3 de CONTAS ("Vale") é o VR nestes testes.
const VR = 3;

const SALVO: LancamentoSaida = {
  transacao_id: 10,
  versao: 1,
  tipo: "debito",
  data: "2026-11-04",
  valor: "50.00",
  conta_id: VR,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: null,
  bolso: "trabalho",
};

afterEach(() => {
  vi.resetAllMocks();
});

describe("bolso no formulário de lançamento", () => {
  function renderizar(contaVrId: number | null) {
    return render(
      <Formulario
        contas={CONTAS}
        contaVrId={contaVrId}
        aoSalvar={vi.fn()}
        aoSessaoExpirar={vi.fn()}
      />,
    );
  }

  it("bolso_obrigatorio_no_vr_e_ausente_fora_dele", async () => {
    const usuario = userEvent.setup();
    apiLanc.criarLancamento.mockResolvedValue({ tipo: "ok", lancamento: SALVO, repetido: false });
    renderizar(VR);
    const conta = screen.getByLabelText("Conta de onde saiu");

    // Conta corrente: sem campo e o envio vai sem bolso.
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
    await usuario.selectOptions(conta, "Banco A");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "10,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(apiLanc.criarLancamento.mock.calls[0]?.[1]).not.toHaveProperty("bolso");

    // Conta do VR: campo obrigatório, com "pessoal" como padrão.
    await usuario.selectOptions(conta, "Vale");
    const bolso = screen.getByLabelText("Bolso");
    expect(bolso).toBeRequired();
    expect(bolso).toHaveValue("pessoal");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "20,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(apiLanc.criarLancamento.mock.calls[1]?.[1]).toMatchObject({ bolso: "pessoal" });

    // Escolhendo trabalho, vai trabalho.
    await usuario.selectOptions(screen.getByLabelText("Bolso"), "trabalho");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "5,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(apiLanc.criarLancamento.mock.calls[2]?.[1]).toMatchObject({ bolso: "trabalho" });
  });

  it("sem_vr_marcado_nao_ha_campo_de_bolso", async () => {
    const usuario = userEvent.setup();
    renderizar(null);
    await usuario.selectOptions(screen.getByLabelText("Conta de onde saiu"), "Vale");
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
  });

  it("bolso_opcional_em_conta_de_beneficio_sem_vr_marcado", async () => {
    const usuario = userEvent.setup();
    apiLanc.criarLancamento.mockResolvedValue({ tipo: "ok", lancamento: SALVO, repetido: false });
    render(
      <Formulario contas={CONTAS} semVr aoSalvar={vi.fn()} aoSessaoExpirar={vi.fn()} />,
    );
    // Conta comum: sem campo.
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
    await usuario.selectOptions(screen.getByLabelText("Conta de onde saiu"), "Vale");
    const bolso = screen.getByLabelText("Bolso");
    expect(bolso).not.toBeRequired();
    expect(bolso).toHaveValue("");
    expect(screen.getByRole("option", { name: "Sem bolso" })).toBeInTheDocument();
    expect(screen.getByText(/Classifique agora se esta conta será o seu VR/)).toBeInTheDocument();

    // Sem escolher, vai sem bolso.
    await usuario.type(screen.getByLabelText("Valor (R$)"), "10,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(apiLanc.criarLancamento.mock.calls[0]?.[1]).not.toHaveProperty("bolso");

    // Escolhendo, classifica.
    await usuario.selectOptions(screen.getByLabelText("Bolso"), "trabalho");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "5,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(apiLanc.criarLancamento.mock.calls[1]?.[1]).toMatchObject({ bolso: "trabalho" });

    // Receita nessa conta: sem campo.
    await usuario.selectOptions(screen.getByLabelText("Tipo"), "receita");
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
  });

  it("sem_campo_de_bolso_no_va_quando_outra_conta_e_o_vr", async () => {
    const usuario = userEvent.setup();
    const contas = [
      ...CONTAS,
      { ...CONTAS[2]!, conta_id: 5, nome: "Vale B" },
    ];
    render(
      <Formulario
        contas={contas}
        contaVrId={VR}
        semVr={false}
        aoSalvar={vi.fn()}
        aoSessaoExpirar={vi.fn()}
      />,
    );
    const conta = screen.getByLabelText("Conta de onde saiu");
    await usuario.selectOptions(conta, "Vale B");
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
    await usuario.selectOptions(conta, "Banco A");
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
    // No VR continua obrigatório, sem a opção "Sem bolso".
    await usuario.selectOptions(conta, "Vale");
    expect(screen.getByLabelText("Bolso")).toBeRequired();
    expect(screen.queryByRole("option", { name: "Sem bolso" })).not.toBeInTheDocument();
  });

  it("receita_no_vr_nao_pede_bolso", async () => {
    const usuario = userEvent.setup();
    renderizar(VR);
    await usuario.selectOptions(screen.getByLabelText("Tipo"), "receita");
    await usuario.selectOptions(screen.getByLabelText("Conta que recebeu"), "Vale");
    expect(screen.queryByLabelText("Bolso")).not.toBeInTheDocument();
  });

  it("nova_chave_quando_o_bolso_muda_depois_de_um_erro_de_rede", async () => {
    const usuario = userEvent.setup();
    apiLanc.criarLancamento.mockResolvedValue({ tipo: "erro" });
    renderizar(VR);
    await usuario.selectOptions(screen.getByLabelText("Conta de onde saiu"), "Vale");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "10,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    // Mesmo envio de novo (rede caiu): a chave se repete.
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    const [primeira, segunda] = apiLanc.criarLancamento.mock.calls;
    expect(segunda?.[0]).toBe(primeira?.[0]);
    // Mudou o bolso: é outro envio, chave nova.
    await usuario.selectOptions(screen.getByLabelText("Bolso"), "trabalho");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    const terceira = apiLanc.criarLancamento.mock.calls[2];
    expect(terceira?.[0]).not.toBe(primeira?.[0]);
    expect(terceira?.[1]).toMatchObject({ bolso: "trabalho" });
  });

  it("422_do_banco_aparece_com_a_mensagem_literal", async () => {
    const usuario = userEvent.setup();
    apiLanc.criarLancamento.mockResolvedValue({ tipo: "invalido", mensagem: "mensagem do banco" });
    renderizar(VR);
    await usuario.selectOptions(screen.getByLabelText("Conta de onde saiu"), "Vale");
    await usuario.type(screen.getByLabelText("Valor (R$)"), "10,00");
    await usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("mensagem do banco");
  });

  it("edicao_reenvia_o_bolso", async () => {
    const usuario = userEvent.setup();
    apiLanc.editarLancamento.mockResolvedValue({
      tipo: "ok",
      lancamento: { ...SALVO, versao: 2 },
      repetido: false,
    });
    render(
      <Formulario
        contas={CONTAS}
        contaVrId={VR}
        edicao={SALVO}
        aoSalvar={vi.fn()}
        aoSessaoExpirar={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Bolso")).toHaveValue("trabalho");
    await usuario.click(screen.getByRole("button", { name: "Salvar alteração" }));
    expect(apiLanc.editarLancamento).toHaveBeenCalledWith(
      10,
      1,
      expect.objectContaining({ bolso: "trabalho" }),
    );
  });
});

describe("lista de lançamentos da conta do VR", () => {
  beforeEach(() => {
    vi.mocked(sessao).recuperarSessao.mockResolvedValue(true);
    vi.mocked(saldos).listarSaldos.mockResolvedValue({ tipo: "ok", saldos: CONTAS });
    vi.mocked(leitura).listarPessoas.mockResolvedValue({ tipo: "ok", dados: [] });
    apiLanc.listarLancamentos.mockResolvedValue({
      tipo: "ok",
      lancamentos: [SALVO, { ...SALVO, transacao_id: 11, conta_id: 1, bolso: null }],
    });
  });

  it("mostra_o_bolso_e_descobre_o_vr_pelo_parametro", async () => {
    vi.mocked(vale).obterParametroVale.mockResolvedValue({
      tipo: "ok",
      dados: {
        conta_id: VR,
        base_trabalho: "200.00",
        destino_padrao: "nenhum",
        vigente_desde: "2026-11-01",
      },
    });
    render(
      <MemoryRouter initialEntries={["/lancamentos"]}>
        <App />
      </MemoryRouter>,
    );
    const lista = await screen.findByRole("list", { name: "Lançamentos" });
    const [noVr, naCorrente] = within(lista).getAllByRole("listitem");
    expect(noVr).toHaveTextContent("bolso trabalho");
    expect(naCorrente).not.toHaveTextContent("bolso");
    // O formulário novo já conhece o VR.
    const form = screen.getByRole("form", { name: "Novo lançamento" });
    await userEvent.setup().selectOptions(within(form).getByLabelText("Conta de onde saiu"), "Vale");
    expect(within(form).getByLabelText("Bolso")).toBeInTheDocument();
  });
  it("sem_vr_marcado_no_parametro_o_formulario_oferece_bolso_opcional", async () => {
    vi.mocked(vale).obterParametroVale.mockResolvedValue({ tipo: "ok", dados: null });
    render(
      <MemoryRouter initialEntries={["/lancamentos"]}>
        <App />
      </MemoryRouter>,
    );
    const form = await screen.findByRole("form", { name: "Novo lançamento" });
    await userEvent.setup().selectOptions(within(form).getByLabelText("Conta de onde saiu"), "Vale");
    expect(within(form).getByLabelText("Bolso")).not.toBeRequired();
  });
});
