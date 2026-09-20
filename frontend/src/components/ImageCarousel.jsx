import { useState } from 'react';

export default function ImageCarousel({ images }) {
  const [current, setCurrent] = useState(0);
  if (!images || images.length === 0) return null;

  const prev = (e) => { e.stopPropagation(); setCurrent(c => c === 0 ? images.length - 1 : c - 1); };
  const next = (e) => { e.stopPropagation(); setCurrent(c => c === images.length - 1 ? 0 : c + 1); };

  return (
    <div className="biz-card__images">
      <div className="biz-card__images-track" style={{ transform: `translateX(-${current * 100}%)` }}>
        {images.map((img, i) => (
          <img key={img.id || i} src={img.image_url || img.image} alt={img.caption || ''} loading="lazy" />
        ))}
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
