import { EstadoVazio, Pagina } from "../ui/componentes";

type Props = { titulo: string; descricao: string; texto: string };

/** Página reservada no menu: existe para fixar a navegação; o conteúdo vem depois. */
export function EmBreve({ titulo, descricao, texto }: Props) {
  return (
    <Pagina titulo={titulo} descricao={descricao}>
      <EstadoVazio titulo="Em breve" texto={texto} />
    </Pagina>
  );
}
