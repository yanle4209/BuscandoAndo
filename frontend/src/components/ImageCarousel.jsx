import { useState, useEffect, useCallback } from 'react';

export default function ImageCarousel({ images, autoplay = false }) {
  const [current, setCurrent] = useState(0);
  const [paused, setPaused] = useState(false);
  if (!images || images.length === 0) return null;

  const prev = (e) => { e.stopPropagation(); setCurrent(c => c === 0 ? images.length - 1 : c - 1); };
  const next = (e) => { e.stopPropagation(); setCurrent(c => c === images.length - 1 ? 0 : c + 1); };

  useEffect(() => {
    if (!autoplay || images.length <= 1 || paused) return;
    const id = setInterval(() => {
      setCurrent(c => c === images.length - 1 ? 0 : c + 1);
    }, 3000);
    return () => clearInterval(id);
  }, [autoplay, paused, images.length]);

  return (
    <div className="biz-card__images" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      <div className="biz-card__images-viewport">
        <div className="biz-card__images-track" style={{ transform: `translateX(-${current * 100}%)` }}>
          {images.map((img, i) => (
            <img key={img.id || i} src={img.image_url || img.image} alt={img.caption || ''} />
          ))}
        </div>
      </div>
      {images.length > 1 && (
        <>
          <div className="biz-card__images-arrows">
            <button className="biz-card__images-arrow" onClick={prev}>‹</button>
            <button className="biz-card__images-arrow" onClick={next}>›</button>
          </div>
          <div className="biz-card__images-nav">
            {images.map((_, i) => (
              <button key={i} className={`biz-card__images-dot${i === current ? ' biz-card__images-dot--active' : ''}`} onClick={(e) => { e.stopPropagation(); setCurrent(i); }} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
