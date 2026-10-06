import { useState, useEffect } from 'react';
import './MapOverlay.css';

// Ninguna frase puede nombrar un municipio: el overlay se ve en los 158
// (y en los que todavia no tienen fichas cargadas).
const MESSAGES = [
  'Encuentra los mejores negocios cerca de ti',
  'Restaurantes, tiendas, servicios y mas',
  'Descubre lo que tu comunidad tiene para ofrecer',
  'Tu guia de negocios en toda la República',
  'Conecta con los mejores profesionales',
  'Explora tu municipio como nunca antes',
];

export default function MapOverlay({ visible, hint }) {
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
            <circle cx="60" cy="60" r="55" fill="none" stroke="#6f6f14" strokeWidth="2" className="map-overlay__circle" />
            <circle cx="60" cy="60" r="45" fill="none" stroke="#6f6f14" strokeWidth="1" opacity="0.35" className="map-overlay__circle-inner" />
            {/* Pin icon. El transform de posicion va en un g AYUDANTE: el
               CSS de .map-overlay__pin anima transform y pisa el atributo,
               y el chinchete se iba a la esquina superior izquierda. */}
            <g transform="translate(60, 35)">
              <g className="map-overlay__pin">
                <path d="M0,-20 C-11,-20 -20,-11 -20,0 C-20,13 0,30 0,30 C0,30 20,13 20,0 C20,-11 11,-20 0,-20Z"
                  fill="var(--yellow)" stroke="#543335" strokeWidth="2" opacity="0.95" />
                <circle cx="0" cy="-2" r="7" fill="var(--dark)" />
              </g>
            </g>
            {/* Pulse rings */}
            <circle cx="60" cy="63" r="8" fill="none" stroke="#6f6f14" strokeWidth="1.5" className="map-overlay__pulse" />
            <circle cx="60" cy="63" r="8" fill="none" stroke="#6f6f14" strokeWidth="1" className="map-overlay__pulse map-overlay__pulse--delay" />
          </svg>
          <h2 className="map-overlay__title">
            Buscando<span>Ando</span>
          </h2>
        </div>

        {/* Rotating message */}
        <p className={`map-overlay__message ${fadeOut ? 'map-overlay__message--fade' : ''}`}>
          {MESSAGES[msgIndex]}
        </p>

        {/* Sin punto activo no hay radio que trazar: hace falta decirle al
            usuario que esa es la unica salida (R1.1). */}
        {hint && <p className="map-overlay__hint">{hint}</p>}

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
