// Pessoas (terceiros) e "a receber" pelo cliente gerado. O nome da pessoa é dado pessoal: aparece
// só na tela do dono, nunca em URL, log ou cache (ADR 050).

import { type Leitura, ler } from "./base";
import { type Escrita, apagar, escrever } from "./escrita";
import {
  type AReceberSaida,
  type PessoaSaida,
  pessoasAReceber,
  pessoasCriar,
  pessoasExcluir,
  pessoasRenomear,
} from "./gerado";

export const listarAReceber = (): Promise<Leitura<AReceberSaida[]>> => ler(() => pessoasAReceber());

export const criarPessoa = (nome: string): Promise<Escrita<PessoaSaida>> =>
  escrever(() => pessoasCriar({ body: { nome } }));

/** `versao` é a que a tela leu; se outra edição veio antes, volta "desatualizado". */
export const renomearPessoa = (
  pessoaId: number,
  versao: number,
  nome: string,
): Promise<Escrita<PessoaSaida>> =>
  escrever(() => pessoasRenomear({ path: { pessoa_id: pessoaId }, body: { nome, versao } }));

export const excluirPessoa = (pessoaId: number, versao: number): Promise<Escrita<null>> =>
  apagar(() => pessoasExcluir({ path: { pessoa_id: pessoaId }, query: { versao } }));
