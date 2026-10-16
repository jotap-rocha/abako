# Padrões vitest + Testing Library

## Setup

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    coverage: {
      provider: "v8",
      thresholds: { lines: 80, functions: 80 },
    },
  },
})
```

```typescript
// src/test/setup.ts
import "@testing-library/jest-dom"
import { cleanup } from "@testing-library/react"
import { afterEach, vi } from "vitest"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// Mock do cliente Supabase para testes de componente
vi.mock("@/lib/supabase", () => ({
  supabase: {
    from: vi.fn().mockReturnThis(),
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    order: vi.fn().mockResolvedValue({ data: [], error: null }),
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  },
}))
```

## Componente React — padrão AAA

```typescript
// src/components/__tests__/CasoCard.test.tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { CasoCard } from "../CasoCard"

const mockCaso = {
  id: "caso-1",
  titulo: "Fraude em sinistro",
  status: "em_analise" as const,
  risco: "alto" as const,
}

describe("CasoCard", () => {
  it("renderiza título e status", () => {
    // Arrange
    render(<CasoCard caso={mockCaso} />)

    // Assert
    expect(screen.getByText("Fraude em sinistro")).toBeInTheDocument()
    expect(screen.getByText("em_analise")).toBeInTheDocument()
  })

  it("chama onSelect com o id correto ao clicar", async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<CasoCard caso={mockCaso} onSelect={onSelect} />)

    await user.click(screen.getByRole("button", { name: /selecionar/i }))

    expect(onSelect).toHaveBeenCalledOnce()
    expect(onSelect).toHaveBeenCalledWith("caso-1")
  })
})
```

## Hook customizado — testar isolado

```typescript
// src/hooks/__tests__/useCasos.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { useCasos } from "../useCasos"
import { supabase } from "@/lib/supabase"

vi.mock("@/lib/supabase")

describe("useCasos", () => {
  beforeEach(() => {
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({
          data: [{ id: "1", titulo: "Caso A" }],
          error: null,
        }),
      }),
    } as any)
  })

  it("retorna casos do tenant", async () => {
    const { result } = renderHook(() => useCasos("tenant-1"))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.casos).toHaveLength(1)
    expect(result.current.casos[0].titulo).toBe("Caso A")
  })

  it("expõe erro quando a query falha", async () => {
    vi.mocked(supabase.from).mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({ data: null, error: { message: "DB Error" } }),
      }),
    } as any)

    const { result } = renderHook(() => useCasos("tenant-1"))
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.error).toBeTruthy()
    expect(result.current.casos).toEqual([])
  })
})
```

## Queries por acessibilidade (não por CSS class)

```typescript
// RUIM: frágil — quebra se renomear a classe
screen.getByClassName("btn-primary")
container.querySelector(".card-title")

// BOM: por papel acessível
screen.getByRole("button", { name: /confirmar/i })
screen.getByRole("heading", { name: /casos de fraude/i })
screen.getByLabelText(/status/i)
screen.getByPlaceholderText(/buscar casos/i)
screen.getByTestId("risco-badge")  // último recurso: data-testid
```

## Rodar vitest

```bash
# Watch mode (desenvolvimento)
npx vitest

# CI (uma vez)
npx vitest run

# Com coverage
npx vitest run --coverage
```
