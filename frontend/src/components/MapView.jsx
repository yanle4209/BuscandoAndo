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

      // Dos fuentes en cadena: Esri World Street Map -> OSM oficial.
      // CARTO se ha quitado de la cadena: sus teselas raster ya no
      // son gratis sin clave y devuelven un placeholder "API KEY
      // REQUIRED" con HTTP 200, o sea que el <img> dispara "load" y
      // el mapa se quedaria enseñando ese mensaje sin que salte
      // tileerror nunca. OSM oficial va el segundo, no el primero:
      // sus servidores de voluntarios bloquean a algunos clientes
      // con una IMAGEN valida (franjas y "403 Access blocked"), que
      // tambien dispara "load" y no "error". (tile.openstreetmap.fr/
      // hot, la fuente original, daba 403 fijo.)
      // Si fallan las dos se avisa en el propio mapa: nunca un gris.
      const fuentes = [
        {
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
          attribution: '&copy; <a href="https://www.esri.com/">Esri</a>, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        },
        {
          url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        },
      ];

      // El aviso va fuera de React: Leaflet limpia el contenedor al
      // crearse, y asi el mensaje no depende de un estado.
      mapRef.current.querySelectorAll('.map-view__aviso').forEach((n) => n.remove());
      const aviso = document.createElement('div');
      aviso.className = 'map-view__aviso';
      aviso.textContent = 'No se pudieron cargar las teselas del mapa (403 o red bloqueada): puede ser un bloqueador o la red del equipo. Recarga la pagina.';
      aviso.style.display = 'none';
      mapRef.current.appendChild(aviso);

      let fallos = 0;
      const montar = (i) => {
        const l = L.tileLayer(fuentes[i].url, {
          attribution: fuentes[i].attribution,
          maxZoom: 19,
        }).addTo(mapInstance.current);
        l.on('tileerror', () => {
          fallos += 1;
          if (fallos < 4) return;
          fallos = 0;
          mapInstance.current.removeLayer(l);
          if (i + 1 >= fuentes.length) {
            aviso.style.display = 'flex';
            return;
          }
          montar(i + 1);
        });
      };
      montar(0);

      mapInstance.current.on('click', (e) => {
        if (onMapClick) {
          onMapClick(e.latlng.lat, e.latlng.lng);
        }
      });
    }
  }, []);

  // Leaflet calcula la posicion de las teselas al crearse. Si el
  // contenedor todavia no tiene su alto definitivo (la barra es flex:1
  // y baja cuando aparece "Filtros" o al cambiar el tamano de la
  // ventana), las teselas se quedan descolocadas y se ve gris. El
  // ResizeObserver avisa de cada cambio y el invalidateSize las vuelve
  // a colocar.
  useEffect(() => {
    const cont = mapRef.current;
    const mapa = mapInstance.current;
    if (!cont || !mapa || typeof ResizeObserver === 'undefined') return undefined;
    let ultimo = { w: 0, h: 0 };
    const ro = new ResizeObserver(() => {
      const r = cont.getBoundingClientRect();
      const ahora = { w: Math.round(r.width), h: Math.round(r.height) };
      if (ahora.w === ultimo.w && ahora.h === ultimo.h) return;
      ultimo = ahora;
      mapa.invalidateSize();
    });
    ro.observe(cont);
    return () => ro.disconnect();
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
