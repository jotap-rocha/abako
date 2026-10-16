# Padrão: Trace de Chamada LLM

## Decorator @observe (zero boilerplate)

```python
from langfuse.decorators import observe, langfuse_context

@observe(name="chat-pipeline", capture_input=True, capture_output=True)
async def run_pipeline(query: str, session_id: str) -> dict:
    langfuse_context.update_current_trace(
        session_id=session_id,
        user_id=session_id,
        tags=["production"],
    )
    # ... pipeline completo
    return result

@observe(name="classify-intent")
async def classify(query: str) -> str: ...

@observe(name="generate", as_type="generation")
async def generate(context: str, query: str) -> str:
    t0 = time.monotonic()
    response = await llm.ainvoke(prompt)
    langfuse_context.update_current_observation(
        model="gpt-4o",
        input=prompt,
        output=response.content,
        usage={
            "input":  response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
            "total":  response.usage.total_tokens,
        },
        metadata={"latency_ms": int((time.monotonic() - t0) * 1000)},
    )
    return response.content
```

## LangChain Callback (automático para LangGraph)

```python
from langfuse.callback import CallbackHandler

def make_langfuse_handler(session_id: str, user_id: str) -> CallbackHandler:
    return CallbackHandler(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        session_id=session_id,
        user_id=user_id,
        tags=["langgraph", "production"],
        metadata={"version": APP_VERSION},
    )

# No nó do grafo ou no invoke:
handler = make_langfuse_handler(session_id, user_id)
result = await app.ainvoke(state, config={"callbacks": [handler]})
```

## Trace manual (máximo controle)

```python
from langfuse import Langfuse
import time

langfuse = Langfuse()

async def traced_pipeline(query: str, session_id: str) -> dict:
    trace = langfuse.trace(
        name="chat-pipeline",
        session_id=session_id,
        input={"query": query},
        tags=["production"],
    )

    # Span de classificação
    classify_span = trace.span(name="classify", input={"query": query})
    intent = await classify(query)
    classify_span.end(output={"intent": intent})

    # Generation (LLM call)
    t0 = time.monotonic()
    gen = trace.generation(
        name="generate",
        model="gpt-4o",
        input=[{"role": "user", "content": build_prompt(query, context)}],
    )
    response = await llm.ainvoke(build_prompt(query, context))
    gen.end(
        output=response.content,
        usage={"input": response.usage.prompt_tokens,
               "output": response.usage.completion_tokens},
        metadata={"latency_ms": int((time.monotonic() - t0) * 1000)},
    )

    # Fechar trace
    trace.update(
        output={"answer": response.content},
        metadata={"intent": intent},
    )
    langfuse.flush()

    return {"answer": response.content, "trace_id": trace.id}
```

## Score automático de grounding

```python
def score_grounding(trace_id: str, answer: str, sources: list[str]) -> float:
    has_grounding = bool(sources) and any(s in answer for s in sources)
    score = 1.0 if has_grounding else 0.0

    langfuse.score(
        trace_id=trace_id,
        name="grounding",
        value=score,
        comment="fontes citadas" if has_grounding else "sem grounding detectado",
    )
    return score
```

## Configuração de ambiente

```bash
# .env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Self-hosted (docker-compose)
LANGFUSE_HOST=http://langfuse:3000
```

## Checklist de trace

- [ ] `session_id` presente em todo trace
- [ ] Chamadas LLM têm `usage` (tokens) — necessário para análise de custo
- [ ] `langfuse.flush()` chamado no shutdown da aplicação
- [ ] Scores de grounding gravados após cada geração
- [ ] `capture_input=False` em dados sensíveis (PII na query)
