/**
 * BuscandoAndo - Admin JS
 * - Mapa Leaflet con geocoding por dirección
 * - Código postal auto-completa provincia, municipio y país
 * - Estado operativo automático basado en horarios
 */
(function() {
    'use strict';

    // ========== MAPA LEAFLET ==========
    function initMap() {
        const prefix = 'id_location-0-';
        const latField = document.getElementById(prefix + 'latitude');
        const lngField = document.getElementById(prefix + 'longitude');
        const streetField = document.getElementById(prefix + 'street');

        if (!latField || !lngField || !streetField) return;

        // Insertar el mapa como sección propia, arriba de los fieldsets
        const fieldsets = document.querySelectorAll('.inline-group');
        const locationInline = streetField.closest('.inline-group');
        
        // Crear sección del mapa completa
        const mapSection = document.createElement('div');
        mapSection.className = 'module aligned';
        mapSection.style.cssText = 'padding: 15px; margin-bottom: 20px;';
        
        const mapTitle = document.createElement('h2');
        mapTitle.textContent = 'Mapa de Ubicacion';
        mapTitle.style.cssText = 'margin: 0 0 10px 0; font-size: 14px; color: #B3B334;';
        mapSection.appendChild(mapTitle);
        
        const mapDiv = document.createElement('div');
        mapDiv.id = 'business-map';
        mapDiv.style.cssText = 'width: 100%; height: 400px; margin: 10px 0; border: 2px solid #B3B334; border-radius: 6px; z-index: 1; background: #1a1a1a;';
        mapSection.appendChild(mapDiv);

        const searchBtn = document.createElement('button');
        searchBtn.type = 'button';
        searchBtn.textContent = '📍 Buscar dirección en mapa';
        searchBtn.className = 'button';
        searchBtn.style.cssText = 'margin: 5px 0; background: #B3B334; color: #1a1a1a; border: 2px solid #B3B334; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.2s;';
        mapSection.appendChild(searchBtn);
        
        // Insertar ANTES del inline de ubicación
        if (locationInline) {
            locationInline.parentNode.insertBefore(mapSection, locationInline);
        }

        // Cargar Leaflet CSS y JS
        if (!document.querySelector('link[href*="leaflet"]')) {
            const leafletCSS = document.createElement('link');
            leafletCSS.rel = 'stylesheet';
            leafletCSS.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(leafletCSS);
        }

        if (!window.L) {
            const leafletJS = document.createElement('script');
            leafletJS.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
            leafletJS.onload = function() { setupMap(latField, lngField, streetField, searchBtn, mapDiv); };
            document.head.appendChild(leafletJS);
        } else {
            setupMap(latField, lngField, streetField, searchBtn, mapDiv);
        }
    }

    function setupMap(latField, lngField, streetField, searchBtn, mapDiv) {
        const defaultLat = parseFloat(latField.value) || 18.4861;
        const defaultLng = parseFloat(lngField.value) || -69.9312;

        const map = L.map(mapDiv).setView([defaultLat, defaultLng], 13);

        L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
            attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a>',
            maxZoom: 17
        }).addTo(map);

        let marker = null;

        // Si ya hay coordenadas, mostrar marcador
        if (latField.value && lngField.value) {
            marker = L.marker([defaultLat, defaultLng]).addTo(map);
        }

        // Buscar dirección con Nominatim
        searchBtn.addEventListener('click', function() {
            // Re-buscar el campo por si el DOM cambió
            const currentStreetField = document.querySelector('[id$="-street"]') || streetField;
            const street = currentStreetField.value.trim();
            if (!street) {
                alert('Ingresa una dirección primero');
                return;
            }

            searchBtn.textContent = '🔄 Buscando...';
            searchBtn.disabled = true;

            // Buscar campos por si el prefijo cambia
            const sectorField = document.querySelector('[id$="-sector"]');
            const municipalityField = document.querySelector('[id$="-municipality"]');
            const districtField = document.querySelector('[id$="-district"]');
            const provinceField = document.querySelector('[id$="-province"]');

            let query = street;
            if (municipalityField && municipalityField.value) query += ', ' + municipalityField.value;
            query += ', República Dominicana';

            console.log('Buscando dirección:', query);

            fetch('https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(query) + '&limit=1')
                .then(function(resp) { return resp.json(); })
                .then(function(data) {
                    console.log('Resultado Nominatim:', data);
                    searchBtn.textContent = '📍 Buscar dirección en mapa';
                    searchBtn.disabled = false;

                    if (data && data.length > 0) {
                        const lat = parseFloat(data[0].lat);
                        const lng = parseFloat(data[0].lon);

                        latField.value = lat.toFixed(6);
                        lngField.value = lng.toFixed(6);

                        map.setView([lat, lng], 17);

                        if (marker) {
                            marker.setLatLng([lat, lng]);
                        } else {
                            marker = L.marker([lat, lng]).addTo(map);
                        }

                        const nameField = document.getElementById('id_name');
                        marker.bindPopup(
                            '<strong>' + (nameField ? nameField.value : 'Negocio') + '</strong><br>' + currentStreetField.value
                        ).openPopup();
                    } else {
                        // Intentar solo con calle y país
                        let simpleQuery = street + ', República Dominicana';
                        console.log('Reintentando con:', simpleQuery);
                        return fetch('https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(simpleQuery) + '&limit=1')
                            .then(function(resp2) { return resp2.json(); })
                            .then(function(data2) {
                                console.log('Segundo intento:', data2);
                                if (data2 && data2.length > 0) {
                                    const lat = parseFloat(data2[0].lat);
                                    const lng = parseFloat(data2[0].lon);
                                    latField.value = lat.toFixed(6);
                                    lngField.value = lng.toFixed(6);
                                    map.setView([lat, lng], 17);
                                    if (marker) { marker.setLatLng([lat, lng]); }
                                    else { marker = L.marker([lat, lng]).addTo(map); }
                                    const nameField = document.getElementById('id_name');
                                    marker.bindPopup(
                                        '<strong>' + (nameField ? nameField.value : 'Negocio') + '</strong><br>' + currentStreetField.value
                                    ).openPopup();
                                } else {
                                    alert('No se encontró la dirección.\n\nPuedes hacer CLICK directamente en el mapa para colocar el marcador.');
                                }
                            });
                    }
                })
                .catch(function(err) {
                    searchBtn.textContent = '📍 Buscar dirección en mapa';
                    searchBtn.disabled = false;
                    console.error('Error en búsqueda:', err);
                    alert('Error al buscar la dirección. Verifica tu conexión a internet.\n\nConsulta: ' + query);
                });
        });

        // Click en el mapa para colocar marcador
        map.on('click', function(e) {
            const lat = e.latlng.lat;
            const lng = e.latlng.lng;

            latField.value = lat.toFixed(6);
            lngField.value = lng.toFixed(6);

            if (marker) {
                marker.setLatLng([lat, lng]);
            } else {
                marker = L.marker([lat, lng]).addTo(map);
            }

            // Reverse geocode
            fetch('https://nominatim.openstreetmap.org/reverse?format=json&lat=' + lat + '&lon=' + lng + '&countrycodes=do')
                .then(function(resp) { return resp.json(); })
                .then(function(data) {
                    if (data && data.display_name) {
                        const parts = data.display_name.split(',');
                        const shortAddress = parts.slice(0, 3).join(',');
                        marker.bindPopup('<strong>Coordenadas capturadas</strong><br>' + shortAddress).openPopup();
                    }
                });
        });

        setTimeout(function() { map.invalidateSize(); }, 500);
    }

    // ========== CÓDIGO POSTAL AUTO-COMPLETAR ==========
    function initPostalCode() {
        const prefix = 'id_location-0-';
        const postalField = document.getElementById(prefix + 'postal_code');
        if (!postalField) return;

        postalField.addEventListener('blur', function() {
            const code = postalField.value.trim();
            if (!code || code.length < 4) return;

            // Buscar en Nominatim por código postal de Rep. Dominicana
            fetch('https://nominatim.openstreetmap.org/search?format=json&postalcode=' + encodeURIComponent(code) + '&country=do&limit=5')
                .then(function(resp) { return resp.json(); })
                .then(function(data) {
                    if (!data || data.length === 0) return;

                    const result = data[0];
                    const address = result.address || {};

                    // Autocompletar provincia
                    const provinceField = document.getElementById(prefix + 'province');
                    if (provinceField && !provinceField.value) {
                        const province = address.state || address.county || address.region || '';
                        if (province) provinceField.value = province;
                    }

                    // Autocompletar municipio
                    const municipalityField = document.getElementById(prefix + 'municipality');
                    if (municipalityField && !municipalityField.value) {
                        const muni = address.city || address.town || address.village || address.municipality || '';
                        if (muni) municipalityField.value = muni;
                    }

                    // Autocompletar distrito municipal
                    const districtField = document.getElementById(prefix + 'district');
                    if (districtField && !districtField.value) {
                        const dist = address.city_district || address.suburb || address.neighbourhood || '';
                        if (dist) districtField.value = dist;
                    }

                    // País siempre Rep. Dominicana
                    const countryField = document.getElementById(prefix + 'country');
                    if (countryField && !countryField.value) {
                        countryField.value = 'República Dominicana';
                    }

                    // Si no hay coordenadas, usar las del resultado
                    const latField = document.getElementById(prefix + 'latitude');
                    const lngField = document.getElementById(prefix + 'longitude');
                    if (latField && !latField.value && result.lat) {
                        latField.value = parseFloat(result.lat).toFixed(6);
                        lngField.value = parseFloat(result.lon).toFixed(6);
                    }
                });
        });
    }

    // ========== ESTADO OPERATIVO AUTOMÁTICO ==========
    function initOperationalStatus() {
        const opStatusField = document.getElementById('id_operational_status');
        if (!opStatusField) return;

        // Buscar "Cerrado Permanente"
        let cerradoPermanenteValue = '';
        for (let i = 0; i < opStatusField.options.length; i++) {
            if (opStatusField.options[i].text.toLowerCase().includes('permanente')) {
                cerradoPermanenteValue = opStatusField.options[i].value;
                break;
            }
        }

        const detectBtn = document.createElement('button');
        detectBtn.type = 'button';
        detectBtn.textContent = '🔄 Auto-detectar estado según horarios';
        detectBtn.style.cssText = 'margin: 5px 0; background: #B3B334; color: #1a1a1a; border: 2px solid #B3B334; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; transition: all 0.2s;';

        opStatusField.parentNode.insertBefore(detectBtn, opStatusField.nextSibling);

        detectBtn.addEventListener('click', function() {
            if (opStatusField.value === cerradoPermanenteValue) {
                alert('El estado está en "Cerrado Permanente". No se modifica automáticamente.');
                return;
            }

            const now = new Date();
            const dayNames = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
            const todayName = dayNames[now.getDay()];
            const currentMinutes = now.getHours() * 60 + now.getMinutes();

            const daySelects = document.querySelectorAll('select[name$="-day"]');
            let isOpen = false;

            daySelects.forEach(function(select) {
                if (select.value === todayName) {
                    const row = select.closest('tr');
                    if (!row) return;

                    const isClosed = row.querySelector('input[name$="-is_closed"]');
                    if (isClosed && isClosed.checked) return;

                    const openTime = row.querySelector('input[name$="-open_time"]');
                    const closeTime = row.querySelector('input[name$="-close_time"]');

                    if (openTime && closeTime && openTime.value && closeTime.value) {
                        const openParts = openTime.value.split(':');
                        const closeParts = closeTime.value.split(':');
                        const openMinutes = parseInt(openParts[0]) * 60 + parseInt(openParts[1]);
                        const closeMinutes = parseInt(closeParts[0]) * 60 + parseInt(closeParts[1]);

                        if (currentMinutes >= openMinutes && currentMinutes < closeMinutes) {
                            isOpen = true;
                        }
                    }
                }
            });

            let abiertoValue = '';
            let cerradoValue = '';

            for (let i = 0; i < opStatusField.options.length; i++) {
                const text = opStatusField.options[i].text.toLowerCase();
                if (text.includes('abierto') || text.includes('open')) {
                    abiertoValue = opStatusField.options[i].value;
                }
                if ((text.includes('cerrado') && !text.includes('permanente')) || text.includes('closed')) {
                    cerradoValue = opStatusField.options[i].value;
                }
            }

            if (isOpen) {
                opStatusField.value = abiertoValue;
                alert('✅ Estado cambiado a: ABIERTO');
            } else {
                opStatusField.value = cerradoValue;
                alert('🔴 Estado cambiado a: CERRADO');
            }
        });
    }

    // ========== INICIALIZAR ==========
    document.addEventListener('DOMContentLoaded', function() {
        initMap();
        initPostalCode();
        initOperationalStatus();
    });

    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function() {
            setTimeout(initMap, 200);
        });
    }
})();
