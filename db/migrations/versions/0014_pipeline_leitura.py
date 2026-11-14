"""EXECUTE mínimo das leituras para o pipeline analítico (SPEC-014, ADR 054)

Revision ID: 0014
Revises: 0013

SQL puro (ADR 025). Nenhuma tabela nem função nova: só `GRANT EXECUTE` ao `abako_pipeline` em
leituras `INVOKER` que já existem, para o pipeline consumir a regra financeira do SQL (ADR 015) em
vez de recalculá-la em Python.

- Rodam com os privilégios do pipeline, que já tem `SELECT` nas tabelas e views que elas leem
  (0002 a 0011); nenhuma ganha `SELECT` novo. `pessoa.nome` segue sem `SELECT` (ADR 045).
- Ficam de fora: toda função de escrita, `alertas`, as de R2, as do vale e a `receita_*`.
- As funções auxiliares entram porque quem chama precisa de `EXECUTE` em cada função que invoca
  (`fatura_resumo` chama `fatura_itens`; `reserva_situacao` chama `saldo_derivado` e
  as `reserva_*`).
- `fatura_itens` devolve `descricao`: o pipeline só a usa por dentro de `fatura_resumo` e nunca a
  seleciona (ADR 054 item 7).
- Downgrade só revoga (sem dado a perder).
"""

from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

FUNCOES = (
    "saldo_derivado(bigint, bigint, date)",
    "r4_divergencias(bigint)",
    "fatura_resumo(bigint, bigint, text)",
    "fatura_itens(bigint, bigint, text)",
    "limite_linha(bigint, bigint, date)",
    "a_receber_pessoas(bigint, bigint)",
    "mes_inicio(text)",
    "gasto_real_itens(bigint, text)",
    "gasto_real(bigint, text)",
    "gasto_real_por_conta(bigint, text)",
    "reserva_nivel(numeric, numeric)",
    "reserva_cobertura(numeric, numeric)",
    "reserva_aporte(numeric, integer)",
    "reserva_meses_ate(date, date)",
    "reserva_situacao(bigint, date)",
)


def upgrade() -> None:
    for assinatura in FUNCOES:
        op.execute(f"GRANT EXECUTE ON FUNCTION {assinatura} TO abako_pipeline")


def downgrade() -> None:
    for assinatura in FUNCOES:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {assinatura} FROM abako_pipeline")
