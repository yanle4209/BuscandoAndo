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

    // ========== COPIAR HORARIOS ==========
    function initCopyHours() {
        // Buscar el group del inline de horarios - probar varios selectores
        let hoursGroup = document.getElementById('businesshours_set-group');
        if (!hoursGroup) hoursGroup = document.getElementById('business_hours_businesshours_set-group');
        if (!hoursGroup) {
            // Fallback: buscar cualquier .inline-group que contenga selects de día
            const groups = document.querySelectorAll('.inline-group');
            for (let g = 0; g < groups.length; g++) {
                if (groups[g].querySelector('select[name$="-day"]')) {
                    hoursGroup = groups[g];
                    break;
                }
            }
        }
        if (!hoursGroup) return;

        const table = hoursGroup.querySelector('table');
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const rows = tbody.querySelectorAll('tr');
        if (rows.length === 0) return;

        // Agregar cabecera "Copiar" al thead
        const thead = table.querySelector('thead');
        if (thead) {
            const headerRow = thead.querySelector('tr');
            if (headerRow && !headerRow.querySelector('.copy-hours-th')) {
                const th = document.createElement('th');
                th.className = 'copy-hours-th';
                th.style.cssText = 'text-align: center; padding: 4px;';
                th.textContent = 'Copiar';
                headerRow.appendChild(th);
            }
        }

        rows.forEach(function(row, idx) {
            // Skip empty/template rows
            if (row.querySelector('.empty-form')) return;
            const daySelect = row.querySelector('select[name$="-day"]');
            if (!daySelect) return;
            // Skip if already has copy button
            if (row.querySelector('.copy-hours-btn')) return;

            // Agregar celda con botón de copiar
            const td = document.createElement('td');
            td.style.cssText = 'text-align: center; vertical-align: middle;';

            const copyBtn = document.createElement('button');
            copyBtn.type = 'button';
            copyBtn.textContent = '📋';
            copyBtn.title = 'Copiar horario de otro día';
            copyBtn.className = 'copy-hours-btn';
            copyBtn.style.cssText = 'background: #B3B334; color: #1a1a1a; border: 2px solid #B3B334; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s;';

            copyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();

                const allRows = tbody.querySelectorAll('tr');
                const options = [];

                allRows.forEach(function(r, i) {
                    if (r.querySelector('.empty-form')) return;
                    const sel = r.querySelector('select[name$="-day"]');
                    const openTime = r.querySelector('input[name$="-open_time"]');
                    const closeTime = r.querySelector('input[name$="-close_time"]');
                    const isClosed = r.querySelector('input[name$="-is_closed"]');
                    const isHoliday = r.querySelector('input[name$="-is_holiday"]');

                    if (sel && sel.value) {
                        const hasData = (openTime && openTime.value) || (closeTime && closeTime.value) || (isClosed && isClosed.checked) || (isHoliday && isHoliday.checked);
                        if (hasData && i !== idx) {
                            options.push({
                                day: sel.value,
                                open: openTime ? openTime.value : '',
                                close: closeTime ? closeTime.value : '',
                                closed: isClosed ? isClosed.checked : false,
                                holiday: isHoliday ? isHoliday.checked : false,
                            });
                        }
                    }
                });

                if (options.length === 0) {
                    alert('No hay otros días con horarios definidos para copiar.');
                    return;
                }

                const overlay = document.createElement('div');
                overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:10000;display:flex;align-items:center;justify-content:center;';

                const popup = document.createElement('div');
                popup.style.cssText = 'background:#1a1a1a;border:2px solid #B3B334;border-radius:10px;padding:20px;min-width:280px;color:#f3f3f3;';

                const title = document.createElement('h3');
                title.textContent = 'Copiar horario de:';
                title.style.cssText = 'margin:0 0 12px 0;color:#B3B334;font-size:16px;';
                popup.appendChild(title);

                options.forEach(function(opt) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    const timeInfo = opt.closed ? 'Cerrado' : (opt.holiday ? 'Fiesta' : (opt.open + ' - ' + opt.close));
                    btn.textContent = opt.day + ' (' + timeInfo + ')';
                    btn.style.cssText = 'display:block;width:100%;text-align:left;padding:10px 14px;margin-bottom:6px;background:#2a2a2a;color:#f3f3f3;border:1px solid #555;border-radius:6px;cursor:pointer;font-size:14px;transition:all 0.2s;';

                    btn.addEventListener('mouseenter', function() { btn.style.borderColor = '#B3B334'; btn.style.background = '#333'; });
                    btn.addEventListener('mouseleave', function() { btn.style.borderColor = '#555'; btn.style.background = '#2a2a2a'; });

                    btn.addEventListener('click', function() {
                        const openTime = row.querySelector('input[name$="-open_time"]');
                        const closeTime = row.querySelector('input[name$="-close_time"]');
                        const isClosed = row.querySelector('input[name$="-is_closed"]');
                        const isHoliday = row.querySelector('input[name$="-is_holiday"]');

                        if (openTime) openTime.value = opt.open;
                        if (closeTime) closeTime.value = opt.close;
                        if (isClosed) isClosed.checked = opt.closed;
                        if (isHoliday) isHoliday.checked = opt.holiday;

                        overlay.remove();
                    });

                    popup.appendChild(btn);
                });

                const cancelBtn = document.createElement('button');
                cancelBtn.type = 'button';
                cancelBtn.textContent = 'Cancelar';
                cancelBtn.style.cssText = 'display:block;width:100%;padding:8px;margin-top:8px;background:transparent;color:#999;border:1px solid #555;border-radius:6px;cursor:pointer;font-size:13px;transition:all 0.2s;';
                cancelBtn.addEventListener('click', function() { overlay.remove(); });
                popup.appendChild(cancelBtn);

                overlay.appendChild(popup);
                overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
                document.body.appendChild(overlay);
            });

            td.appendChild(copyBtn);
            row.appendChild(td);
        });
    }

    // ========== DETECTAR FERIADOS ==========
    function initHolidayDetection() {
        // Buscar el inline group de horarios
        let hoursGroup = document.getElementById('businesshours_set-group');
        if (!hoursGroup) hoursGroup = document.getElementById('business_hours_businesshours_set-group');
        if (!hoursGroup) {
            const groups = document.querySelectorAll('.inline-group');
            for (let g = 0; g < groups.length; g++) {
                if (groups[g].querySelector('select[name$="-day"]')) {
                    hoursGroup = groups[g];
                    break;
                }
            }
        }
        if (!hoursGroup) return;

        // Feriados fijos de RD (mes, día)
        var HOLIDAYS = [
            [1, 1, 'Año Nuevo'],
            [1, 21, 'Próceres'],
            [1, 26, 'Altagracia'],
            [2, 27, 'Independencia'],
            [5, 1, 'Trabajo'],
            [8, 16, 'Restauración'],
            [9, 24, 'Mercedes'],
            [11, 6, 'Constitución'],
            [12, 25, 'Navidad']
        ];

        var DAY_TO_INDEX = { 'Lunes': 0, 'Martes': 1, 'Miércoles': 2, 'Jueves': 3, 'Viernes': 4, 'Sábado': 5, 'Domingo': 6 };

        function checkHolidays() {
            var today = new Date();
            var todayIdx = today.getDay() === 0 ? 6 : today.getDay() - 1; // 0=Lunes
            var detected = [];

            var table = hoursGroup.querySelector('table');
            if (!table) return;
            var tbody = table.querySelector('tbody');
            if (!tbody) return;
            var rows = tbody.querySelectorAll('tr');

            rows.forEach(function(row) {
                if (row.querySelector('.empty-form')) return;
                var sel = row.querySelector('select[name$="-day"]');
                if (!sel || !sel.value) return;

                var dayIdx = DAY_TO_INDEX[sel.value];
                if (dayIdx === undefined) return;

                // Calcular la fecha de ese día en la semana actual
                var diff = dayIdx - todayIdx;
                var targetDate = new Date(today);
                targetDate.setDate(today.getDate() + diff);

                // Verificar si es feriado
                var holidayName = null;
                for (var h = 0; h < HOLIDAYS.length; h++) {
                    if (targetDate.getMonth() + 1 === HOLIDAYS[h][0] && targetDate.getDate() === HOLIDAYS[h][1]) {
                        holidayName = HOLIDAYS[h][2];
                        break;
                    }
                }

                var isHoliday = row.querySelector('input[name$="-is_holiday"]');
                if (holidayName && isHoliday && !isHoliday.checked) {
                    isHoliday.checked = true;
                    detected.push(sel.value + ' (' + holidayName + ')');
                }
            });

            if (detected.length > 0) {
                alert('🎉 Feriados detectados y marcados:\n\n• ' + detected.join('\n• '));
            } else {
                alert('No se encontraron feriados esta semana.\n\nSolo se detectan feriados en la semana actual (7 días desde hoy).');
            }
        }

        // Agregar botón al encabezado del inline
        var titleEl = hoursGroup.querySelector('h3, h2, .inline-group-title');
        if (!titleEl) {
            // Buscar el header del inline
            var header = hoursGroup.querySelector('.module');
            if (header) titleEl = header.querySelector('h2, h3');
        }

        var detectBtn = document.createElement('button');
        detectBtn.type = 'button';
        detectBtn.textContent = '🎉 Detectar fiestas de esta semana';
        detectBtn.style.cssText = 'margin: 8px 0 4px; background: #B3B334; color: #1a1a1a; border: 2px solid #B3B334; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 12px; transition: all 0.2s;';
        detectBtn.addEventListener('mouseenter', function() { detectBtn.style.background = '#9e9e2e'; });
        detectBtn.addEventListener('mouseleave', function() { detectBtn.style.background = '#B3B334'; });
        detectBtn.addEventListener('click', function(e) { e.preventDefault(); checkHolidays(); });

        // Insertar el botón después del título del inline
        if (titleEl && titleEl.parentNode) {
            titleEl.parentNode.insertBefore(detectBtn, titleEl.nextSibling);
        } else {
            // Fallback: insertar al inicio del inline
            hoursGroup.insertBefore(detectBtn, hoursGroup.firstChild);
        }
    }

    // ========== INICIALIZAR ==========
    document.addEventListener('DOMContentLoaded', function() {
        initMap();
        initPostalCode();
        initOperationalStatus();
        initCopyHours();
        initHolidayDetection();
    });

    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function() {
            setTimeout(initMap, 200);
        });
    }
})();
