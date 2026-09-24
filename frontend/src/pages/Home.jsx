import { useState, useEffect, useCallback } from 'react';
import SearchBar from '../components/SearchBar';
import MapView from '../components/MapView';
import BusinessCard from '../components/BusinessCard';
import BusinessModal from '../components/BusinessModal';
import MapOverlay from '../components/MapOverlay';
import api from '../api/axios';
import './Home.css';

const DR_CENTER = [18.7357, -70.1627];

// Grid: 4 cols x 3 rows = 12 cards per page
// Positions 0, 3, 5, 9 (0-indexed) are highlighted with yellow shadow
// Level mapping: Pos 1=Nivel 1, Pos 4=Nivel 2, Pos 6=Nivel 3, Pos 10=Nivel 4
const POSITION_LEVEL_MAP = {
  0: '1',  // Pos 1 → Nivel 1
  3: '2',  // Pos 4 → Nivel 2
  5: '3',  // Pos 6 → Nivel 3
  9: '4',  // Pos 10 → Nivel 4
};

function paginateFeatured(allFeatured) {
  const pages = [];
  for (let i = 0; i < allFeatured.length; i += 12) {
    pages.push(allFeatured.slice(i, i + 12));
  }
  return pages.length > 0 ? pages : [[]];
}

function assignGrid(businesses) {
  return businesses.map((biz, i) => ({
    ...biz,
    _highlighted: i in POSITION_LEVEL_MAP,
    _level: POSITION_LEVEL_MAP[i] || null,
    _position: i + 1,
  }));
}

