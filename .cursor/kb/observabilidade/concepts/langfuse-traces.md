# Langfuse — Traces, Spans, Scores e Datasets

## Conceitos fundamentais

```
Trace      = uma execução completa (1 query do usuário → 1 resposta)
Span       = uma etapa dentro do trace (classify, search, generate)
Generation = span específico para chamada LLM (tem input/output/tokens/custo)
Score      = avaliação do trace (manual ou automática: 0–1)
Dataset    = coleção de inputs/outputs para avaliação e fine-tuning
```

## Setup

```python
# pyproject.toml
# langfuse = "^2.0"

from langfuse import Langfuse

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)
```

## Trace manual de uma run de agente

```python
from langfuse.decorators import observe, langfuse_context
import time

@observe(name="chat-pipeline")
async def process_query(query: str, session_id: str) -> dict:
    langfuse_context.update_current_trace(
        session_id=session_id,
        user_id=session_id,  # ou user_id real
        tags=["production"],
        metadata={"query_len": len(query)},
    )

    intent = await classify(query)
    result = await search_or_sql(intent, query)
    answer = await generate(result, query)

    return {"answer": answer, "sources": result.sources}

@observe(name="classify")
async def classify(query: str) -> str:
    # Langfuse captura automaticamente input/output do span
    ...

@observe(name="generate", as_type="generation")
async def generate(context: str, query: str) -> str:
    # as_type="generation" captura tokens e custo do LLM
    response = await llm.ainvoke(PROMPT.format(context=context, query=query))
    langfuse_context.update_current_observation(
        model="gpt-4o",
        usage={"input": response.usage.prompt_tokens,
               "output": response.usage.completion_tokens},
    )
    return response.content
```

## Integração LangChain/LangGraph

```python
from langfuse.callback import CallbackHandler

handler = CallbackHandler(
    public_key=LANGFUSE_PUBLIC_KEY,
    secret_key=LANGFUSE_SECRET_KEY,
    session_id=session_id,
    user_id=user_id,
    tags=["langgraph", "production"],
)

# Passar como callback no invoke
result = await app.ainvoke(
    initial_state,
    config={
        "configurable": {"thread_id": session_id},
        "callbacks": [handler],
    },
)
```

## Scores — avaliação de qualidade

```python
# Score automático (ex: após geração, verificar grounding)
langfuse.score(
    trace_id=trace.id,
    name="grounding",
    value=1.0 if has_source_cited(answer) else 0.0,
    comment="fonte citada na resposta" if has_source_cited(answer) else "sem grounding",
)

# Score manual (avaliação humana via API ou UI do Langfuse)
langfuse.score(
    trace_id=trace_id,
    name="relevance",
    value=0.8,
    data_type="NUMERIC",
)
```

## Datasets — golden set para evals

```python
# Criar dataset
dataset = langfuse.create_dataset(name="golden-queries-v1")

# Adicionar item ao dataset
langfuse.create_dataset_item(
    dataset_name="golden-queries-v1",
    input={"query": "quais produtos mais venderam no Q3?"},
    expected_output={"answer_contains": ["produto", "Q3", "vendas"]},
)

# Rodar eval contra dataset
for item in langfuse.get_dataset("golden-queries-v1").items:
    result = await process_query(item.input["query"], session_id="eval")
    item.link(trace_id=result["trace_id"], observation_id=None)

    score = evaluate_quality(result["answer"], item.expected_output)
    langfuse.score(trace_id=result["trace_id"], name="eval_quality", value=score)
```

## Flush ao encerrar (importante em scripts)

```python
# Em scripts/batch — sempre fazer flush antes de terminar
langfuse.flush()

# Em FastAPI — flush no shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    langfuse.flush()
```

## Variáveis de ambiente

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com  # ou self-hosted
```
