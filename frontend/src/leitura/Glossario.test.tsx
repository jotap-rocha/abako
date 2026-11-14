import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Glossario, type IdTermo, TERMOS, Termo } from "./Glossario";

// Os termos que o usuário precisa ver explicados (CONTEXT.md), por id.
const OBRIGATORIOS: IdTermo[] = [
  "competencia",
  "fatura_propria",
  "fatura_terceiros",
  "limite_usado",
  "cobertura",
  "sobra",
  "horizonte",
  "snapshot",
  "divergencia",
];

describe("glossário", () => {
  it("termos_explicados", async () => {
    // Todo termo obrigatório existe e tem uma explicação de verdade (não só o nome repetido).
    for (const id of OBRIGATORIOS) {
      expect(TERMOS[id].texto.length).toBeGreaterThan(40);
    }

    // Termo no meio do texto: a explicação só aparece ao ativar, e o botão avisa o estado.
    const usuario = userEvent.setup();
    const { unmount } = render(
      <p>
        Veja a <Termo id="competencia">competência</Termo> da fatura.
      </p>,
    );
    const botao = screen.getByRole("button", { name: /competência/ });
    expect(botao).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    await usuario.click(botao);
    expect(botao).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("note")).toHaveTextContent(TERMOS.competencia.texto);
    // Funciona pelo teclado também: Enter fecha, Espaço abre de novo. A explicação continua no
    // DOM (o aria-controls do botão aponta para ela), só escondida.
    botao.focus();
    await usuario.keyboard("{Enter}");
    expect(botao).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(document.getElementById(botao.getAttribute("aria-controls") ?? "")).toHaveAttribute(
      "hidden",
    );
    await usuario.keyboard(" ");
    expect(botao).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("note")).toBeInTheDocument();
    unmount();

    // Lista no fim da página: todos os termos pedidos, com nome e explicação.
    render(<Glossario termos={OBRIGATORIOS} />);
    const lista = screen.getByText("O que significam estes termos?").closest("details");
    expect(lista).not.toBeNull();
    for (const id of OBRIGATORIOS) {
      expect(within(lista as HTMLElement).getByText(TERMOS[id].nome)).toBeInTheDocument();
      expect(within(lista as HTMLElement).getByText(TERMOS[id].texto)).toBeInTheDocument();
    }
  });
});
