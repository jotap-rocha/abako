// A chave de idempotência (INV-28) identifica um envio: o formulário gera uma por lançamento
// e repete a mesma se o usuário tentar de novo depois de uma falha, para o servidor não duplicar.
// 8 a 64 caracteres entre letras, números, "-" e "_".

export function novaChave(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // Navegador sem randomUUID: 16 bytes aleatórios em hexadecimal.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
