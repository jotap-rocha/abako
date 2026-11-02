"""Nome dos arquivos de backup e retenção mínima 7 diários + 4 semanais (ADR 037).

Funções puras: a seleção não toca disco; quem remove é `scripts/backup.py`, só dentro da
pasta configurada e só arquivos com o padrão de nome abaixo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
DIARIOS = 7
SEMANAIS = 4
SUFIXO = ".dump.age"
# Só data/hora e o ambiente: nenhum dado pessoal no nome do arquivo.
RE_NOME = re.compile(r"^abako-(tst|prd)-(\d{8})-(\d{6})\.dump\.age$")


def nome_backup(ambiente: str, agora: datetime) -> str:
    """`abako-<amb>-AAAAMMDD-HHMMSS.dump.age`, hora civil de São Paulo."""
    if ambiente not in {"tst", "prd"}:
        raise ValueError(f"ambiente inválido: {ambiente!r}")
    local = agora.astimezone(FUSO) if agora.tzinfo else agora
    return f"abako-{ambiente}-{local:%Y%m%d-%H%M%S}{SUFIXO}"


def ler_nome(nome: str) -> tuple[str, datetime] | None:
    """(ambiente, instante civil) de um nome de backup; `None` se não seguir o padrão."""
    m = RE_NOME.match(nome)
    if not m:
        return None
    try:
        instante = datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return m.group(1), instante


def selecionar_retencao(
    instantes: Iterable[datetime], diarios: int = DIARIOS, semanais: int = SEMANAIS
) -> set[datetime]:
    """Instantes que ficam; o resto expira.

    - Diário: o backup mais recente de cada um dos `diarios` dias civis mais recentes que
      têm backup.
    - Semanal: o mais recente de cada uma das `semanais` semanas ISO mais recentes que têm
      backup, anteriores à semana do backup mais recente.
    As camadas se sobrepõem (união). Contar dias/semanas *com backup*, e não do calendário,
    evita apagar tudo depois de um período sem backups.
    """
    ordenados = sorted(set(instantes), reverse=True)
    manter: set[datetime] = set()
    if not ordenados:
        return manter
    dias: set[date] = set()
    for t in ordenados:
        if len(dias) >= diarios:
            break
        if t.date() not in dias:
            dias.add(t.date())
            manter.add(t)
    semana_atual = ordenados[0].isocalendar()[:2]
    semanas: set[tuple[int, int]] = set()
    for t in ordenados:
        semana = (t.isocalendar()[0], t.isocalendar()[1])
        if semana == semana_atual or semana in semanas:
            continue
        if len(semanas) >= semanais:
            break
        semanas.add(semana)
        manter.add(t)
    return manter


def expirados(nomes: Iterable[str], ambiente: str) -> list[str]:
    """Nomes de backup do `ambiente` que a retenção manda remover (ordem alfabética).

    Nomes fora do padrão ou de outro ambiente nunca entram na lista.
    """
    por_instante: dict[datetime, str] = {}
    for nome in nomes:
        lido = ler_nome(nome)
        if lido and lido[0] == ambiente:
            por_instante[lido[1]] = nome
    manter = selecionar_retencao(por_instante)
    return sorted(n for t, n in por_instante.items() if t not in manter)
