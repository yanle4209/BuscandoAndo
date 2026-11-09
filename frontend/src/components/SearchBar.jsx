import { useState, useEffect, useMemo } from 'react';
import { claveCabecera } from '../municipios';
import './SearchBar.css';

/**
 * Barra de busqueda del Home, en una sola linea bajo la cabecera:
 * Municipio · Categoria · buscador · Mi ubicacion.
 *
 * El mapa ya no vive en el Home: solo aparece dentro de la ficha
 * completa. El punto de consulta se elige con el municipio o con el GPS.
 */
export default function SearchBar({
  filters,
  onSearch,
  onGeolocate,
  hasSearched,
  cabeceras,
  municipioClave,
  onMunicipio,
  // Las categorias las pide Home y llegan por aqui: la barra no hace
  // peticiones propias.
  categories = [],
}) {
  const [text, setText] = useState(filters.text || '');

  // El texto se borra desde fuera cuando R3.2 resetea la busqueda: sin
  // esto el input se quedaria con la busqueda que el sistema acaba de borrar.
  useEffect(() => {
    setText(filters.text || '');
  }, [filters.text]);

  useEffect(() => {
    if (text === '' && hasSearched) {
      onSearch({ text: '' });
    }
  }, [text]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch({ text });
  };

  const handleCategoryChange = (e) => {
    onSearch({ category: e.target.value });
  };

  // Las cabeceras llegan planas del API y se agrupan aqui: la agrupacion
  // por provincia es cosa de la interfaz, no del backend.
  const porProvincia = useMemo(() => {
    const grupos = new Map();
    (cabeceras || []).forEach((c) => {
      if (!grupos.has(c.provincia)) grupos.set(c.provincia, []);
      grupos.get(c.provincia).push(c);
    });
    return Array.from(grupos.entries())
      .map(([provincia, lista]) => ({
        provincia,
        lista: lista.slice()
          .sort((a, b) => a.municipio.localeCompare(b.municipio, 'es')),
      }))
      .sort((a, b) => a.provincia.localeCompare(b.provincia, 'es'));
  }, [cabeceras]);

  return (
    <div className="search-bar-container">
      {/* R1.1: sin GPS, elegir municipio es OBLIGATORIO. Por eso no vive
          detras de un boton "Filtros": quien niegue la ubicacion tiene que
          llegar al selector en un toque. */}
      <div className="filter-group municipio-group">
        <label>Municipio</label>
        {/* aria-label (y no label[for]): el select mantiene nombre
            accesible sin depender de ids. */}
        <select
          aria-label="Municipio"
          value={municipioClave}
          onChange={(e) => onMunicipio(e.target.value)}
        >
          <option value="">Elige tu municipio</option>
          {porProvincia.map((grupo) => (
            <optgroup key={grupo.provincia} label={grupo.provincia}>
              {grupo.lista.map((c) => (
                <option key={claveCabecera(c)} value={claveCabecera(c)}>
                  {c.municipio}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {/* Categoria siempre visible: forma parte del "menu" en linea. */}
      <div className="filter-group categoria-group">
        <label>Categoría</label>
        <select
          aria-label="Categoría"
          value={filters.category}
          onChange={handleCategoryChange}
        >
          <option value="">Todas</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>{cat.name}</option>
          ))}
        </select>
      </div>

      <form onSubmit={handleSubmit} className="search-form">
        <div className="search-input-wrapper">
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            type="text"
            className="search-input"
            placeholder="Buscar negocio, categoría o dirección..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" className="search-btn">Buscar</button>
        </div>
      </form>

      <button type="button" className="geo-btn" onClick={onGeolocate}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
        </svg>
        Mi ubicación
      </button>
    </div>
  );
}
