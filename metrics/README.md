# metrics/ — rastreamento de entregas

## entregas.jsonl

Uma linha JSON por task entregue. O `harness-build` appenda automaticamente ao fechar cada task.
O `/scorecard` lê este arquivo para calcular as métricas de entrega.

### Schema

```json
{
  "issue": 1,
  "titulo": "Título da task",
  "data": "2026-06-27",
  "criterios_aceite": {
    "total": 3,
    "atendidos": 3
  },
  "gate": {
    "resultado": "verde",
    "tentativas_ate_verde": 1
  },
  "revisor": {
    "veredito": "aprovado",
    "bloqueantes": 0,
    "ressalvas": 0
  },
  "intervencoes_humanas": 0,
  "commit": "abc1234",
  "evidencias_ref": ".claude/projetos/{slug}/evidencias/tasks/1.yaml"
}
```

### Campos

| Campo | Tipo | Descrição |
|---|---|---|
| `issue` | int | Número da task (NN do arquivo `tasks/{slug}/NN-*.md`) |
| `titulo` | string | Título da task |
| `data` | string | Data de fechamento (YYYY-MM-DD) |
| `criterios_aceite.total` | int | Total de critérios na task |
| `criterios_aceite.atendidos` | int | Critérios com evidência de aceite |
| `gate.resultado` | "verde"\|"vermelho" | Resultado final do /validar |
| `gate.tentativas_ate_verde` | int | Quantas vezes rodou /validar até passar |
| `revisor.veredito` | "aprovado"\|"aprovado com ressalvas"\|"bloqueado" | Veredito do revisor-codigo |
| `revisor.bloqueantes` | int | Número de bloqueantes encontrados |
| `revisor.ressalvas` | int | Número de ressalvas (não bloqueantes) |
| `intervencoes_humanas` | int | Quantas vezes o humano interveio mid-task |
| `commit` | string | SHA curto do commit de fechamento |
| `evidencias_ref` | string | **Obrigatório** — path relativo do manifesto `evidencias/tasks/<id>.yaml` (evidence-gate) |

### Métricas derivadas pelo /scorecard

- **Taxa de critérios atendidos**: `sum(atendidos) / sum(total)`
- **Tentativas medianas até gate verde**: mediana de `gate.tentativas_ate_verde`
- **Taxa de autonomia**: tasks com `intervencoes_humanas == 0` / total
- **Taxa de aprovação direta**: tasks com `revisor.veredito == "aprovado"` / total
- **Change-failure**: issues reabertas após fechamento (rastreado no GitHub Issues ou manualmente)

### Sinais lagging (fora do loop do agente)

Não entram no `entregas.jsonl` automaticamente — registre manualmente quando ocorrer:

```json
{"issue": 3, "titulo": "...", "change_failure": true, "razao": "bug encontrado em review humano"}
```

> Não persiga vaidade (linhas de código, nº de commits). O gate é alvo legítimo.
> Métrica de humano (review, bug escapado) não entra no que o agente otimiza.
