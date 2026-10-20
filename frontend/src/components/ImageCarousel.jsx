import { useState, useEffect } from 'react';

export default function ImageCarousel({ images, autoplay = false, altBase = '' }) {
  const [current, setCurrent] = useState(0);
  const [paused, setPaused] = useState(false);
  const total = images?.length || 0;

  // Hooks SIEMPRE en el mismo orden: el early-return va DESPUES de
  // useEffect (si no, pasar de "sin imagenes" a "con imagenes" con el
  // componente montado cambiaba el numero de hooks y React reventaba).
  useEffect(() => {
    if (!autoplay || total <= 1 || paused) return;
    const id = setInterval(() => {
      setCurrent(c => c === total - 1 ? 0 : c + 1);
    }, 3000);
    return () => clearInterval(id);
  }, [autoplay, paused, total]);

  if (total === 0) return null;

  return (
    <div className="biz-card__images" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="biz-card__images-viewport">
        <div className="biz-card__images-track" style={{ transform: `translateX(-${current * 100}%)` }}>
          {images.map((img, i) => (
            <img
              key={img.id || i}
              src={img.image_url || img.image}
              // Accesibilidad (auditoria D): el caption no existe en la
              // API, asi que sin altBase las fotos quedaban en silencio
              // para el lector de pantalla. El alt lo arma quien
              // conoce el negocio (tarjeta y modal).
              alt={img.caption || altBase}
              loading="lazy"
              decoding="async"
            />
          ))}
        </div>
      </div>
      {images.length > 1 && (
        <>
          <div className="biz-card__images-arrows">
            <button className="biz-card__images-arrow" onClick={prev} aria-label="Foto anterior">‹</button>
            <button className="biz-card__images-arrow" onClick={next} aria-label="Foto siguiente">›</button>
          </div>
          <div className="biz-card__images-nav">
            {images.map((_, i) => (
              <button key={i} aria-label={`Foto ${i + 1} de ${images.length}`} className={`biz-card__images-dot${i === current ? ' biz-card__images-dot--active' : ''}`} onClick={(e) => { e.stopPropagation(); setCurrent(i); }} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
