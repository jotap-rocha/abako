import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router";

import {
  IconeAlertas,
  IconeCartoes,
  IconeContas,
  IconeGasto,
  IconeInicio,
  IconeLancamentos,
  IconeParametros,
  IconePessoas,
  IconeRecorrentes,
  IconeReserva,
  IconeSair,
  IconeSobra,
} from "../ui/icones";

type ItemMenu = { para: string; texto: string; icone: ReactNode };

const MENU: ItemMenu[] = [
  { para: "/", texto: "Início", icone: <IconeInicio /> },
  { para: "/contas", texto: "Contas", icone: <IconeContas /> },
  { para: "/lancamentos", texto: "Lançamentos", icone: <IconeLancamentos /> },
  { para: "/cartoes", texto: "Cartões", icone: <IconeCartoes /> },
  { para: "/gasto-real", texto: "Gasto do mês", icone: <IconeGasto /> },
  { para: "/reserva", texto: "Reserva", icone: <IconeReserva /> },
  { para: "/sobra", texto: "Sobra (R2)", icone: <IconeSobra /> },
  { para: "/alertas", texto: "Alertas", icone: <IconeAlertas /> },
  { para: "/pessoas", texto: "Pessoas", icone: <IconePessoas /> },
  { para: "/recorrentes", texto: "Recorrentes", icone: <IconeRecorrentes /> },
  { para: "/parametros", texto: "Parâmetros", icone: <IconeParametros /> },
];

/** O que as páginas recebem da casca (via `useOutletContext`). */
export type ContextoCasca = { aoSessaoExpirar: () => void };

type Props = { aoSair: () => void; aoSessaoExpirar: () => void };

/** Moldura do app logado: menu lateral (vira barra de baixo no celular), topo e conteúdo. */
export function Casca({ aoSair, aoSessaoExpirar }: Props) {
  const contexto: ContextoCasca = { aoSessaoExpirar };
  return (
    <div className="casca">
      <a className="pular-para-conteudo" href="#conteudo">
        Pular para o conteúdo
      </a>
      <aside className="lateral">
        <div className="marca">
          <span className="marca-logo" aria-hidden="true">
            a
          </span>
          <span className="marca-nome">abako</span>
        </div>
        <nav aria-label="Principal">
          <ul className="menu">
            {MENU.map((item) => (
              <li key={item.para}>
                <NavLink
                  to={item.para}
                  end={item.para === "/"}
                  className={({ isActive }) => (isActive ? "menu-link ativo" : "menu-link")}
                >
                  {item.icone}
                  <span>{item.texto}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="area">
        <header className="topo">
          <span className="topo-titulo">Controle financeiro pessoal</span>
          <button type="button" className="botao botao-secundario" onClick={aoSair}>
            <IconeSair />
            <span>Sair</span>
          </button>
        </header>
        <main id="conteudo" className="conteudo" tabIndex={-1}>
          <Outlet context={contexto} />
        </main>
      </div>
    </div>
  );
}
