"""Execução do pipeline: trava, leitura consistente, arquivo novo, validação e troca atômica.

Garantias (ADR 054): lê só pelo papel somente leitura, em transação REPEATABLE READ READ ONLY;
escreve só no arquivo analítico; o arquivo anterior só é substituído (os.replace) depois de o
novo passar na validação; em qualquer falha o anterior fica intacto e o temporário é apagado.
Logs levam apenas etapa, contagens e duração: nunca valor, id de conta/pessoa ou nome.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import psycopg
from psycopg.rows import tuple_row

from db.alvo import USUARIO_PIPELINE, AlvoInvalido, verificar_banco_conectado
from pipeline import esquema, extracao
from pipeline.config import Config

LOG = logging.getLogger("abako.pipeline")
# Chave de duas partes: espaço de chaves diferente do `pg_advisory_xact_lock(bigint)` do ledger.
TRAVA_CLASSE = 1_094_994_767
TRAVA_OBJETO = 14

SUCESSO = 0
RECUSADO = 2
TRAVADO = 3
FALHA = 4


class ExecucaoOcupada(Exception):
    """Outra execução do pipeline está em andamento (INV-35)."""


class ValidacaoFalhou(Exception):
    """O arquivo novo não bate com o transacional; não é publicado."""


def _etapa(etapa: str, run_id: str, lidos: int | None, escritos: int | None, t0: float) -> None:
    LOG.info(
        "etapa=%s run_id=%s registros_lidos=%s registros_escritos=%s duracao_ms=%d",
        etapa,
        run_id,
        lidos,
        escritos,
        int((time.monotonic() - t0) * 1000),
    )


@contextmanager
def _trava(url: str) -> Iterator[None]:
    """Trava de sessão no Postgres: a segunda execução falha rápido, sem tocar o arquivo."""
    with psycopg.connect(url, autocommit=True) as c:
        linha = c.execute(
            "SELECT pg_try_advisory_lock(%s, %s)", (TRAVA_CLASSE, TRAVA_OBJETO)
        ).fetchone()
        if not linha or linha[0] is not True:
            raise ExecucaoOcupada("outra execução do pipeline está em andamento")
        try:
            yield
        finally:
            c.execute("SELECT pg_advisory_unlock(%s, %s)", (TRAVA_CLASSE, TRAVA_OBJETO))


def _limpar(caminho: Path) -> None:
    for sufixo in ("", ".wal"):
        Path(str(caminho) + sufixo).unlink(missing_ok=True)


def _temporarios_antigos(config: Config) -> None:
    """Restos de execução morta no meio (só possível sob a trava, então nenhum é de outro run)."""
    for resto in config.diretorio.glob(f"{config.arquivo.name}.*.tmp*"):
        resto.unlink(missing_ok=True)


def _abrir_leitura(config: Config) -> psycopg.Connection[Any]:
    conn = psycopg.connect(config.url, row_factory=tuple_row)
    conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    conn.read_only = True
    linha = conn.execute("SELECT current_database(), current_user").fetchone()
    if linha is None:
        raise AlvoInvalido("a conexão não identificou banco e papel")
    verificar_banco_conectado(config.ambiente, linha[0])
    if linha[1] != USUARIO_PIPELINE:
        raise AlvoInvalido("a conexão não é do papel abako_pipeline")
    return conn


def _somas(tabela: str, linhas: extracao.Linhas) -> dict[str, Decimal]:
    nomes = [n for n, _ in esquema.TABELAS[tabela]]
    somas: dict[str, Decimal] = {}
    for coluna in esquema.COLUNAS_DE_VALOR.get(tabela, ()):
        i = nomes.index(coluna)
        somas[coluna] = sum((Decimal(r[i]) for r in linhas if r[i] is not None), Decimal(0))
    return somas


def validar(
    arquivo: Path,
    esperado: dict[str, extracao.Linhas],
    totais_gasto: extracao.Linhas,
) -> None:
    """Reabre o arquivo novo só para leitura e confere contagens e somas com o que foi lido."""
    con = duckdb.connect(str(arquivo), read_only=True)
    try:
        for tabela in esquema.TABELAS_DE_DADOS:
            linhas = esperado[tabela]
            qtd = con.execute(f"SELECT count(*) FROM {tabela}").fetchone()  # noqa: S608
            if not qtd or qtd[0] != len(linhas):
                raise ValidacaoFalhou(f"contagem divergente em {tabela}")
            for coluna, soma in _somas(tabela, linhas).items():
                lida = con.execute(  # noqa: S608
                    f"SELECT COALESCE(sum({coluna}), 0) FROM {tabela}"
                ).fetchone()
                if not lida or Decimal(lida[0]) != soma:
                    raise ValidacaoFalhou(f"soma divergente em {tabela}.{coluna}")
        # o gasto do mês (somado por conta) é o gasto_real do mês, por usuário
        for uid, mes, total in totais_gasto:
            lida = con.execute(
                "SELECT COALESCE(sum(gasto), 0) FROM gasto_mensal WHERE user_id = ? AND mes = ?",
                [uid, mes],
            ).fetchone()
            if not lida or Decimal(lida[0]) != Decimal(total):
                raise ValidacaoFalhou("gasto_mensal não bate com gasto_real")
        # fatura: total = própria + terceiros em toda linha
        ruim = con.execute(
            "SELECT count(*) FROM fatura_resumo WHERE total <> propria + terceiros"
        ).fetchone()
        if ruim and ruim[0]:
            raise ValidacaoFalhou("fatura_resumo com total diferente de própria + terceiros")
    finally:
        con.close()


def construir(config: Config, destino: Path, run_id: str) -> dict[str, int]:
    """Lê o transacional (um retrato) e grava `destino`; devolve linhas por tabela."""
    t0 = time.monotonic()
    conn = _abrir_leitura(config)
    try:
        uids = extracao.usuarios(conn, config.usuarios)
        hoje = config.hoje
        dados: dict[str, extracao.Linhas] = {
            "saldo_diario": extracao.saldo_diario(conn, uids, hoje),
            "gasto_mensal": extracao.gasto_mensal(conn, uids),
            "fatura_resumo": extracao.fatura_resumo(conn, uids),
            "limite_linha": extracao.limite_linha(conn, uids, hoje),
            "cobertura_reserva": extracao.cobertura_reserva(conn, uids, hoje),
            "a_receber": extracao.a_receber(conn, uids),
        }
        totais_gasto = extracao.gasto_total_por_mes(conn, uids)
        r4 = extracao.divergencias_r4(conn, uids)
    finally:
        conn.rollback()  # leitura apenas: nada a confirmar
        conn.close()
    _etapa("leitura", run_id, sum(len(v) for v in dados.values()), None, t0)
    LOG.info("R4: divergencias=%d", r4)  # só contagem (ADR 041/054)

    t1 = time.monotonic()
    con = duckdb.connect(str(destino))
    contagens: dict[str, int] = {}
    try:
        esquema.criar(con)
        for tabela in esquema.TABELAS_DE_DADOS:
            contagens[tabela] = esquema.inserir(con, tabela, dados[tabela])
        esquema.inserir(con, "execucao", [(hoje, esquema.VERSAO_ESQUEMA, config.ambiente)])
        con.execute("CHECKPOINT")
    finally:
        con.close()
    _etapa("escrita", run_id, None, sum(contagens.values()), t1)

    t2 = time.monotonic()
    validar(destino, dados, totais_gasto)
    _etapa("validacao", run_id, None, None, t2)
    return contagens


def executar(config: Config) -> int:
    """Roda o pipeline inteiro; devolve o código de saída (0 ok, 3 travado, 4 falha)."""
    run_id = uuid.uuid4().hex[:8]
    try:
        with _trava(config.url):
            config.diretorio.mkdir(parents=True, exist_ok=True)  # só sob a trava
            _temporarios_antigos(config)
            tmp = config.arquivo.with_name(f"{config.arquivo.name}.{run_id}.tmp")
            try:
                construir(config, tmp, run_id)
                t0 = time.monotonic()
                os.replace(tmp, config.arquivo)  # troca atômica
                _etapa("troca", run_id, None, None, t0)
            finally:
                _limpar(tmp)
        LOG.info("pipeline concluído run_id=%s", run_id)
        return SUCESSO
    except ExecucaoOcupada:
        LOG.error("pipeline recusado: outra execução em andamento")
        return TRAVADO
    except Exception as exc:  # noqa: BLE001 - qualquer falha mantém o arquivo anterior
        # Só a classe (e o SQLSTATE): a mensagem de driver pode carregar valor ou nome.
        LOG.error(
            "pipeline falhou run_id=%s erro=%s sqlstate=%s",
            run_id,
            type(exc).__name__,
            getattr(exc, "sqlstate", None),
        )
        return FALHA
