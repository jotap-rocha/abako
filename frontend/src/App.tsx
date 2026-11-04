import { useCallback, useEffect, useState } from "react";
import { Route, Routes } from "react-router";

import { recuperarSessao, sair } from "./api/sessao";
import { Casca } from "./layout/Casca";
import { Login } from "./login/Login";
import { Contas } from "./paginas/Contas";
import { EmBreve } from "./paginas/EmBreve";
import { Inicio } from "./paginas/Inicio";
import { NaoEncontrada } from "./paginas/NaoEncontrada";
import { limparCachesDoApp } from "./pwa/cache";
import { Carregando } from "./ui/componentes";

type Estado = "carregando" | "anonimo" | "autenticado";

export function App() {
  const [estado, setEstado] = useState<Estado>("carregando");

  useEffect(() => {
    let ativo = true;
    void recuperarSessao().then((aberta) => {
      if (ativo) setEstado(aberta ? "autenticado" : "anonimo");
    });
    return () => {
      ativo = false;
    };
  }, []);

  async function aoSair() {
    try {
      await sair();
    } catch {
      // Sem resposta do servidor: a sessão expira sozinha lá; aqui o logout segue.
    }
    // Aconteça o que acontecer no servidor, o que ficou no navegador é apagado.
    await limparCachesDoApp();
    setEstado("anonimo");
  }

  // Sessão vencida no meio do uso: volta ao login sem mexer em mais nada.
  const aoSessaoExpirar = useCallback(() => setEstado("anonimo"), []);

  if (estado === "carregando") {
    return (
      <div className="tela-cheia">
        <Carregando />
      </div>
    );
  }
  if (estado === "anonimo") {
    return <Login aoEntrar={() => setEstado("autenticado")} />;
  }
  return (
    <Routes>
      <Route element={<Casca aoSair={() => void aoSair()} aoSessaoExpirar={aoSessaoExpirar} />}>
        <Route index element={<Inicio />} />
        <Route path="contas" element={<Contas />} />
        <Route
          path="lancamentos"
          element={
            <EmBreve
              titulo="Lançamentos"
              descricao="Receitas, despesas, transferências e mais."
              texto="O formulário de lançamento chega junto com a regra de lançamentos."
            />
          }
        />
        <Route
          path="alertas"
          element={
            <EmBreve
              titulo="Alertas"
              descricao="O que pede a sua atenção."
              texto="Os alertas chegam depois de saldo, gasto real e recorrentes."
            />
          }
        />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  );
}
