import { useState, useEffect } from 'react';
import './MapOverlay.css';

const MESSAGES = [
  'Encuentra los mejores negocios de Moca',
  'Restaurantes, tiendas, servicios y mas',
  'Descubre lo que tu comunidad tiene para ofrecer',
  'Tu guia de negocios en Espaillat',
  'Conecta con los mejores profesionales',
  'Explora Moca como nunca antes',
];

export default function MapOverlay({ visible }) {
  const [msgIndex, setMsgIndex] = useState(0);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    if (!visible) return;
    const interval = setInterval(() => {
      setFadeOut(true);
      setTimeout(() => {
        setMsgIndex(prev => (prev + 1) % MESSAGES.length);
        setFadeOut(false);
      }, 400);
    }, 3500);
    return () => clearInterval(interval);
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="map-overlay">
      <div className="map-overlay__content">
        {/* Animated logo */}
        <div className="map-overlay__logo">
          <svg viewBox="0 0 120 120" className="map-overlay__icon">
            <circle cx="60" cy="60" r="55" fill="none" stroke="var(--yellow)" strokeWidth="2" className="map-overlay__circle" />
            <circle cx="60" cy="60" r="45" fill="none" stroke="var(--yellow)" strokeWidth="1" opacity="0.3" className="map-overlay__circle-inner" />
            {/* Pin icon */}
            <g transform="translate(60, 35)" className="map-overlay__pin">
              <path d="M0,-20 C-11,-20 -20,-11 -20,0 C-20,13 0,30 0,30 C0,30 20,13 20,0 C20,-11 11,-20 0,-20Z"
                fill="var(--yellow)" opacity="0.9" />
              <circle cx="0" cy="-2" r="7" fill="var(--dark)" />
            </g>
            {/* Pulse rings */}
            <circle cx="60" cy="63" r="8" fill="none" stroke="var(--yellow)" strokeWidth="1.5" className="map-overlay__pulse" />
            <circle cx="60" cy="63" r="8" fill="none" stroke="var(--yellow)" strokeWidth="1" className="map-overlay__pulse map-overlay__pulse--delay" />
          </svg>
          <h2 className="map-overlay__title">
            Buscando<span>Ando</span>
          </h2>
        </div>

        {/* Rotating message */}
        <p className={`map-overlay__message ${fadeOut ? 'map-overlay__message--fade' : ''}`}>
          {MESSAGES[msgIndex]}
        </p>

        {/* Decorative dots */}
        <div className="map-overlay__dots">
          {MESSAGES.map((_, i) => (
            <span key={i} className={`map-overlay__dot ${i === msgIndex ? 'map-overlay__dot--active' : ''}`} />
          ))}
        </div>
      </div>
    </div>
  );
}
