import { useState, useEffect } from 'react';
import api from '../api/axios';
import './SearchBar.css';

export default function SearchBar({ filters, onSearch, onGeolocate, hasSearched }) {
  const [text, setText] = useState(filters.text || '');
  const [categories, setCategories] = useState([]);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    api.get('/categories/')
      .then(({ data }) => setCategories(data.results || data))
      .catch(() => {});
  }, []);

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

  const handleRadiusChange = (e) => {
    onSearch({ radius: parseInt(e.target.value) });
  };

  const handleCityChange = (e) => {
    onSearch({ city: e.target.value });
  };

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
            autoFocus
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

      {showFilters && (
        <div className="filters-panel">
          <div className="filter-group">
            <label>Categoría</label>
            <select value={filters.category} onChange={handleCategoryChange}>
              <option value="">Todas</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label>Ciudad</label>
            <input
              type="text"
              placeholder="ej. Santo Domingo"
              value={filters.city}
              onChange={handleCityChange}
            />
          </div>
          <div className="filter-group">
            <label>Radio: {filters.radius} km</label>
            <input
              type="range"
              min="1"
              max="20"
              value={filters.radius}
              onChange={handleRadiusChange}
            />
          </div>
        </div>
      )}
    </div>
  );
}
