import { type FormEvent, useState } from "react";

import { type ResultadoLogin, entrar } from "../api/sessao";
import { IconeOlho, IconeOlhoRiscado } from "../ui/icones";

const MENSAGENS: Record<Exclude<ResultadoLogin, "ok">, string> = {
  credenciais: "Login ou senha inválidos.",
  bloqueado: "Muitas tentativas. Aguarde alguns minutos e tente de novo.",
  erro: "Não foi possível falar com o servidor. Tente de novo.",
};

type Props = { aoEntrar: () => void };

export function Login({ aoEntrar }: Props) {
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setEnviando(true);
    setErro(null);
    const resultado = await entrar(login, senha);
    setEnviando(false);
    setSenha("");
    if (resultado === "ok") {
      aoEntrar();
    } else {
      setErro(MENSAGENS[resultado]);
    }
  }

  return (
    <div className="login">
      <aside className="login-marca" aria-hidden="true">
        <span className="marca-logo marca-logo-grande">a</span>
        <p className="login-frase">Suas finanças, claras e só suas.</p>
        <p className="login-apoio">Local, privado e sem depender de ninguém.</p>
      </aside>
      <main className="login-painel">
        <div className="login-cartao">
          <h1>Entrar</h1>
          <p className="login-subtitulo">Use o login e a senha da sua conta.</p>
          <form onSubmit={enviar} className="formulario">
            <div className="campo">
              <label htmlFor="login">Login</label>
              <input
                id="login"
                name="login"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                required
              />
            </div>
            <div className="campo">
              <label htmlFor="senha">Senha</label>
              <div className="campo-senha">
                <input
                  id="senha"
                  name="senha"
                  type={mostrarSenha ? "text" : "password"}
                  autoComplete="current-password"
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="botao-icone"
                  aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                  aria-pressed={mostrarSenha}
                  onClick={() => setMostrarSenha((atual) => !atual)}
                >
                  {mostrarSenha ? <IconeOlhoRiscado /> : <IconeOlho />}
                </button>
              </div>
            </div>
            {erro !== null && (
              <p role="alert" className="erro-form">
                {erro}
              </p>
            )}
            <button type="submit" className="botao botao-primario" disabled={enviando}>
              {enviando ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
