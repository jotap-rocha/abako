import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";

import type { LancamentoSaida } from "../api/gerado";
import * as api from "../api/lancamentos";
import { CONTAS } from "./contasDeTeste";
import { Formulario } from "./Formulario";

vi.mock("../api/lancamentos");
const apiLanc = vi.mocked(api);

const EXISTENTE: LancamentoSaida = {
  transacao_id: 10,
  versao: 3,
  tipo: "debito",
  data: "2026-11-04",
  valor: "50.00",
  conta_id: 1,
  conta_destino_id: null,
  bruto: null,
  imposto: null,
  descricao: null,
};

afterEach(() => {
  vi.resetAllMocks();
});

describe("erros do formulário de lançamento", () => {
  it("erro_direto", async () => {
    const usuario = userEvent.setup();
    render(<Formulario contas={CONTAS} aoSalvar={vi.fn()} aoSessaoExpirar={vi.fn()} />);
    const enviar = () => usuario.click(screen.getByRole("button", { name: "Salvar lançamento" }));

    // Valor ilegível: a própria tela explica, sem chamar o servidor.
    await usuario.type(screen.getByLabelText("Valor (R$)"), "abc");
    await enviar();
    expect(screen.getByRole("alert")).toHaveTextContent("Valor não reconhecido");
    // O campo com problema é marcado para leitores de tela e recebe o foco.
    const campo = screen.getByLabelText("Valor (R$)");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAttribute("aria-describedby", screen.getByRole("alert").id);
    expect(campo).toHaveFocus();
    expect(apiLanc.criarLancamento).not.toHaveBeenCalled();

    // Sinal de menos: o tipo é que diz se entra ou sai.
    await usuario.clear(screen.getByLabelText("Valor (R$)"));
    await usuario.type(screen.getByLabelText("Valor (R$)"), "-5,00");
    await enviar();
    expect(screen.getByRole("alert")).toHaveTextContent("sem sinal de menos");
    expect(apiLanc.criarLancamento).not.toHaveBeenCalled();

    // Regra recusada pelo servidor: a mensagem dele aparece e nada é reenviado sozinho.
    apiLanc.criarLancamento.mockResolvedValueOnce({
      tipo: "invalido",
      mensagem: "a data não pode ser futura",
    });
    await usuario.clear(screen.getByLabelText("Valor (R$)"));
    await usuario.type(screen.getByLabelText("Valor (R$)"), "5,00");
    await enviar();
    expect(await screen.findByRole("alert")).toHaveTextContent("a data não pode ser futura");
    expect(apiLanc.criarLancamento).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Valor (R$)")).toHaveValue("5,00");
  });

  it("explica_versao_desatualizada_na_edicao", async () => {
    const usuario = userEvent.setup();
    apiLanc.editarLancamento.mockResolvedValueOnce({ tipo: "desatualizado" });
    render(
      <Formulario
        contas={CONTAS}
        edicao={EXISTENTE}
        aoSalvar={vi.fn()}
        aoSessaoExpirar={vi.fn()}
      />,
    );
    await usuario.click(screen.getByRole("button", { name: "Salvar alteração" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("mudou em outra aba");
    expect(apiLanc.editarLancamento).toHaveBeenCalledWith(10, 3, expect.objectContaining({ valor: "50.00" }));
    expect(apiLanc.editarLancamento).toHaveBeenCalledTimes(1);
  });
});
