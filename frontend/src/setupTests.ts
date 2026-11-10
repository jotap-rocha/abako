import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// Com vários arquivos rodando em paralelo, a primeira renderização pode passar de 1 s; o
// `findBy*` espera até 5 s antes de falhar (o teste continua falhando se a tela não aparecer).
configure({ asyncUtilTimeout: 5000 });
