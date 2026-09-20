import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/axios';
import MapView from '../components/MapView';
import './BusinessDetail.css';

const DAY_NAMES = {
  L: 'Lunes', M: 'Martes', X: 'Miércoles',
  J: 'Jueves', V: 'Viernes', S: 'Sábado', D: 'Domingo',
};

export default function BusinessDetail() {
  const { slug } = useParams();
  const [biz, setBiz] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    api.get(`/businesses/${slug}/`)
      .then(({ data }) => setBiz(data))
      .catch(() => setError('No se encontró el negocio.'))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) return <div className="detail-page"><p className="detail-loading">Cargando...</p></div>;
  if (error) return (
    <div className="detail-page">
      <div className="detail-error">
        <p>{error}</p>
        <Link to="/" className="detail-back">← Volver al inicio</Link>
      </div>
    </div>
  );

  const loc = biz.location || {};
  const contact = biz.contact || {};
  const hours = biz.hours || [];

  const address = [loc.street, loc.sector, loc.municipality, loc.district, loc.province]
    .filter(Boolean).join(', ');

  return (
    <div className="detail-page">
      <div className="detail-left">
        <Link to="/" className="detail-back">← Volver</Link>

        <h1 className="detail-name">{biz.name}</h1>

        {biz.category_name && (
          <span className="detail-category">{biz.category_name}</span>
        )}

        <span className={`detail-status detail-status--${biz.operational_status_name?.toLowerCase().replace(/\s/g, '-')}`}>
          {biz.operational_status_name}
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
                  <span className="detail-hours-day">{DAY_NAMES[h.day] || h.day}</span>
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
          <MapView
            businesses={[biz]}
            selected={biz}
            center={[biz.latitude, biz.longitude]}
            onMarkerClick={() => {}}
          />
        ) : (
          <div className="detail-no-map">Sin ubicación en mapa</div>
        )}
      </div>
    </div>
  );
}
