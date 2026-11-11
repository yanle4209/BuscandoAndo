import { useEffect, useState } from 'react';
import api from '../api/axios';
import './HeroCollage.css';

// R1.3: mismo radio fijo de 5 km que el resto del buscador.
const RADIO_KM = 5;
const HUECOS = 5;

// Orden de importancia de los huecos: el 1 (2x2) es el nivel 1; el 5
// (ancho inferior) el nivel 2; despues 2, 3 y 4. Los datos llegan
// ordenados por nivel (destacados primero), asi que el item 0 va al
// hueco grande y el item 1 al ancho de abajo.
const ORDEN = [0, 2, 3, 4, 1];

/**
 * Portada del Home una vez elegido municipio/GPS y antes de buscar.
 *
 * Pide los destacados dentro de los 5 km y, si no hay cinco, completa
 * con los negocios mas recientes de la zona. Cada hueco abre su ficha;
 * la jerarquia (grande / ancho / pequenos) es la del grid de referencia.
 */
export default function HeroCollage({ punto, lugar, onOpen, onVerTodos }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!punto) return undefined;
    let cancelado = false;
    setLoading(true);

    const base = { lat: punto.lat, lng: punto.lng, radius: RADIO_KM };

    Promise.all([
      // Hasta 3 destacados activos dentro del radio, por nivel.
      api.get('/businesses/featured-by-search/', { params: base })
        .then(({ data }) => (Array.isArray(data) ? data : []))
        .catch(() => []),
      // Relleno: los negocios mas recientes de la zona.
      api.get('/businesses/', { params: base })
        .then(({ data }) => data.results || [])
        .catch(() => []),
    ]).then(([destacados, cercanos]) => {
      if (cancelado) return;
      const vistos = new Set();
      const lista = [];
      [...destacados, ...cercanos].forEach((biz) => {
        const clave = biz.id ?? biz.slug;
        if (vistos.has(clave)) return;
        vistos.add(clave);
        lista.push(biz);
      });
      setItems(lista.slice(0, HUECOS));
      setLoading(false);
    });

    return () => { cancelado = true; };
  }, [punto]);

  const tiles = ORDEN.map((i) => items[i] || null);

  return (
    <section className="hero-collage" aria-label="Negocios destacados">
      <div className="hero-collage__copy">
        <span className="hero-collage__kicker">
          {lugar ? `Destacados en ${lugar}` : 'Destacados cerca de ti'}
        </span>
        <h2 className="hero-collage__title">
          Negocios que <em>destacan</em> en tu zona
        </h2>
        <p className="hero-collage__lede">
          Una muestra de lo que hay a menos de 5 km. Abre una ficha para
          ver sus datos, horarios y ubicación.
        </p>
        <div className="hero-collage__actions">
          <button type="button" className="hero-collage__cta" onClick={onVerTodos}>
            Ver todos los negocios →
          </button>
          <span className="hero-collage__nota">o elige una categoría arriba</span>
        </div>
      </div>

      <div className="hero-collage__grid">
        {loading ? (
          Array.from({ length: HUECOS }, (_, i) => (
            <div
              key={`hueco-${i + 1}`}
              className={`hero-collage__tile hero-collage__tile--${i + 1} hero-collage__tile--cargando`}
              aria-hidden="true"
            />
          ))
        ) : items.length === 0 ? (
          <div className="hero-collage__vacio">
            <strong>Todavía no hay fichas cerca de aquí.</strong>
            <span>Prueba con otro municipio o vuelve pronto: estamos creciendo.</span>
          </div>
        ) : (
          tiles.map((biz, idx) => {
            const n = idx + 1;
            if (!biz) {
              return (
                <div
                  key={`vacio-${n}`}
                  className={`hero-collage__tile hero-collage__tile--${n} hero-collage__tile--vacio`}
                  aria-hidden="true"
                />
              );
            }
            const foto = biz.images?.[0]?.image_url;
            const categoria = biz.category_name || '';
            return (
              <button
                key={biz.id ?? biz.slug}
                type="button"
                className={`hero-collage__tile hero-collage__tile--${n}${foto ? '' : ' hero-collage__tile--sin-foto'}`}
                style={foto ? { backgroundImage: `url("${foto}")` } : undefined}
                onClick={() => onOpen(biz)}
                aria-label={`Abrir ficha de ${biz.name}${categoria ? `, ${categoria}` : ''}`}
              >
                {categoria && <span className="hero-collage__pill">{categoria}</span>}
                <span className="hero-collage__label">{biz.name}</span>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}
