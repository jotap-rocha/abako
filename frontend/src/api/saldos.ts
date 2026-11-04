// Saldos, snapshots e R4 pelo cliente gerado. Como em `contas.ts`, devolve um resultado tipado em
// vez de lançar, para a tela tratar sempre carregando, sucesso, vazio e erro. Os valores chegam
// como texto e seguem texto: o front não soma, não compara e não arredonda nada (ADR 015).

import {
  type DivergenciaSaida,
  type SaldoSaida,
  type SnapshotSaida,
  saldosListar,
  saldosR4,
  saldosRegistrarSnapshot,
} from "./gerado";

export type ResultadoSaldos =
  | { tipo: "ok"; saldos: SaldoSaida[] }
  | { tipo: "sessao_expirada" }
  | { tipo: "erro" };

export type ResultadoR4 =
  | { tipo: "ok"; divergencias: DivergenciaSaida[] }
  | { tipo: "sessao_expirada" }
  | { tipo: "erro" };

export type ResultadoSnapshot =
  | { tipo: "ok"; snapshot: SnapshotSaida }
  | { tipo: "sessao_expirada" }
  | { tipo: "conta_nao_encontrada" }
  | { tipo: "invalido" }
  | { tipo: "erro" };

export async function listarSaldos(): Promise<ResultadoSaldos> {
  try {
    const resposta = await saldosListar();
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", saldos: resposta.data };
    }
    return status === 401 ? { tipo: "sessao_expirada" } : { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

export async function listarDivergencias(): Promise<ResultadoR4> {
  try {
    const resposta = await saldosR4();
    const status = resposta.response?.status;
    if (status === 200 && resposta.data !== undefined) {
      return { tipo: "ok", divergencias: resposta.data };
    }
    return status === 401 ? { tipo: "sessao_expirada" } : { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}

/** `valor` já vem no formato da API ("1234.56"); `data` é "AAAA-MM-DD". */
export async function registrarSnapshot(
  contaId: number,
  data: string,
  valor: string,
): Promise<ResultadoSnapshot> {
  try {
    const resposta = await saldosRegistrarSnapshot({
      path: { conta_id: contaId },
      body: { data, valor },
    });
    const status = resposta.response?.status;
    if (status === 201 && resposta.data !== undefined) {
      return { tipo: "ok", snapshot: resposta.data };
    }
    if (status === 401) return { tipo: "sessao_expirada" };
    if (status === 404) return { tipo: "conta_nao_encontrada" };
    if (status === 422) return { tipo: "invalido" };
    return { tipo: "erro" };
  } catch {
    return { tipo: "erro" };
  }
}
