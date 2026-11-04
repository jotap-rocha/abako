import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, vi } from "vitest";

import { App } from "../App";
import * as sessao from "../api/sessao";

// A fronteira com o servidor é a única coisa simulada; a tela e o App rodam de verdade.
vi.mock("../api/sessao");
const api = vi.mocked(sessao);

function renderizar() {
  return render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
}

async function preencherEEnviar() {
  const usuario = userEvent.setup();
  // O App começa em "Carregando…" até saber se já há sessão; espera o campo aparecer.
  await usuario.type(await screen.findByLabelText("Login"), "joao");
  await usuario.type(screen.getByLabelText("Senha"), "senha-de-teste-123");
  await usuario.click(screen.getByRole("button", { name: "Entrar" }));
}

beforeEach(() => {
  api.recuperarSessao.mockResolvedValue(false);
  api.sair.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe("login e logout", () => {
  it("login_entra_com_credenciais", async () => {
    api.entrar.mockResolvedValue("ok");
    renderizar();
    await preencherEEnviar();

    expect(await screen.findByRole("button", { name: "Sair" })).toBeInTheDocument();
    expect(api.entrar).toHaveBeenCalledWith("joao", "senha-de-teste-123");
  });

  it("login_mostra_erro_e_limpa_a_senha", async () => {
    api.entrar.mockResolvedValue("credenciais");
    renderizar();
    await preencherEEnviar();

    expect(await screen.findByRole("alert")).toHaveTextContent("Login ou senha inválidos.");
    expect(screen.getByLabelText("Senha")).toHaveValue("");
  });

  it("login_avisa_bloqueio_e_falha_de_rede", async () => {
    api.entrar.mockResolvedValueOnce("bloqueado").mockResolvedValueOnce("erro");
    renderizar();
    await preencherEEnviar();
    expect(await screen.findByRole("alert")).toHaveTextContent("Muitas tentativas");

    await preencherEEnviar();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível falar com o servidor"),
    );
  });

  it("botao_mostra_e_oculta_a_senha", async () => {
    renderizar();
    const campo = await screen.findByLabelText("Senha");
    expect(campo).toHaveAttribute("type", "password");

    const usuario = userEvent.setup();
    await usuario.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(screen.getByLabelText("Senha")).toHaveAttribute("type", "text");
    await usuario.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(screen.getByLabelText("Senha")).toHaveAttribute("type", "password");
  });

  it("sessao_aberta_pula_o_login", async () => {
    api.recuperarSessao.mockResolvedValue(true);
    renderizar();

    expect(await screen.findByRole("button", { name: "Sair" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Login")).not.toBeInTheDocument();
  });

  it("logout_limpa_cache", async () => {
    api.recuperarSessao.mockResolvedValue(true);
    const apagar = vi.fn().mockResolvedValue(true);
    vi.stubGlobal("caches", {
      keys: vi.fn().mockResolvedValue(["abako-shell-v1", "outro-cache"]),
      delete: apagar,
    });
    renderizar();

    await userEvent.setup().click(await screen.findByRole("button", { name: "Sair" }));

    expect(await screen.findByLabelText("Login")).toBeInTheDocument();
    expect(api.sair).toHaveBeenCalledTimes(1);
    expect(apagar).toHaveBeenCalledWith("abako-shell-v1");
    expect(apagar).toHaveBeenCalledWith("outro-cache");
  });

  it("logout_limpa_cache_mesmo_se_o_servidor_falhar", async () => {
    api.recuperarSessao.mockResolvedValue(true);
    api.sair.mockRejectedValue(new Error("sem rede"));
    const apagar = vi.fn().mockResolvedValue(true);
    vi.stubGlobal("caches", { keys: vi.fn().mockResolvedValue(["abako-shell-v1"]), delete: apagar });
    renderizar();

    await userEvent.setup().click(await screen.findByRole("button", { name: "Sair" }));

    await waitFor(() => expect(apagar).toHaveBeenCalledWith("abako-shell-v1"));
  });
});
