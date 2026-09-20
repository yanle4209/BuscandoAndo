import { useEffect } from 'react';
import ImageCarousel from './ImageCarousel';
import './BusinessModal.css';

const DAY_NAMES = {
  L: 'Lunes', M: 'Martes', X: 'Miércoles',
  J: 'Jueves', V: 'Viernes', S: 'Sábado', D: 'Domingo',
};

export default function BusinessModal({ business, onClose }) {
  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  if (!business) return null;

  const loc = business.location || {};
  const contact = business.contact || {};
  const hours = business.hours || [];
  const phone = business.phone || contact.phone;
  const whatsapp = business.whatsapp || contact.whatsapp;
  const email = business.email || contact.email;
  const website = contact.website;
  const address = [business.street || loc.street, business.sector || loc.sector, business.municipality || loc.municipality, business.district || loc.district, business.province || loc.province, loc.postal_code]
    .filter(Boolean).join(', ');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>

        <div className="modal-header">
          <h1 className="modal-name">{business.name}</h1>
          {business.is_featured && <span className="modal-badge">⭐ Destacado</span>}
        </div>

        {business.category_name && (
          <span className="modal-category">{business.category_name}</span>
        )}

        <span className={`modal-status modal-status--${business.operational_status_slug || 'default'}`}>
          {business.operational_status_name || 'Sin estado'}
        </span>

        {business.images && business.images.length > 0 && (
          <div className="modal-images">
            <ImageCarousel images={business.images} />
          </div>
        )}

        {(business.description || business.short_description) && (
          <p className="modal-desc">{business.description || business.short_description}</p>
        )}

        <div className="modal-grid">
          {/* Ubicación */}
          <section className="modal-section">
            <h2>📍 Ubicación</h2>
            {address ? <p>{address}</p> : <p className="modal-no-data">Sin dirección registrada</p>}
          </section>

          {/* Contacto */}
          <section className="modal-section">
            <h2>📞 Contacto</h2>
            <div className="modal-contacts">
              {phone && (
                <div className="modal-contact-row">
                  <span className="modal-contact-label">Teléfono</span>
                  <a href={`tel:${phone}`}>{phone}</a>
                </div>
              )}
              {whatsapp && (
                <div className="modal-contact-row modal-contact-row--wa">
                  <span className="modal-contact-label">WhatsApp</span>
                  <a href={`https://wa.me/${whatsapp.replace(/\D/g, '')}`} target="_blank" rel="noopener">{whatsapp}</a>
                </div>
              )}
              {email && (
                <div className="modal-contact-row">
                  <span className="modal-contact-label">Email</span>
                  <a href={`mailto:${email}`}>{email}</a>
                </div>
              )}
              {website && (
                <div className="modal-contact-row">
                  <span className="modal-contact-label">Web</span>
                  <a href={website} target="_blank" rel="noopener">{website}</a>
                </div>
              )}
              {!phone && !whatsapp && !email && !website && (
                <p className="modal-no-data">Sin datos de contacto</p>
              )}
            </div>
          </section>
        </div>

        {/* Horarios */}
        {hours.length > 0 && (
          <section className="modal-section modal-section--hours">
            <h2>🕐 Horarios</h2>
            <div className="modal-hours-grid">
              {hours.map((h) => (
                <div key={h.day} className="modal-hours-row">
                  <span className="modal-hours-day">{DAY_NAMES[h.day] || h.day}</span>
                  {h.is_closed ? (
                    <span className="modal-hours-closed">Cerrado</span>
                  ) : (
                    <span className="modal-hours-time">{h.open_time} - {h.close_time}</span>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
