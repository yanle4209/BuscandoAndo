import './AnuncioCard.css';

/**
 * Tarjeta de anuncio para la celda destacada (2x2) de los resultados.
 *
 * Rellena el espacio cuando la busqueda no tiene destacado de pago que
 * mostrar — la web lo decide: destacado primero, anuncio rellena
 * (DISENO.md a1). La tarjeta entera es el enlace (target _blank): un
 * anuncio sin clic no es anuncio. El borde ambar y la pastilla
 * ANUNCIO la separan de un destacado pagado (borde verde).
 */
export default function AnuncioCard({ anuncio }) {
  return (
    <a
      className="anuncio-card"
      href={anuncio.enlace}
      target="_blank"
      rel="noopener noreferrer"
      title={anuncio.titulo}
    >
      <div className="anuncio-card__media">
        <img src={anuncio.imagen_url} alt={anuncio.titulo} />
      </div>
      <div className="anuncio-card__body">
        <span className="anuncio-card__badge">Anuncio</span>
        <h3 className="anuncio-card__titulo">{anuncio.titulo}</h3>
        <span className="anuncio-card__cta">
          Ir al anuncio
          <span aria-hidden="true"> →</span>
        </span>
      </div>
    </a>
  );
}
