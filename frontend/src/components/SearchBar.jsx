import { useState, useEffect, useMemo } from 'react';
import { claveCabecera } from '../municipios';
import './SearchBar.css';

export default function SearchBar({
  filters,
  onSearch,
  onGeolocate,
  hasSearched,
  cabeceras,
  municipioClave,
  onMunicipio,
  // Las categorias las pide Home y llegan por aqui: esta barra se monta
  // DOS veces (escritorio y movil, una la esconde el CSS) y con estado
  // propio cada instancia hacia SU peticion a /categories/ — dos idas y
  // vuelta por el mismo listado en cada carga de la portada.
  categories = [],
  // Solo la barra de escritorio la pide. Las dos montan a la vez y el
  // ultimo montado se llevaba el foco: era la MOVIL, que en telefono
  // abria el teclado al cargar.
  autoFocus = false,
}) {
  const [text, setText] = useState(filters.text || '');
  const [showFilters, setShowFilters] = useState(false);

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
            autoFocus={autoFocus}
          />
          <button type="submit" className="search-btn">Buscar</button>
        </div>
      </form>

      <div className="search-actions">
        {hasSearched && (
          <button
            className="filter-toggle"
            onClick={() => setShowFilters(!showFilters)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
            </svg>
            Filtros
          </button>
        )}
        <button className="geo-btn" onClick={onGeolocate}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
          </svg>
          Mi ubicación
        </button>
      </div>

      {/* R1.1: sin GPS, elegir municipio es OBLIGATORIO. Por eso no vive
          dentro de "Filtros" (que solo se abre tras buscar): quien niegue la
          ubicacion tiene que llegar al selector en un toque, si no se queda
          mirando el overlay sin salida. Sustituye al viejo filtro "Ciudad"
          por nombre: la ciudad ahora son coordenadas + 5 km (R3.5). */}
      <div className="filter-group municipio-group">
        <label>Municipio</label>
        {/* aria-label (y no label[for]: Home monta esta barra DOS
            veces, escritorio y movil, y los ids duplicados no valen):
            sin esto el select no tiene nombre accesible — el label de
            arriba no esta asociado. */}
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

      {showFilters && (
        <div className="filters-panel">
          <div className="filter-group">
            <label>Categoría</label>
            {/* Mismo motivo que el de municipio: nombre accesible sin
                ids duplicados. */}
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
          {/* El radio ya no se elige: R1.3 lo fija en 5 km en las dos
              plataformas y el backend lo acota por arriba. */}
        </div>
      )}
    </div>
  );
}
