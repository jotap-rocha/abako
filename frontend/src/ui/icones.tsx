// Ícones de traço simples (24x24, herdam a cor do texto). Decorativos: ficam escondidos para
// leitores de tela; o texto ao lado diz o que é. SVG como elemento JSX não conflita com a CSP.
import type { ReactNode } from "react";

function Icone({ children }: { children: ReactNode }) {
  return (
    <svg
      className="icone"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const IconeInicio = () => (
  <Icone>
    <path d="M4 11.5 12 5l8 6.5" />
    <path d="M6 10.5V19h12v-8.5" />
  </Icone>
);

export const IconeContas = () => (
  <Icone>
    <rect x="3.5" y="6" width="17" height="12" rx="2.5" />
    <path d="M3.5 10h17" />
    <path d="M7 14.5h3" />
  </Icone>
);

export const IconeLancamentos = () => (
  <Icone>
    <path d="M8 6h11M8 12h11M8 18h11" />
    <path d="M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
  </Icone>
);

export const IconeAlertas = () => (
  <Icone>
    <path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.5h-15L6 16.5Z" />
    <path d="M10 20.5a2 2 0 0 0 4 0" />
  </Icone>
);

export const IconeSair = () => (
  <Icone>
    <path d="M14 5H7.5A1.5 1.5 0 0 0 6 6.5v11A1.5 1.5 0 0 0 7.5 19H14" />
    <path d="m17 8.5 3.5 3.5-3.5 3.5M20.5 12H10" />
  </Icone>
);

export const IconeOlho = () => (
  <Icone>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="2.8" />
  </Icone>
);

export const IconeOlhoRiscado = () => (
  <Icone>
    <path d="M4 4l16 16" />
    <path d="M9.9 6A9.4 9.4 0 0 1 12 5.5C18 5.5 21.5 12 21.5 12a17 17 0 0 1-3.2 4" />
    <path d="M6.2 7.8A17 17 0 0 0 2.5 12S6 18.5 12 18.5a9.6 9.6 0 0 0 3.8-.8" />
  </Icone>
);

export const IconeCartoes = () => (
  <Icone>
    <rect x="3" y="5.5" width="18" height="13" rx="2.5" />
    <path d="M3 10h18" />
    <path d="M6.5 15h4" />
  </Icone>
);

export const IconeGasto = () => (
  <Icone>
    <path d="M5 19V11M12 19V5M19 19v-6" />
  </Icone>
);

export const IconeReserva = () => (
  <Icone>
    <path d="M12 3.5 5 6v5.5c0 4.2 2.8 7.2 7 9 4.2-1.8 7-4.8 7-9V6l-7-2.5Z" />
  </Icone>
);

export const IconeSobra = () => (
  <Icone>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5v9M9.5 10c0-1 1-1.7 2.5-1.7s2.5.7 2.5 1.7-1 1.5-2.5 1.9S9.5 13 9.5 14s1 1.7 2.5 1.7 2.5-.7 2.5-1.7" />
  </Icone>
);
