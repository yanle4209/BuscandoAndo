import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './MapView.css';

// Fix default marker icons in Leaflet + bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const YELLOW_ICON = L.divIcon({
  className: 'custom-marker',
  html: `<div style="width:14px;height:14px;background:#FBBF24;border:2px solid #1f1a1a;border-radius:50%;box-shadow:0 0 6px rgba(251,191,36,0.5);"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const SELECTED_ICON = L.divIcon({
  className: 'custom-marker',
  html: `<div style="width:20px;height:20px;background:#FBBF24;border:3px solid #fff;border-radius:50%;box-shadow:0 0 12px rgba(251,191,36,0.7);"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const USER_ICON = L.divIcon({
  className: 'custom-marker',
  html: `<div style="width:12px;height:12px;background:#4285f4;border:2px solid #fff;border-radius:50%;box-shadow:0 0 8px rgba(66,133,244,0.6);"></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

// Vista por defecto mientras no hay punto activo (sin municipio y sin
// GPS): el mapa se abre mirando el pais entero. No es un "punto", asi
// que no lleva marcador de usuario.
const CENTRO_PAIS = [18.7357, -70.1627];
const ZOOM_PAIS = 8;

export default function MapView({ businesses, selected, center, onMarkerClick, onMapClick }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef([]);
  // true mientras el mapa siga en la vista del pais: el primer centro
  // que llegue entra con zoom de municipio (12), no con el 8 del pais.
  const sinCentroRef = useRef(!center);

  // Initialize map: siempre, con punto o sin el
  useEffect(() => {
    if (mapRef.current && !mapInstance.current) {
      mapInstance.current = L.map(mapRef.current, {
        center: center || CENTRO_PAIS,
        zoom: center ? 12 : ZOOM_PAIS,
        zoomControl: false,
      });

      L.control.zoom({ position: 'topright' }).addTo(mapInstance.current);

      // OpenStreetMap oficial (gratis, sin API key). Se cambiaba del
      // estilo "hot" de tile.openstreetmap.fr porque ahi las teselas
      // salian rotas (naturalWidth 0) y el mapa se quedaba gris.
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(mapInstance.current);

      mapInstance.current.on('click', (e) => {
        if (onMapClick) {
          onMapClick(e.latlng.lat, e.latlng.lng);
        }
      });
    }
  }, []);

  // Update markers
  useEffect(() => {
    if (!mapInstance.current) return;

    // Clear old markers
    markersRef.current.forEach((m) => mapInstance.current.removeLayer(m));
    markersRef.current = [];

    // Add user location marker
    if (center) {
      const userMarker = L.marker(center, { icon: USER_ICON })
        .addTo(mapInstance.current)
        .bindPopup('Tu ubicación');
      markersRef.current.push(userMarker);
    }

    // Add business markers
    businesses.forEach((biz) => {
      const lat = parseFloat(biz.latitude);
      const lng = parseFloat(biz.longitude);
      if (isNaN(lat) || isNaN(lng)) return;

      const isSelected = selected?.slug === biz.slug;
      const icon = isSelected ? SELECTED_ICON : YELLOW_ICON;

      const marker = L.marker([lat, lng], { icon })
        .addTo(mapInstance.current)
        .bindPopup(`<strong>${biz.name}</strong><br/>${biz.category_name || ''}`);

      marker.on('click', () => {
        if (onMarkerClick) onMarkerClick(biz);
      });

      markersRef.current.push(marker);
    });

    // Fit bounds if we have businesses
    if (businesses.length > 0) {
      const validCoords = businesses
        .map((b) => [parseFloat(b.latitude), parseFloat(b.longitude)])
        .filter(([lat, lng]) => !isNaN(lat) && !isNaN(lng));

      if (validCoords.length > 1) {
        mapInstance.current.fitBounds(validCoords, { padding: [40, 40] });
      }
    }
  }, [businesses, selected]);

  // Update center when the active point changes. Va DESPUES del efecto de
  // marcas a proposito: al refrescar cambian a la vez el punto y los
  // negocios, y el reciente del mapa (R2.1) tiene que ganarle al fitBounds.
  // Con center estable (useMemo en Home) esto solo salta en un refresco, no
  // en cada render, asi que se puede arrastrar el mapa.
  useEffect(() => {
    if (!mapInstance.current || !center) return;
    // Si el mapa arranco en la vista del pais (sin punto), el primer
    // centro entra a zoom de municipio; despues se respeta el zoom que
    // tenga el usuario.
    const desdeElPais = sinCentroRef.current;
    sinCentroRef.current = false;
    mapInstance.current.setView(center, desdeElPais ? 12 : mapInstance.current.getZoom());
  }, [center]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, []);

  return <div ref={mapRef} className="map-view" />;
}
