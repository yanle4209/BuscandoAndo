import './AnuncioCard.css';

/**
 * Tarjeta de anuncio con VIDEO para la celda destacada (2x2).
 *
 * Es el negocio marcado "Anuncio de video" en el panel: en la celda
 * deja de salir como tarjeta normal y su espacio es su video
 * (DISENO.md a1 — la celda es destacado > video > imagen). Mismo
 * borde ámbar y misma pastilla ANUNCIO que el anuncio de imagen; lo
 * que cambia es la foto: ahora es un <video> que arranca solo en
 * silencio, con controles para subir el sonido.
 *
 * La ficha se abre con su propio botón, no envolviendo la tarjeta:
 * los controles del video necesitan los clicks para pausar y subir
 * volumen.
 */
export default function AnuncioVideoCard({ anuncio, onVerFicha }) {
  return (
    <article className="anuncio-card anuncio-card--video">
      <div className="anuncio-card__media">
        <video
          src={anuncio.video_url}
          poster={anuncio.poster_url || undefined}
          autoPlay
          muted
          loop
          playsInline
          controls
        />
      </div>
      <div className="anuncio-card__body">
        <span className="anuncio-card__badge">Anuncio</span>
        <h3 className="anuncio-card__titulo">{anuncio.name}</h3>
        <button
          type="button"
          className="anuncio-card__cta"
          onClick={() => onVerFicha(anuncio)}
        >
          Ver ficha<span aria-hidden="true"> →</span>
        </button>
      </div>
    </article>
  );
}
