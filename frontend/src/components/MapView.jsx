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
  html: `<div style="width:14px;height:14px;background:#B3B334;border:2px solid #1a1a1a;border-radius:50%;box-shadow:0 0 6px rgba(179,179,52,0.5);"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const SELECTED_ICON = L.divIcon({
  className: 'custom-marker',
  html: `<div style="width:20px;height:20px;background:#B3B334;border:3px solid #fff;border-radius:50%;box-shadow:0 0 12px rgba(179,179,52,0.7);"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const USER_ICON = L.divIcon({
  className: 'custom-marker',
  html: `<div style="width:12px;height:12px;background:#4285f4;border:2px solid #fff;border-radius:50%;box-shadow:0 0 8px rgba(66,133,244,0.6);"></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

export default function MapView({ businesses, selected, center, onMarkerClick, onMapClick }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef([]);

  // Initialize map
  useEffect(() => {
    if (mapRef.current && !mapInstance.current) {
      mapInstance.current = L.map(mapRef.current, {
        center: center,
        zoom: 12,
        zoomControl: false,
      });

      L.control.zoom({ position: 'topright' }).addTo(mapInstance.current);

      // OpenStreetMap tiles (free, no API key)
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

  // Update center when user location changes
  useEffect(() => {
    if (mapInstance.current && center) {
      mapInstance.current.setView(center, mapInstance.current.getZoom());
    }
  }, [center]);

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
