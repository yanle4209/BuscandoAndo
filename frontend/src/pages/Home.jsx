import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import SearchBar from '../components/SearchBar';
import MapView from '../components/MapView';
import BusinessCard from '../components/BusinessCard';
import CorrectionModal from '../components/CorrectionModal';
import BusinessModal from '../components/BusinessModal';
import MapOverlay from '../components/MapOverlay';
import { claveCabecera } from '../municipios';
import api from '../api/axios';
import './Home.css';

// R1.3: el radio es fijo a 5 km en las dos plataformas. El backend ya lo
// acota por arriba, pero se manda explicito porque la portada tambien
// filtra por distancia y no debe depender de un default.
const RADIO_KM = 5;

// Debe coincidir con SearchPagination.page_size del backend. Si no, el
// total de páginas sale inflado y "Siguiente" deja llegar a una página
// vacía que solo muestra el overlay.
const POR_PAGINA = 12;
// R1.a disparo 3: refrescar cuando el usuario se aleja >= 500 m del ultimo
// punto consultado.
const UMBRAL_MOV_KM = 0.5;
// R1.a: minimo 30 s entre refrescos AUTOMATICOS por movimiento. Los cambios
// explicitos de punto (llegada, municipio, primera busqueda, "Mi ubicacion")
// no se limitan: si no, el refresco de llegada se descartaria y te quedarias
// viendo resultados de destino con el GPS ya dentro del circulo.
const THROTTLE_MS = 30000;
// R3.4: la ciudad elegida se recuerda entre sesiones, pero solo como base
// para cuando no hay GPS (R3.6). El destino no se reanuda.
const CLAVE_MUNICIPIO = 'buscandoando.municipio';

// Grid: 3 cols x 4 rows = 12 cards per page; la paginacion aparece
// cuando la pagina se llena (POR_PAGINA = 12).

const FILTROS_VACIOS = { text: '', category: '' };

// La maquina de 3 estados + flag "llego" de DISENO.md §1 vive aqui y no en
// useState sueltos: casi todas las transiciones cambian punto, pagina y
// filtros A LA VEZ, y si no se hacen en la misma actualizacion se disparan
// dos consultas (una con la pagina vieja y otra con la nueva).
const ESTADO_INICIAL = {
  modo: 'espera',   // 'espera' (S0) | 'gps' (S1) | 'destino' (S2)
  punto: null,      // centro del circulo: el punto de la ULTIMA consulta
  pos: null,        // ultima posicion GPS conocida
  destino: null,    // cabecera elegida; sirve para ver llegada y salida
  restaurado: false,// el destino viene del localStorage, no de una eleccion
  llego: false,     // ya estuvo dentro del destino; habilita el reset (R3.2)
  filters: FILTROS_VACIOS,
  haBuscado: false,
  pagina: 1,
};

