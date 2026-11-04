// Peças base da interface. Toda tela é montada com elas, para o padrão visual nascer num
// lugar só (o design final do usuário troca os estilos, não a estrutura).
import type { ReactNode } from "react";

type PaginaProps = { titulo: string; descricao?: string; children: ReactNode };

/** Moldura de toda página: título, texto de apoio e conteúdo. */
export function Pagina({ titulo, descricao, children }: PaginaProps) {
  return (
    <section className="pagina">
      <header className="pagina-cabecalho">
        <h1>{titulo}</h1>
        {descricao !== undefined && <p>{descricao}</p>}
      </header>
      {children}
    </section>
  );
}

export function Cartao({ titulo, children }: { titulo?: string; children: ReactNode }) {
  return (
    <div className="cartao">
      {titulo !== undefined && <h2>{titulo}</h2>}
      {children}
    </div>
  );
}

/** Estado "carregando": avisa leitores de tela sem mexer no foco. */
export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return (
    <p className="estado estado-carregando" role="status">
      <span className="giro" aria-hidden="true" />
      {texto}
    </p>
  );
}

type EstadoVazioProps = { titulo: string; texto: string };

/** Estado "vazio": nada a mostrar ainda (ou a tela chega numa próxima etapa). */
export function EstadoVazio({ titulo, texto }: EstadoVazioProps) {
  return (
    <div className="estado estado-vazio">
      <strong>{titulo}</strong>
      <p>{texto}</p>
    </div>
  );
}

type MensagemErroProps = { texto: string; aoTentarDeNovo?: () => void };

/** Estado "erro": diz o que houve e, se der, oferece tentar de novo. */
export function MensagemErro({ texto, aoTentarDeNovo }: MensagemErroProps) {
  return (
    <div className="estado estado-erro" role="alert">
      <p>{texto}</p>
      {aoTentarDeNovo !== undefined && (
        <button type="button" className="botao botao-secundario" onClick={aoTentarDeNovo}>
          Tentar de novo
        </button>
      )}
    </div>
  );
}