export default function Home() {
  const [businesses, setBusinesses] = useState([]);
  const [allFeatured, setAllFeatured] = useState([]);
  const [featuredPages, setFeaturedPages] = useState([]);
  const [searchFeatured, setSearchFeatured] = useState([]);
  const [selected, setSelected] = useState(null);
  const [modalBiz, setModalBiz] = useState(null);
  const [showContact, setShowContact] = useState(false);
  const [loading, setLoading] = useState(false);
  const [userLocation, setUserLocation] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [featuredPage, setFeaturedPage] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [filters, setFilters] = useState({
    text: '', category: '', city: '', lat: '', lng: '', radius: 10,
  });

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(loc);
          setFilters(prev => ({ ...prev, lat: loc.lat, lng: loc.lng }));
        },
        () => setUserLocation({ lat: DR_CENTER[0], lng: DR_CENTER[1] })
      );
    } else {
      setUserLocation({ lat: DR_CENTER[0], lng: DR_CENTER[1] });
    }
  }, []);

  // Load all featured for homepage grid; if none, load recent businesses as fallback
  useEffect(() => {
    api.get('/businesses/', { params: { featured: 'true', page_size: 50 } })
      .then(({ data }) => {
        let results = data.results || [];
        if (results.length === 0) {
          return api.get('/businesses/', { params: { page_size: 15 } });
        }
        return { data: { results } };
      })
      .then(({ data }) => {
        const results = data.results || [];
        setAllFeatured(results);
        setFeaturedPages(paginateFeatured(results));
      })
      .catch(() => {});
  }, []);

  const fetchBusinesses = useCallback(async (pageNum = 1) => {
    setLoading(true);
    try {
      const params = { page: pageNum };
      if (filters.text) params.text = filters.text;
      if (filters.category) params.category = filters.category;
      if (filters.city) params.city = filters.city;
      if (filters.lat) params.lat = filters.lat;
      if (filters.lng) params.lng = filters.lng;
      if (filters.radius) params.radius = filters.radius;
      const { data } = await api.get('/businesses/', { params });
      setBusinesses(data.results || []);
      setTotalResults(data.count || 0);
      setTotalPages(Math.ceil((data.count || 0) / 9));

      // Fetch featured by search
      const searchParams = {};
      if (filters.text) searchParams.text = filters.text;
      if (filters.category) searchParams.category = filters.category;
      if (filters.city) searchParams.city = filters.city;
      try {
        const { data: featData } = await api.get('/businesses/featured-by-search/', { params: searchParams });
        setSearchFeatured(Array.isArray(featData) ? featData : []);
      } catch {
        setSearchFeatured([]);
      }
    } catch (err) {
      console.error('Error fetching businesses:', err);
      setBusinesses([]);
      setTotalResults(0);
      setTotalPages(1);
      setSearchFeatured([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    if (hasSearched) fetchBusinesses(page);
  }, [fetchBusinesses, hasSearched, page]);

  const handleSearch = (newFilters) => {
    if (newFilters.text === '' && !newFilters.category && !newFilters.city) {
      setHasSearched(false);
      setBusinesses([]);
      setSearchFeatured([]);
      setPage(1);
      return;
    }
    setFilters(prev => ({ ...prev, ...newFilters }));
    setPage(1);
    setHasSearched(true);
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
    document.querySelector('.right-panel')?.scrollTo(0, 0);
  };

  const handleFeaturedPageChange = (newPage) => {
    setFeaturedPage(newPage);
    document.querySelector('.right-panel')?.scrollTo(0, 0);
  };

  // Current page of featured businesses for bento grid
  const currentFeatured = featuredPages[featuredPage] || [];
  const displayedGrid = assignGrid(currentFeatured);
  const featuredTotalPages = featuredPages.length;

  // Map shows current page featured + search results
  const mapBusinesses = hasSearched ? businesses : currentFeatured;

  return (
    <div className="home-layout">
      <div className="left-panel">
        <div className="sidebar-top">
          <button className="contact-link" onClick={() => setShowContact(true)}>Contactanos</button>
        </div>
        <SearchBar
          filters={filters}
          onSearch={handleSearch}
          hasSearched={hasSearched}
          onGeolocate={() => {
            if (userLocation) {
              setFilters(prev => ({ ...prev, lat: userLocation.lat, lng: userLocation.lng }));
              setHasSearched(true);
            }
          }}
        />
        <div className="sidebar-map">
          <MapOverlay visible={!hasSearched} />
          {!hasSearched ? null : (
          <MapView
            businesses={mapBusinesses}
            selected={selected}
            center={userLocation ? [userLocation.lat, userLocation.lng] : DR_CENTER}
            onMarkerClick={(biz) => setModalBiz(biz)}
            onMapClick={(lat, lng) => setFilters(prev => ({ ...prev, lat, lng }))}
          />
          )}
        </div>
      </div>

      <div className="right-panel">
        <div className={`right-brand ${hasSearched ? 'right-brand--compact' : ''}`}>
          <h1 className="right-brand-title" onClick={() => window.location.reload()} style={{ cursor: 'pointer' }}>Buscando<span className="right-brand-accent">Ando</span></h1>
        </div>

        {/* Mobile search bar */}
        <div className="mobile-search">
          <SearchBar
            filters={filters}
            onSearch={handleSearch}
            hasSearched={hasSearched}
            onGeolocate={() => {
              if (userLocation) {
                setFilters(prev => ({ ...prev, lat: userLocation.lat, lng: userLocation.lng }));
                setHasSearched(true);
              }
            }}
          />
        </div>

        {hasSearched ? (
          <>
            <div className="right-section-header">
              <h2>{loading ? 'Buscando...' : `${totalResults} resultado${totalResults !== 1 ? 's' : ''}`}</h2>
            </div>
            <div className="right-results-scroll">
              {/* 3 Featured by category */}
              {searchFeatured.length > 0 && (
                <div className="search-featured-top">
                  {searchFeatured.map((biz) => (
                    <BusinessCard
                      key={biz.id || biz.slug}
                      business={biz}
                      onClick={() => setModalBiz(biz)}
                    />
                  ))}
                </div>
              )}

              {/* Regular results */}
              <div className="right-results-list">
                {businesses.map((biz) => (
                  <BusinessCard
                    key={biz.id || biz.slug}
                    business={biz}
                    onClick={() => setModalBiz(biz)}
                  />
                ))}
                {!loading && businesses.length === 0 && searchFeatured.length === 0 && (
                  <div className="no-results">
                    <p>No se encontraron negocios.</p>
                    <p className="no-results-hint">Intenta buscar algo diferente.</p>
                  </div>
                )}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="pagination">
                  <button className="pagination-btn" disabled={page <= 1} onClick={() => handlePageChange(page - 1)}>Anterior</button>
                  <span className="pagination-info">{page} / {totalPages}</span>
                  <button className="pagination-btn" disabled={page >= totalPages} onClick={() => handlePageChange(page + 1)}>Siguiente</button>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="right-bento-grid">
              {displayedGrid.map((biz) => (
                <BusinessCard
                  key={biz.id || biz.slug}
                  business={biz}
                  highlighted={biz._highlighted}
                  level={biz._level}
                  onClick={() => setModalBiz(biz)}
                />
              ))}
              {displayedGrid.length === 0 && (
                <div className="no-results">
                  <p>No hay negocios destacados.</p>
                </div>
              )}
            </div>
            {featuredTotalPages > 1 && (
              <div className="pagination">
                <button className="pagination-btn" disabled={featuredPage <= 0} onClick={() => handleFeaturedPageChange(featuredPage - 1)}>Anterior</button>
                <span className="pagination-info">{featuredPage + 1} / {featuredTotalPages}</span>
                <button className="pagination-btn" disabled={featuredPage >= featuredTotalPages - 1} onClick={() => handleFeaturedPageChange(featuredPage + 1)}>Siguiente</button>
              </div>
            )}
          </>
        )}
      </div>

      {modalBiz && <BusinessModal business={modalBiz} onClose={() => setModalBiz(null)} />}

      {showContact && (
        <div className="modal-overlay" onClick={() => setShowContact(false)}>
          <div className="modal-content modal-contact" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowContact(false)}>&#10005;</button>
            <h2 className="modal-contact-title">Contactanos</h2>
            <p className="modal-contact-desc">Si quieres anunciarte o comunicarte para cualquier otra sugerencia</p>
            <div className="modal-contact-info">
              <div className="modal-contact-row">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
                <a href="mailto:herlingrodriguez@gmail.com">herlingrodriguez@gmail.com</a>
              </div>
              <div className="modal-contact-row">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
                </svg>
                <a href="tel:8093537242">809-353-7242</a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
