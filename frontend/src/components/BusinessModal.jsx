import { useEffect } from 'react';
import ImageCarousel from './ImageCarousel';
import './BusinessModal.css';

const DAY_NAMES = {
  L: 'Lunes', M: 'Martes', X: 'Miercoles',
  J: 'Jueves', V: 'Viernes', S: 'Sabado', D: 'Domingo',
};

export default function BusinessModal({ business, onClose }) {
  useEffect(() => {
    const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEsc);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  if (!business) return null;

  const loc = business.location || {};
  const contact = business.contact || {};
  const hours = business.hours || [];
  const images = business.images || [];
  const phone = business.phone || contact.phone;
  const whatsapp = business.whatsapp || contact.whatsapp;
  const email = business.email || contact.email;
  const website = contact.website;
  const contactPerson = business.contact_person || contact.contact_person;
  const address = [business.street || loc.street, business.sector || loc.sector, business.municipality || loc.municipality, business.province || loc.province]
    .filter(Boolean).join(', ');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="20" height="20">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>

        {/* Image carousel */}
        {images.length > 0 && (
          <div className="modal-carousel">
            <ImageCarousel images={images} />
          </div>
        )}

        <div className="modal-body">
          {/* Header */}
          <div className="modal-header">
            <div className="modal-header-top">
              <h1 className="modal-name">{business.name}</h1>
              <div className="modal-badges">
                {business.is_featured && <span className="modal-badge modal-badge--featured">Destacado</span>}
              </div>
            </div>
            <div className="modal-meta">
              {business.category_name && (
                <span className="modal-category">{business.category_name}</span>
              )}
              <span className={`modal-status modal-status--${business.effective_status || business.operational_status_slug || 'default'}`}>
                {business.effective_status_name || business.operational_status_name || 'Sin estado'}
              </span>
            </div>
          </div>

          {/* Description */}
          {(business.description || business.short_description) && (
            <p className="modal-desc">{business.description || business.short_description}</p>
          )}

          {/* Info grid */}
          <div className="modal-info-grid">
            {/* Ubicacion */}
            <div className="modal-info-card">
              <div className="modal-info-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
                </svg>
              </div>
              <div className="modal-info-content">
                <span className="modal-info-label">Ubicacion</span>
                {address ? <span className="modal-info-value">{address}</span> : <span className="modal-info-empty">Sin direccion</span>}
              </div>
            </div>

            {/* Contacto */}
            <div className="modal-info-card">
              <div className="modal-info-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
                </svg>
              </div>
              <div className="modal-info-content">
                <span className="modal-info-label">Contacto</span>
                <div className="modal-contact-links">
                  {phone && <a href={`tel:${phone}`} className="modal-link">{phone}</a>}
                  {whatsapp && <a href={`https://wa.me/${whatsapp.replace(/\D/g, '')}`} target="_blank" rel="noopener" className="modal-link modal-link--wa">WhatsApp</a>}
                  {email && <a href={`mailto:${email}`} className="modal-link">{email}</a>}
                  {website && <a href={website} target="_blank" rel="noopener" className="modal-link">Sitio web</a>}
                  {!phone && !whatsapp && !email && !website && <span className="modal-info-empty">Sin datos</span>}
                </div>
              </div>
            </div>

            {/* Responsable */}
            {contactPerson && (
              <div className="modal-info-card">
                <div className="modal-info-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                  </svg>
                </div>
                <div className="modal-info-content">
                  <span className="modal-info-label">Responsable</span>
                  <span className="modal-info-value">{contactPerson}</span>
                </div>
              </div>
            )}

            {/* Horarios */}
            {hours.length > 0 && (
              <div className="modal-info-card modal-info-card--full">
                <div className="modal-info-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                  </svg>
                </div>
                <div className="modal-info-content">
                  <span className="modal-info-label">Horarios</span>
                  <div className="modal-hours">
                    {hours.map((h) => (
                      <div key={h.day} className="modal-hour-row">
                        <span className="modal-hour-day">{DAY_NAMES[h.day] || h.day}</span>
                        {h.is_closed ? (
                          <span className="modal-hour-closed">Cerrado</span>
                        ) : h.is_holiday ? (
                          <span className="modal-hour-closed">Fiesta</span>
                        ) : (
                          <span className="modal-hour-time">{h.open_time} - {h.close_time}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Google Maps link */}
          {business.latitude && business.longitude && (
            <a
              href={`https://www.google.com/maps?q=${business.latitude},${business.longitude}`}
              target="_blank"
              rel="noopener noreferrer"
              className="modal-map-link"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
              </svg>
              Ver en Google Maps
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
