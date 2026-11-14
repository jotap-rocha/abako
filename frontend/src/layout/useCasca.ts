import { useOutletContext } from "react-router";

import type { ContextoCasca } from "./Casca";

/** O que a casca entrega às páginas (hoje: o aviso de sessão vencida). */
export function useCasca(): ContextoCasca {
  return useOutletContext<ContextoCasca>();
}
