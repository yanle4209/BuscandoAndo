import { Suspense, lazy, useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/axios';
import { slugDeEstado, nombreDeEstado } from '../estado';
import './BusinessDetail.css';

// Code-splitting (DISENO.md 14.6): el mapa (Leaflet) en su propio chunk.
const MapView = lazy(() => import('../components/MapView'));

export default function BusinessDetail() {
  const { slug } = useParams();
  const [biz, setBiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // true = la API no contesto (sin red, timeout, 500) y reintentar sirve;
  // false = 404, el negocio no existe y volver a pulsar no cambia nada.
  const [reintentable, setReintentable] = useState(false);
  // Subirlo vuelve a hacer la peticion: no hay que repetir la logica.
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.get(`/businesses/${slug}/`)
      .then(({ data }) => setBiz(data))
      .catch((err) => {
        // Antes TODOS los fallos se informaban como "No se encontro el
        // negocio": un corte de red, un 500 o un timeout enseñaban un 404
        // inventado, y encima sin manera de reintentarlo.
        const es404 = err.response?.status === 404;
        setError(es404
          ? 'No se encontró el negocio.'
          : 'No se pudo cargar el negocio. Revisa tu conexión.');
        setReintentable(!es404);
      })
      .finally(() => setLoading(false));
  }, [slug, revision]);

  if (loading) return <main className="detail-page" id="contenido" tabIndex={-1}><p className="detail-loading">Cargando...</p></main>;
  if (error) return (
    <main className="detail-page" id="contenido" tabIndex={-1}>
      <div className="detail-error" role="alert">
        <p>{error}</p>
        {reintentable && (
          <button
            className="detail-retry"
            onClick={() => setRevision((n) => n + 1)}
          >
            Reintentar
          </button>
        )}
        <Link to="/" className="detail-back">← Volver al inicio</Link>
      </div>
    </main>
  );

  const loc = biz.location || {};
  const contact = biz.contact || {};
  const hours = biz.hours || [];

  const address = [loc.street, loc.sector, loc.municipality, loc.district, loc.province]
    .filter(Boolean).join(', ');

  return (
    // <main> con id para el "Saltar al contenido" (auditoria D).
    <main className="detail-page" id="contenido" tabIndex={-1}>
      <div className="detail-left">
        <Link to="/" className="detail-back">← Volver</Link>

        <h1 className="detail-name">{biz.name}</h1>

        {biz.category_name && (
          <span className="detail-category">{biz.category_name}</span>
        )}

        {/* Mismo estado que en la tarjeta y en el modal: manda el
            calculado con los horarios de hoy (effective_status), no el
            declarado en la base. */}
        <span className={`detail-status detail-status--${slugDeEstado(biz)}`}>
          {nombreDeEstado(biz)}
        </span>

        {biz.is_featured && <span className="detail-badge">⭐ Destacado</span>}

        <p className="detail-desc">{biz.description}</p>

        {/* Ubicación */}
        <section className="detail-section">
          <h2>📍 Ubicación</h2>
          {address && <p>{address}</p>}
          {loc.postal_code && <p className="detail-postal">CP: {loc.postal_code}</p>}
        </section>

        {/* Contacto */}
        <section className="detail-section">
          <h2>📞 Contacto</h2>
          {contact.phone && (
            <div className="detail-contact-row">
              <span>Teléfono:</span>
              <a href={`tel:${contact.phone}`}>{contact.phone}</a>
            </div>
          )}
          {contact.whatsapp && (
            <div className="detail-contact-row detail-contact-row--wa">
              <span>WhatsApp:</span>
              <a href={`https://wa.me/${contact.whatsapp.replace(/\D/g, '')}`} target="_blank" rel="noopener">
                {contact.whatsapp}
              </a>
            </div>
          )}
          {contact.email && (
            <div className="detail-contact-row">
              <span>Email:</span>
              <a href={`mailto:${contact.email}`}>{contact.email}</a>
            </div>
          )}
          {contact.website && (
            <div className="detail-contact-row">
              <span>Sitio web:</span>
              <a href={contact.website} target="_blank" rel="noopener">{contact.website}</a>
            </div>
          )}
        </section>

        {/* Horarios */}
        {hours.length > 0 && (
          <section className="detail-section">
            <h2>🕐 Horarios</h2>
            <div className="detail-hours">
              {hours.map((h) => (
                <div key={h.day} className="detail-hours-row">
                  {/* h.day llega completo del serializer ("Miércoles") */}
                  <span className="detail-hours-day">{h.day}</span>
                  {h.is_closed ? (
                    <span className="detail-hours-closed">Cerrado</span>
                  ) : (
                    <span className="detail-hours-time">{h.open_time} - {h.close_time}</span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="detail-right">
        {biz.latitude && biz.longitude ? (
          <Suspense
            fallback={
              <div className="mapa-cargando" role="status">
                Cargando mapa…
              </div>
            }
          >
            <MapView
              businesses={[biz]}
              selected={biz}
              center={[biz.latitude, biz.longitude]}
              onMarkerClick={() => {}}
            />
          </Suspense>
        ) : (
          <div className="detail-no-map">Sin ubicación en mapa</div>
        )}
      </div>
    </main>
  );
}
