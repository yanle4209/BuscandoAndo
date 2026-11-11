import { Fragment, Suspense, lazy, useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/axios';
import { slugDeEstado, nombreDeEstado } from '../estado';
import { partirTelefono } from '../telefono';
import ImageCarousel from '../components/ImageCarousel';
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

  // Cada peticion se numera, igual que en Home: si cambia el slug (o se
  // pide un reintento) mientras la anterior vuela, la respuesta VIEJA se
  // tira en vez de pisar la buena. Sin esto, dos navegaciones rapidas de
  // /business/a a /business/b podian acabar mostrando la ficha de "a".
  const peticionRef = useRef(0);

  useEffect(() => {
    const peticion = peticionRef.current + 1;
    peticionRef.current = peticion;
    const vigente = () => peticionRef.current === peticion;
    setLoading(true);
    setError(null);
    api.get(`/businesses/${slug}/`)
      .then(({ data }) => {
        if (vigente()) setBiz(data);
      })
      .catch((err) => {
        // Antes TODOS los fallos se informaban como "No se encontro el
        // negocio": un corte de red, un 500 o un timeout enseñaban un 404
        // inventado, y encima sin manera de reintentarlo.
        if (!vigente()) return;
        const es404 = err.response?.status === 404;
        setError(es404
          ? 'No se encontró el negocio.'
          : 'No se pudo cargar el negocio. Revisa tu conexión.');
        setReintentable(!es404);
      })
      .finally(() => {
        // El "cargando" solo se apaga si esta peticion sigue mandando; si
        // no, la vieja lo apagaria mientras la nueva aun vuela.
        if (vigente()) setLoading(false);
      });
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
  const images = biz.images || [];
  // Varios numeros en una sola cadena: cada uno con su enlace tel:.
  const telefonos = partirTelefono(contact.phone);
  const hours = biz.hours || [];

  const address = [loc.street, loc.sector, loc.municipality, loc.district, loc.province]
    .filter(Boolean).join(', ');

  const municipio = loc.municipality || '';
  const altBase = [biz.name, biz.category_name].filter(Boolean).join(' – ')
    + (municipio ? ` en ${municipio}` : '');

  return (
    // <main> con id para el "Saltar al contenido" (auditoria D).
    <main className="detail-page" id="contenido" tabIndex={-1}>
      <div className="detail-left">
        <Link to="/" className="detail-back">← Volver</Link>

        {/* Galería de imágenes ARRIBA, limpia (sin texto encima). */}
        {images.length > 0 && (
          <div className="detail-gallery">
            <ImageCarousel images={images} altBase={altBase} />
          </div>
        )}

        {/* Nombre DEBAJO de la imagen, como título. */}
        <h1 className="detail-name">{biz.name}</h1>

        <div className="detail-meta">
          {biz.category_name && (
            <span className="detail-category">{biz.category_name}</span>
          )}
          {/* Mismo estado que en la tarjeta y en el modal: manda el
              calculado con los horarios de hoy (effective_status), no el
              declarado en la base. */}
          <span className={`detail-status detail-status--${slugDeEstado(biz)}`}>
            {nombreDeEstado(biz)}
          </span>
          {biz.is_featured && <span className="detail-badge">Destacado</span>}
        </div>

        <p className="detail-desc">{biz.description}</p>

        {/* Teléfono prominente: el dato estrella del directorio. */}
        {telefonos.length > 0 && (
          <div className="detail-phone">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
            </svg>
            <span className="detail-phone-nums">
              {telefonos.map((n, i) => (
                <Fragment key={n}>
                  {i > 0 ? ' · ' : ''}
                  <a href={`tel:${n}`}>{n}</a>
                </Fragment>
              ))}
            </span>
          </div>
        )}

        {/* Ubicación */}
        <section className="detail-section">
          <h2>Ubicación</h2>
          {address && <p className="detail-section-text">{address}</p>}
          {loc.postal_code && <p className="detail-postal">CP: {loc.postal_code}</p>}
        </section>

        {/* Contacto */}
        <section className="detail-section">
          <h2>Contacto</h2>
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
            <h2>Horarios</h2>
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
