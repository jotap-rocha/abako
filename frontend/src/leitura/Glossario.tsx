import { useId, useState, type ReactNode } from "react";

// Explicações em linguagem direta dos termos das telas de leitura. Vêm do glossário do projeto
// (CONTEXT.md); aqui só se explica, nunca se calcula.
export const TERMOS = {
  competencia: {
    nome: "Competência",
    texto:
      "O mês da fatura a que uma compra pertence. Uma compra de 5 de março pode cair na fatura de " +
      "abril se o cartão já tiver fechado: vale o mês da fatura, não a data da compra.",
  },
  fatura_aberta_fechada: {
    nome: "Fatura aberta ou fechada",
    texto:
      "Aberta: ainda não chegou o dia de fechamento, então novas compras podem entrar. Fechada: o " +
      "dia de fechamento já passou e a fatura não recebe mais compras. Pagar a fatura não muda isso.",
  },
  fatura_propria: {
    nome: "Fatura própria",
    texto: "A parte da fatura que é gasto seu. É o que entra nos seus gastos e na sobra.",
  },
  fatura_terceiros: {
    nome: "Terceiros",
    texto:
      "Compras que você fez no seu cartão para outra pessoa. Entram na fatura e no limite usado, " +
      "mas não são gasto seu: ficam como valor a receber dela.",
  },
  credito_estorno: {
    nome: "Crédito de estorno",
    texto:
      "Valor devolvido por uma compra estornada, que reduz a fatura. Aparece com sinal de menos " +
      "porque abate o total, e não é uma parcela.",
  },
  limite_usado: {
    nome: "Limite usado",
    texto:
      "Quanto da linha de crédito já está comprometido: o total das compras ainda não pagas, " +
      "inclusive as parcelas dos próximos meses. Vários cartões podem dividir a mesma linha. " +
      "O disponível pode ficar negativo: nada bloqueia a compra.",
  },
  gasto_real: {
    nome: "Gasto real",
    texto:
      "O que você gastou de fato no mês, contado pelas parcelas da fatura do mês. Não entram " +
      "transferências, investimentos, repasses, rendimentos, pagamento de fatura, compras de " +
      "terceiros nem contas de benefício.",
  },
  receita_caixa: {
    nome: "Receita de caixa",
    texto: "O dinheiro que entrou nas suas contas no mês. Não inclui contas de benefício.",
  },
  cobertura: {
    nome: "Cobertura da reserva",
    texto:
      "Por quantos meses a sua reserva paga o gasto essencial: saldo da reserva dividido pelo " +
      "gasto essencial de um mês.",
  },
  nivel_reserva: {
    nome: "Nível da reserva",
    texto:
      "Crítica: a reserva tem menos da metade da meta. Atenção: tem de metade até quase toda a " +
      "meta. Saudável: atingiu a meta. Quem decide o nível é o servidor.",
  },
  saldo_liquido: {
    nome: "Saldo líquido e bruto",
    texto:
      "Bruto é o que a reserva rendeu e guardou antes do imposto; líquido é o que sobra depois de " +
      "descontar o imposto já acumulado.",
  },
  aporte: {
    nome: "Aporte mensal",
    texto: "Quanto guardar por mês na reserva para chegar à meta até a data-alvo.",
  },
  horizonte: {
    nome: "Horizonte",
    texto:
      "Quantos dias à frente a sobra olha. Só entram contas e recebimentos com data dentro desse " +
      "prazo, contado a partir de hoje.",
  },
  disponivel: {
    nome: "Disponível",
    texto:
      "Saldo das contas correntes mais as receitas esperadas dentro do horizonte. Não inclui " +
      "reserva, vale nem crédito do vale.",
  },
  compromissos: {
    nome: "Compromissos",
    texto:
      "Contas fixas e faturas próprias que vencem dentro do horizonte e ainda não foram pagas. " +
      "Faturas de terceiros ficam de fora.",
  },
  sobra: {
    nome: "Sobra",
    texto:
      "Disponível menos compromissos no horizonte. Se ficar negativa, falta dinheiro para o que " +
      "vence nos próximos dias.",
  },
  parcial: {
    nome: "Fatura parcial",
    texto:
      "A fatura ainda está aberta, então o valor mostrado é só o que já foi comprado até agora. " +
      "Pode aumentar até o fechamento.",
  },
  vencidas: {
    nome: "Vencidas",
    texto:
      "Contas fixas com data já passada e sem lançamento ligado a elas. Ficam numa lista à parte " +
      "e não entram na sobra.",
  },
  sobra_nao_confiavel: {
    nome: "Sobra não confiável",
    texto:
      "Há um cartão com dívida sem dia de vencimento ou de fechamento cadastrado, então o abako " +
      "não sabe se a fatura vence dentro do horizonte. O número pode estar errado.",
  },
  snapshot: {
    nome: "Snapshot (saldo informado)",
    texto:
      "O saldo que você digita olhando o app do banco. Serve de ponto de conferência: o abako " +
      "compara com o que ele calculou.",
  },
  divergencia: {
    nome: "Divergência",
    texto:
      "Diferença entre o saldo calculado pelo abako e o saldo que você informou. Nada é corrigido " +
      "sozinho: o alerta fica até você conferir os lançamentos.",
  },
} as const;

export type IdTermo = keyof typeof TERMOS;

/**
 * Palavra técnica com explicação sob demanda. É um botão (funciona com teclado e leitor de
 * tela): ao ativar, a explicação aparece logo abaixo e o botão avisa que está expandido.
 */
export function Termo({ id, children }: { id: IdTermo; children?: ReactNode }) {
  const [aberto, setAberto] = useState(false);
  const idExplicacao = useId();
  const termo = TERMOS[id];
  return (
    <span className="termo">
      <button
        type="button"
        className="termo-botao"
        aria-expanded={aberto}
        aria-controls={idExplicacao}
        onClick={() => setAberto((valor) => !valor)}
      >
        {children ?? termo.nome}
        <span className="so-leitor"> (o que significa?)</span>
      </button>
      {/* Sempre no DOM (o `aria-controls` do botão aponta para ele); `hidden` o esconde de
          todos, inclusive de leitores de tela, até o botão abrir. */}
      <span id={idExplicacao} className="termo-explicacao" role="note" hidden={!aberto}>
        <strong>{termo.nome}:</strong> {termo.texto}
      </span>
    </span>
  );
}

/** Lista fixa no fim da página com as explicações dos termos usados nela. */
export function Glossario({ termos }: { termos: IdTermo[] }) {
  return (
    <details className="glossario">
      <summary>O que significam estes termos?</summary>
      <dl>
        {termos.map((id) => (
          <div key={id}>
            <dt>{TERMOS[id].nome}</dt>
            <dd>{TERMOS[id].texto}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
