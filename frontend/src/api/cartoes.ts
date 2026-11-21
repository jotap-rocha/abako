// Cadastro da linha de crédito e do cartão pelo cliente gerado (ADR 043, 055). O servidor valida
// e decide (formato do limite, nome repetido, regras do banco); esta camada só repassa. O limite
// é sempre texto: nenhuma conta, nenhum `number`.

import { type Leitura, ler } from "./base";
import { type Escrita, escrever } from "./escrita";
import {
  type ContaSaida,
  type LinhaSaida,
  contasCriar,
  linhasCreditoCriar,
  linhasCreditoEditar,
  linhasCreditoListar,
} from "./gerado";

export const listarLinhas = (): Promise<Leitura<LinhaSaida[]>> => ler(() => linhasCreditoListar());

export const criarLinha = (nome: string, limite: string): Promise<Escrita<LinhaSaida>> =>
  escrever(() => linhasCreditoCriar({ body: { nome, limite } }));

/** `versao` é a que a tela leu; se outra edição veio antes, volta `desatualizado`. */
export const editarLinha = (
  linhaId: number,
  versao: number,
  nome: string,
  limite: string,
): Promise<Escrita<LinhaSaida>> =>
  escrever(() =>
    linhasCreditoEditar({ path: { linha_id: linhaId }, body: { nome, limite, versao } }),
  );

/** Cartão = conta do tipo dívida ligada a uma linha de crédito (o banco recusa sem a linha). */
export const criarCartao = (nome: string, linhaId: number): Promise<Escrita<ContaSaida>> =>
  escrever(() =>
    contasCriar({
      body: { nome, tipo: "divida", conta_beneficio: false, linha_credito_id: linhaId },
    }),
  );