function distanciaKm(a, b) {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function elegirPuntoDeMunicipio(estado, destino, restaurado) {
  // R3.3: si la cabecera esta a 5 km o menos de su posicion, es su propio
  // municipio. Lo asume y sigue en GPS — no hay nada que mover.
  if (estado.pos && distanciaKm(destino, estado.pos) <= RADIO_KM) {
    return {
      ...estado,
      destino,
      modo: 'gps',
      punto: estado.pos,
      restaurado: false,
      llego: false,
      pagina: 1,
    };
  }
  // S0/S1 -> S2: el punto pasa a ser la cabecera (o el punto del mapa).
  return {
    ...estado,
    destino,
    modo: 'destino',
    punto: destino,
    restaurado: Boolean(restaurado),
    llego: false,
    pagina: 1,
  };
}

function reducer(estado, accion) {
  switch (accion.type) {
    case 'gps': {
      const pos = accion.pos;
      const base = { ...estado, pos, restaurado: false };

      // S0 -> S1: al abrir, el GPS manda si esta disponible (R3.6).
      if (estado.modo === 'espera') {
        return { ...base, modo: 'gps', punto: pos, llego: false };
      }

      // Lo recordado solo tapa la ausencia de GPS: en cuanto hay posicion
      // real, manda la posicion real (R3.4 "el destino no se reanuda").
      // PERO si esa posicion real esta a mas de 5 km de la cabecera
      // guardada, manda la CABECERA: se siguen consultando los negocios
      // de su municipio y no se cambian los resultados por estar lejos.
      // La siguiente actualizacion ya no entra aqui (restaurado pasa a
      // false) y las reglas S2 -> S1 toman el relevo: al acercarse a 5 km
      // vuelve a GPS solo.
      if (estado.modo === 'destino' && estado.restaurado) {
        if (estado.destino && distanciaKm(pos, estado.destino) > RADIO_KM) {
          return { ...base, modo: 'destino', punto: estado.destino, llego: false };
        }
        return { ...base, modo: 'gps', punto: pos, destino: null, llego: false };
      }

      // S2 -> S1: al entrar a 5 km del destino vuelve a GPS solo, sin
      // boton (R3.1). "llego" queda en true y habilita la salida.
      if (estado.modo === 'destino' && estado.destino
        && distanciaKm(pos, estado.destino) <= RADIO_KM) {
        return { ...base, modo: 'gps', punto: pos, llego: true };
      }

      // Ya en GPS: solo se actualiza la posicion. "punto" NO se mueve: es
      // el ultimo punto CONSULTADO, contra el que se mide R1.a.
      return base;
    }

    case 'municipio':
      if (!accion.cabecera) {
        // Deseleccionar: vuelve a su GPS si lo hay; si no, a espera. Sin
        // punto no se consulta (R1.1), asi que ademas se vuelve a la
        // portada: quitar el municipio es volver a empezar, no quedarse
        // mirando una rejilla vacia.
        const base = {
          ...estado,
          destino: null,
          restaurado: false,
          llego: false,
          pagina: 1,
          haBuscado: false,
        };
        if (estado.pos) return { ...base, modo: 'gps', punto: estado.pos };
        return { ...base, modo: 'espera', punto: null };
      }
      // Elegir municipio (a mano o al restaurarlo de localStorage) EMPIEZA
      // a consultar: el overlay de portada se oculta y salen las tarjetas
      // de ese punto. Antes el punto se ponia pero el estado seguia en la
      // portada (haBuscado false) y no se pedia nada: no aparecia nada.
      return {
        ...elegirPuntoDeMunicipio(estado, accion.cabecera, accion.restaurado),
        haBuscado: true,
      };

    case 'mapa':
      // Mover el punto con el mapa es el mismo acto que elegir municipio:
      // un cambio explicito de punto que sigue las reglas de R3. No se
      // recuerda: R3.4 habla de la ciudad elegida, no de un punto del mapa.
      // Y al igual que elegir municipio, EMPIEZA la busqueda: en portada
      // el clic movia el punto pero el overlay seguia encima y no salia
      // ninguna tarjeta.
      return {
        ...elegirPuntoDeMunicipio(estado, accion.pos, false),
        haBuscado: true,
      };

    case 'forzar_gps': {
      const pos = accion.pos || estado.pos;
      if (!pos) return estado;
      // "Mi ubicacion" es explicito: ademas de mover el punto, EMPIEZA a
      // consultar (haBuscado). Sin eso el overlay de portada se quedaba
      // encima y no aparecia ninguna tarjeta.
      //
      // Regla de la cabecera: si hay municipio elegido/recordado y esta
      // posicion queda a mas de 5 km de el, manda la CABECERA: el punto
      // de consulta no se mueve y solo se guarda la posicion nueva. Con
      // la cabecera a 5 km o menos es su propio municipio -> manda su
      // GPS (el punto pasa a la posicion real, mas precisa).
      if (estado.destino && distanciaKm(pos, estado.destino) > RADIO_KM) {
        return {
          ...estado,
          pos,
          modo: 'destino',
          punto: estado.destino,
          restaurado: false,
          pagina: 1,
          haBuscado: true,
        };
      }
      return {
        ...estado,
        pos,
        modo: 'gps',
        punto: pos,
        destino: null,
        restaurado: false,
        llego: false,
        pagina: 1,
        haBuscado: true,
      };
    }

    case 'mover':
      // Refresco automatico por movimiento (R1.a disparo 3) con su throttle
      // de 30 s aplicado antes de llegar aqui.
      if (estado.modo !== 'gps' || !estado.punto) return estado;
      if (distanciaKm(accion.pos, estado.punto) < UMBRAL_MOV_KM) return estado;
      return { ...estado, punto: accion.pos, pagina: 1 };

    case 'reset':
      // R3.2: salir de >5 km del destino DESPUES de haber entrado borra
      // TODO. Si hay posicion GPS, el propio GPS vuelve a ser el punto en el
      // mismo paso: no se deja al usuario en espera con un GPS valido sin
      // usar (R1.1, nunca navegar sin punto activo).
      {
        const base = {
          ...estado,
          destino: null,
          restaurado: false,
          llego: false,
          filters: FILTROS_VACIOS,
          haBuscado: false,
          pagina: 1,
        };
        return estado.pos
          ? { ...base, modo: 'gps', punto: estado.pos }
          : { ...base, modo: 'espera', punto: null };
      }

    case 'buscar': {
      // R2: en cada consulta se conservan texto y categoria y se vuelve a
      // pagina 1. Un filtro vacio vuelve a la portada.
      const filters = { ...estado.filters, ...accion.parcial };
      const vacio = !filters.text && !filters.category;
      return { ...estado, filters, pagina: 1, haBuscado: !vacio };
    }

    case 'pagina':
      return { ...estado, pagina: accion.n };

    default:
      return estado;
  }
}

export default function Home() {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL);
  const [searchFeatured, setSearchFeatured] = useState([]);
  const [businesses, setBusinesses] = useState([]);
  const [selected, setSelected] = useState(null);
  const [modalBiz, setModalBiz] = useState(null);
  const [showContact, setShowContact] = useState(false);
  // Negocio del que el visitante ha pulsado "Corregir" (null = sin modal).
  const [correctionBiz, setCorrectionBiz] = useState(null);
  const [loading, setLoading] = useState(false);
  const [totalPages, setTotalPages] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const [municipioClave, setMunicipioClave] = useState('');
  const [cabeceras, setCabeceras] = useState([]);
  // Bundle que corre ESTA pestana (index-BP-pSWLW). Se pinta en el
  // badge de la esquina: es la prueba de si la pestana esta al dia.
  const [version] = useState(() => {
    const src = document.querySelector('script[type="module"]')?.src || '';
    const nombre = (src.split('/').pop() || '').replace(/^index-/, '').replace(/\.js$/, '');
    return nombre || 'desconocida';
  });
  // Se pone con la version nueva cuando NO se puede recargar sola
  // (hay una busqueda encima); null = esta al dia.
  const [versionNueva, setVersionNueva] = useState(null);

  const pendienteRef = useRef(null);
  const ultimaRefrescoRef = useRef(0);
  const temporizadorRef = useRef(null);

  // ------------------------------------------------------------------
  // Las 158 cabeceras: selector manual y respaldo cuando no hay GPS.
  // ------------------------------------------------------------------
  useEffect(() => {
    api.get('/cabeceras/')
      .then(({ data }) => setCabeceras(Array.isArray(data) ? data : []))
      .catch(() => setCabeceras([]));
  }, []);

  const restaurarMunicipio = useCallback(() => {
    // R3.4 + R3.6: lo recordado solo entra cuando NO hay GPS.
    try {
      const guardado = localStorage.getItem(CLAVE_MUNICIPIO);
      if (!guardado) return;
      const cabecera = JSON.parse(guardado);
      if (!cabecera || typeof cabecera.lat !== 'number'
        || typeof cabecera.lng !== 'number') return;
      setMunicipioClave(claveCabecera(cabecera));
      dispatch({ type: 'municipio', cabecera, restaurado: true });
    } catch {
      // Sin localStorage (modo privado) o dato corrupto: se queda en espera
      // y el usuario elige municipio a mano.
    }
  }, []);

  // ------------------------------------------------------------------
  // GPS. "Mi ubicacion" manda al abrir (R3.6); el watch es el que mueve el
  // punto al andar (R1.a) y detecta llegadas y salidas (R3.1 / R3.2).
  // ------------------------------------------------------------------
  useEffect(() => {
    const aPos = (p) => ({ lat: p.coords.latitude, lng: p.coords.longitude });
    if (!navigator.geolocation) {
      restaurarMunicipio();
      return undefined;
    }
    const geo = navigator.geolocation;
    geo.getCurrentPosition(
      (p) => dispatch({ type: 'gps', pos: aPos(p) }),
      () => restaurarMunicipio(),
      { maximumAge: 60000, timeout: 15000, enableHighAccuracy: false },
    );
    const id = geo.watchPosition(
      (p) => dispatch({ type: 'gps', pos: aPos(p) }),
      () => {},
      { maximumAge: 10000, enableHighAccuracy: false },
    );
    return () => geo.clearWatch(id);
  }, [restaurarMunicipio]);

  // ------------------------------------------------------------------
  // Refresco automatico por movimiento (R1.a) con throttle de 30 s.
  // ------------------------------------------------------------------
  const programarRefresco = useCallback((pos) => {
    pendienteRef.current = pos;
    const refrescar = () => {
      const p = pendienteRef.current;
      if (!p) return;
      pendienteRef.current = null;
      ultimaRefrescoRef.current = Date.now();
      dispatch({ type: 'mover', pos: p });
    };
    const espera = THROTTLE_MS - (Date.now() - ultimaRefrescoRef.current);
    if (espera <= 0) {
      refrescar();
      return;
    }
    // Si cae dentro del throttle no se descarta: se deja el ultimo punto
    // pendiente y se dispara al vencer. Si no, quien camina y se detiene
    // justo en esa ventana se quedaria mirando resultados viejos.
    if (temporizadorRef.current) return;
    temporizadorRef.current = setTimeout(() => {
      temporizadorRef.current = null;
      refrescar();
    }, espera);
  }, []);

  const cancelarRefresco = useCallback(() => {
    if (temporizadorRef.current) {
      clearTimeout(temporizadorRef.current);
      temporizadorRef.current = null;
    }
    pendienteRef.current = null;
  }, []);

  useEffect(() => cancelarRefresco, [cancelarRefresco]);

  useEffect(() => {
    const pos = estado.pos;
    if (!pos) return;

    // R3.2: salir de >5 km del destino ya alcanzado -> borra todo.
    if (estado.modo === 'gps' && estado.llego && estado.destino
      && distanciaKm(pos, estado.destino) > RADIO_KM) {
      cancelarRefresco();
      dispatch({ type: 'reset' });
      return;
    }

    if (estado.modo !== 'gps' || !estado.punto) return;
    if (distanciaKm(pos, estado.punto) < UMBRAL_MOV_KM) return;
    programarRefresco(pos);
  }, [estado, programarRefresco, cancelarRefresco]);

  // ------------------------------------------------------------------
  // Consulta de resultados. Todo el mundo manda lat+lng+radius y NADIE
  // manda city (R3.5): la ciudad ya es coordenadas + 5 km.
  // ------------------------------------------------------------------
  const peticionRef = useRef(0);

  const fetchBusinesses = useCallback(async (pageNum = 1) => {
    const punto = estado.punto;
    if (!punto) return; // R1.1: sin punto activo no se consulta nada.
    // Cada consulta se numera: si llega un cambio de punto mientras esta
    // vuelva, la respuesta vieja se tira en vez de pisar la buena.
    const peticion = peticionRef.current + 1;
    peticionRef.current = peticion;
    const vigente = () => peticionRef.current === peticion;
    setLoading(true);
    try {
      const params = {
        page: pageNum, lat: punto.lat, lng: punto.lng, radius: RADIO_KM,
      };
      if (estado.filters.text) params.text = estado.filters.text;
      if (estado.filters.category) params.category = estado.filters.category;
      const { data } = await api.get('/businesses/', { params });
      if (!vigente()) return;
      setBusinesses(data.results || []);
      setTotalResults(data.count || 0);
      setTotalPages(Math.ceil((data.count || 0) / POR_PAGINA));

      // Destacados del buscador: R1.2 entran en el MISMO filtro de 5 km.
      const searchParams = {
        lat: punto.lat, lng: punto.lng, radius: RADIO_KM,
      };
      if (estado.filters.text) searchParams.text = estado.filters.text;
      if (estado.filters.category) searchParams.category = estado.filters.category;
      try {
        const { data: featData } = await api.get('/businesses/featured-by-search/', { params: searchParams });
        if (!vigente()) return;
        setSearchFeatured(Array.isArray(featData) ? featData : []);
      } catch {
        if (vigente()) setSearchFeatured([]);
      }
    } catch (err) {
      if (!vigente()) return;
      console.error('Error fetching businesses:', err);
      setBusinesses([]);
      setTotalResults(0);
      setTotalPages(1);
      setSearchFeatured([]);
    } finally {
      if (vigente()) setLoading(false);
    }
  }, [estado.punto, estado.filters]);

  useEffect(() => {
    if (estado.haBuscado) fetchBusinesses(estado.pagina);
  }, [fetchBusinesses, estado.haBuscado, estado.pagina]);

  // ------------------------------------------------------------------
  // Portada: ya no se piden destacados sin buscar (R4.1 retirado); los
  // destacados solo salen de una busqueda (.search-featured-top). Lo
  // que si se borra es lo que hubiera de una consulta anterior: sin
  // punto activo no hay circulo de 5 km que mostrar.
  // ------------------------------------------------------------------
  useEffect(() => {
    if (estado.punto) return undefined;
    setBusinesses([]);
    setSearchFeatured([]);
    setTotalResults(0);
    setTotalPages(1);
    return undefined;
  }, [estado.punto]);

  // Pestañas viejas: una pestaña abierta se queda con el bundle con el
  // que se cargo y no se entera del deploy (teselas 403, sombra sin
  // ver, barra del ancho antiguo...). Cada minuto se mira si el
  // index.html del servidor apunta a otro bundle. En portada y sin nada
  // abierto se recarga sola; con una busqueda encima NO se arrastra la
  // recarga (se perdia todo lo buscado): se pone el aviso en pantalla
  // y decide el usuario. Antes este chequeo se salia sin avisar cuando
  // habia busqueda, y ahi la pestana NUNCA se actualizaba.
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const r = await fetch(window.location.origin + window.location.pathname, { cache: 'no-store' });
        if (!r.ok) return;
        const html = await r.text();
        const servido = (html.match(/assets\/(index-[\w-]+\.js)/) || [])[1];
        const mio = (document.querySelector('script[type="module"]')?.src || '').split('/').pop();
        if (!servido || !mio || servido === mio) {
          setVersionNueva(null);
          return;
        }
        if (estado.haBuscado || modalBiz || correctionBiz || showContact) {
          setVersionNueva(servido);
          return;
        }
        window.location.reload();
      } catch {
        // sin red no se recarga: se reintenta en el siguiente minuto
      }
    }, 60000);
    return () => clearInterval(id);
  }, [estado.haBuscado, modalBiz, correctionBiz, showContact]);

  const handleSearch = (parcial) => dispatch({ type: 'buscar', parcial });

  const handlePageChange = (newPage) => {
    dispatch({ type: 'pagina', n: newPage });
    document.querySelector('.right-panel')?.scrollTo(0, 0);
  };

  const elegirMunicipio = (clave) => {
    if (!clave) {
      try { localStorage.removeItem(CLAVE_MUNICIPIO); } catch { /* sin storage */ }
      setMunicipioClave('');
      dispatch({ type: 'municipio', cabecera: null });
      return;
    }
    const cabecera = cabeceras.find((c) => claveCabecera(c) === clave);
    if (!cabecera) return;
    try { localStorage.setItem(CLAVE_MUNICIPIO, JSON.stringify(cabecera)); } catch { /* sin storage */ }
    setMunicipioClave(clave);
    dispatch({ type: 'municipio', cabecera });
  };

  const pedirGps = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (p) => dispatch({
        type: 'forzar_gps',
        pos: { lat: p.coords.latitude, lng: p.coords.longitude },
      }),
      () => {},
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  };

  const elegirPuntoDelMapa = (lat, lng) => {
    setMunicipioClave('');
    dispatch({ type: 'mapa', pos: { lat, lng } });
  };

  const sinPunto = !estado.punto;
  const sinResultados = !loading
    && businesses.length === 0
    && searchFeatured.length === 0;
  // Sin punto activo no hay circulo de 5 km que trazar. El overlay es toda
  // la pantalla, asi que tiene que decir ademas como salir de ahi.
  const avisoSinPunto = sinPunto
    ? 'Elige tu municipio o activa tu ubicación para empezar'
    : null;

  // El mapa de la barra: los resultados cuando hay busqueda; en la
  // portada no hay marcadores (los destacados ya no se piden sin buscar).
  const mapBusinesses = estado.haBuscado ? businesses : [];

  // Identidad estable: si no, el mapa se recentra en cada render y no se
  // puede arrastrar. Recentra SOLO cuando cambia el punto (R2.1).
  const centroMapa = useMemo(
    () => (estado.punto ? [estado.punto.lat, estado.punto.lng] : null),
    [estado.punto],
  );

  const searchProps = {
    filters: estado.filters,
    onSearch: handleSearch,
    hasSearched: estado.haBuscado,
    onGeolocate: pedirGps,
    cabeceras,
    municipioClave,
    onMunicipio: elegirMunicipio,
  };

  return (
    <div className="home-layout">
      {/* Cabecera a todo el ancho del viewport: debajo van la barra
          izquierda (20-25% del ancho) y la rejilla de resultados. */}
      <div className={`right-brand ${estado.haBuscado ? 'right-brand--compact' : ''}`}>
        <h1 className="right-brand-title" onClick={() => window.location.reload()} style={{ cursor: 'pointer' }}>Buscando<span className="right-brand-accent">Ando</span></h1>
      </div>

      <div className="left-panel">
        <div className="sidebar-top">
          <button className="contact-link" onClick={() => setShowContact(true)}>Contactanos</button>
        </div>
        <SearchBar {...searchProps} />
        {/* El mapa esta SIEMPRE, debajo del selector de municipio: se
            centra en el municipio elegido o, si no lo hay, en lo que
            haya captado el GPS. Sin punto aun -> vista del pais. */}
        <div className="sidebar-map">
          <MapView
            businesses={mapBusinesses}
            selected={selected}
            center={centroMapa}
            onMarkerClick={(biz) => setModalBiz(biz)}
            onMapClick={elegirPuntoDelMapa}
          />
        </div>
      </div>

      <div className="right-panel">
        {/* Mobile search bar */}
        <div className="mobile-search">
          <SearchBar {...searchProps} />
        </div>

        {estado.haBuscado ? (
          <>
            <div className="right-section-header">
              <h2>{loading ? 'Buscando...' : `${totalResults} resultado${totalResults !== 1 ? 's' : ''}`}</h2>
            </div>
            <div className="right-results-scroll">
              {/* 3 Featured by category: solo si hay destacados dentro de los 5 km (a1).
                  No se pintan mientras carga la busqueda: si no, se veian los
                  destacados de la consulta anterior saltando por la pantalla. */}
              {!loading && searchFeatured.length > 0 && (
                <div className="search-featured-top">
                  {searchFeatured.map((biz) => (
                    <BusinessCard
                      key={biz.id || biz.slug}
                      business={biz}
                      onClick={() => setModalBiz(biz)}
                      onReport={() => setCorrectionBiz(biz)}
                    />
                  ))}
                </div>
              )}

              {/* Regular results */}
              {/* Esqueleto mientras responde la API: 12 huecos (POR_PAGINA),
                  la misma pagina 3x4 que despues, para que el cambio a los
                  resultados reales no mueva ni un pixel el layout. */}
              <div className="right-results-list" aria-busy={loading ? 'true' : 'false'}>
                {loading ? (
                  Array.from({ length: POR_PAGINA }, (_, i) => (
                    <div className="skeleton-card" key={`skeleton-${i}`} aria-hidden="true">
                      <div className="skeleton-card__cover" />
                      <div className="skeleton-card__line skeleton-card__line--title" />
                      <div className="skeleton-card__line" />
                      <div className="skeleton-card__line skeleton-card__line--short" />
                      <div className="skeleton-card__footer" />
                    </div>
                  ))
                ) : sinResultados ? (
                  // 0 destacadas + 0 normales -> overlay en vez de
                  // "No se encontraron negocios" (DISENO.md a1 / m2).
                  <div className="sin-resultados">
                    <MapOverlay visible hint={avisoSinPunto} />
                  </div>
                ) : businesses.map((biz) => (
                  <BusinessCard
                    key={biz.id || biz.slug}
                    business={biz}
                    onClick={() => setModalBiz(biz)}
                    onReport={() => setCorrectionBiz(biz)}
                  />
                ))}
              </div>

              {/* Pagination */}
              {/* Sin paginacion mientras carga: si no, los botones de la
                  pagina anterior quedaban activos debajo de los esqueletos. */}
              {!loading && totalPages > 1 && !sinResultados && (
                <div className="pagination">
                  <button className="pagination-btn" disabled={estado.pagina <= 1} onClick={() => handlePageChange(estado.pagina - 1)}>Anterior</button>
                  <span className="pagination-info">{estado.pagina} / {totalPages}</span>
                  <button className="pagination-btn" disabled={estado.pagina >= totalPages} onClick={() => handlePageChange(estado.pagina + 1)}>Siguiente</button>
                </div>
              )}
            </div>
          </>
        ) : (
          // Portada: el overlay ocupa el hueco de la rejilla, a la
          // derecha, hasta que se hace la primera busqueda.
          <div className="right-portada">
            <MapOverlay visible hint={avisoSinPunto} />
          </div>
        )}
      </div>

      {modalBiz && <BusinessModal business={modalBiz} onClose={() => setModalBiz(null)} />}

      {/* Formulario "Corregir": se monta aqui, en la raiz y fuera de la
          tarjeta, igual que los demas modales (el overlay es position:fixed,
          y dentro de la tarjeta podria quedar atrapado por un transform). */}
      {correctionBiz && (
        <CorrectionModal business={correctionBiz} onClose={() => setCorrectionBiz(null)} />
      )}

      {showContact && (
        <div className="modal-overlay" onClick={() => setShowContact(false)}>
          {/* .modal-panel, NO .modal-content: esa clase no existe en ningún
              CSS y el modal salía transparente con texto negro sobre el
              overlay oscuro. Ver nota en Home.css. */}
          <div className="modal-panel modal-contact" onClick={e => e.stopPropagation()}>
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

      {/* Badge de version: deja ver que bundle corre ESTA pestana. Si no
          aparece (o no coincide con el de produccion), la pestana esta
          con cache vieja: es lo primero que hay que mirar. */}
      <div className="version-badge" title="Versión desplegada en esta pestaña">
        v{version}
      </div>

      {/* Aviso de version nueva: solo cuando NO se puede recargar sola
          (hay una busqueda encima y se perdia su estado). */}
      {versionNueva && (
        <div className="version-aviso" role="status">
          <span>Nueva versión publicada</span>
          <button className="version-aviso__btn" onClick={() => window.location.reload()}>
            Recargar
          </button>
          <button
            className="version-aviso__cerrar"
            aria-label="Descartar aviso"
            onClick={() => setVersionNueva(null)}
          >
            &#10005;
          </button>
        </div>
      )}
    </div>
  );
}
