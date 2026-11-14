import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router";

import type { Leitura } from "../api/leitura";
import type { ContextoCasca } from "../layout/Casca";

export type EstadoCarga<T> =
  | { tipo: "carregando" }
  | { tipo: "erro" }
  | { tipo: "invalido" }
  | { tipo: "nao_encontrado" }
  | { tipo: "ok"; dados: T };

/**
 * Busca dados na API e acompanha o estado (carregando, erro, ok). "Hook" é uma função do React
 * que guarda estado dentro de um componente; este repete a receita que as telas de saldo usam:
 * só a resposta do pedido mais recente vale, e sessão vencida (401) manda de volta ao login.
 *
 * `buscar` precisa ser estável (useCallback) ou a tela buscaria sem parar. Passe `null` para
 * não buscar ainda.
 */
export function useCarga<T>(buscar: (() => Promise<Leitura<T>>) | null): {
  estado: EstadoCarga<T>;
  recarregar: () => void;
} {
  const { aoSessaoExpirar } = useOutletContext<ContextoCasca>();
  const [estado, setEstado] = useState<EstadoCarga<T>>({ tipo: "carregando" });
  const ultimoPedido = useRef(0);

  const carregar = useCallback(async () => {
    const pedido = ++ultimoPedido.current;
    if (buscar === null) return;
    setEstado({ tipo: "carregando" });
    const resultado = await buscar();
    if (pedido !== ultimoPedido.current) return;
    if (resultado.tipo === "sessao_expirada") aoSessaoExpirar();
    else if (resultado.tipo === "ok") setEstado({ tipo: "ok", dados: resultado.dados });
    else setEstado({ tipo: resultado.tipo });
  }, [buscar, aoSessaoExpirar]);

  useEffect(() => {
    void carregar();
    return () => {
      ultimoPedido.current += 1;
    };
  }, [carregar]);

  return { estado, recarregar: () => void carregar() };
}

type Falha = Exclude<Leitura<never>, { tipo: "ok" }>;

/**
 * Se alguma leitura falhou, devolve a falha que deve valer: sessão vencida (401) sempre ganha,
 * porque o certo é voltar ao login; senão vale a primeira. Sem falha, devolve `null`.
 */
export function primeiraFalha(leituras: Leitura<unknown>[]): Falha | null {
  const falhas = leituras.filter((l): l is Falha => l.tipo !== "ok");
  return falhas.find((f) => f.tipo === "sessao_expirada") ?? falhas[0] ?? null;
}

/** Junta duas leituras numa só: ok só se as duas deram certo; senão a falha que vale. */
export async function juntar<A, B>(
  a: Promise<Leitura<A>>,
  b: Promise<Leitura<B>>,
): Promise<Leitura<[A, B]>> {
  const [ra, rb] = await Promise.all([a, b]);
  const falha = primeiraFalha([ra, rb]);
  if (falha !== null) return falha;
  if (ra.tipo !== "ok" || rb.tipo !== "ok") return { tipo: "erro" };
  return { tipo: "ok", dados: [ra.dados, rb.dados] };
}
