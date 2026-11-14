import { useCallback, useEffect, useState } from "react";
import { Route, Routes } from "react-router";

import { recuperarSessao, sair } from "./api/sessao";
import { Casca } from "./layout/Casca";
import { Login } from "./login/Login";
import { Lancamentos } from "./lancamento/Lancamentos";
import { Alertas } from "./leitura/Alertas";
import { Cartoes } from "./leitura/Cartoes";
import { GastoReal } from "./leitura/GastoReal";
import { Reserva } from "./leitura/Reserva";
import { SobraR2 } from "./leitura/SobraR2";
import { Parametros } from "./parametros/Parametros";
import { Recorrentes } from "./recorrentes/Recorrentes";
import { Pessoas } from "./terceiros/Pessoas";
import { Inicio } from "./paginas/Inicio";
import { NaoEncontrada } from "./paginas/NaoEncontrada";
import { limparCachesDoApp } from "./pwa/cache";
import { Saldos } from "./saldos/Saldos";
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
        <Route path="contas" element={<Saldos />} />
        <Route path="lancamentos" element={<Lancamentos />} />
        <Route path="cartoes" element={<Cartoes />} />
        <Route path="gasto-real" element={<GastoReal />} />
        <Route path="reserva" element={<Reserva />} />
        <Route path="sobra" element={<SobraR2 />} />
        <Route path="alertas" element={<Alertas />} />
        <Route path="pessoas" element={<Pessoas />} />
        <Route path="recorrentes" element={<Recorrentes />} />
        <Route path="parametros" element={<Parametros />} />
        <Route path="*" element={<NaoEncontrada />} />
      </Route>
    </Routes>
  );
}
