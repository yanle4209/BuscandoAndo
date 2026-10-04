import { useEffect, useMemo, useState } from 'react';
import { claveCabecera } from '../municipios';
import api from '../api/axios';
import './Levantamiento.css';

// Donde se guarda el token en este navegador. Es una firma, no una
// sesion: si se borra, se vuelve a pegar. Nada de lo que hace la pagina
// depende de que este guardado.
const CLAVE_TOKEN = 'buscandoando.levantamiento.token';

// R1 / §10-j: el circulo de un envio. El backend lo vuelve a medir — esto
// solo es el aviso previo para que nadie mande algo que ya sabe que no
// va a entrar.
const RADIO_KM = 5;

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

const VACIO = {
  nombre: '',
  telefono: '',
  calle: '',
  sector: '',
  descripcion: '',
  categoria: '',
  whatsapp: '',
  correo: '',
  web: '',
};

// El mismo cruce de nombres que hace el backend: "Baní" y "Bani" son el
// mismo municipio. Aquí solo para amarrar la ficha elegida a su cabecera.
const normal = (texto) => (texto || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, ' ')
  .trim();

// Lo que sin esto no se publica solo (§10-f). Marcarlo distinto al resto
// porque completarlo es lo que saca la ficha del reporte.
const TRIO = ['nombre', 'telefono', 'punto'];

const CONTACTO = ['whatsapp', 'correo', 'web'];

const aCoordenada = (valor) => {
  if (valor === '' || valor === null || valor === undefined) return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
};

// La misma formula que el backend: si no, el aviso de "estas a 7 km" del
// navegador y el rechazo del servidor dirian cosas distintas.
const distanciaKm = (lat1, lng1, lat2, lng2) => {
  const a = (Math.PI / 180);
  const dLat = (lat2 - lat1) * a;
  const dLng = (lng2 - lng1) * a;
  const h = Math.sin(dLat / 2) ** 2
    + Math.cos(lat1 * a) * Math.cos(lat2 * a) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
};

export default function Levantamiento() {
  const [token, setToken] = useState('');
  const [tokenVisible, setTokenVisible] = useState(false);
  const [cabeceras, setCabeceras] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [municipioClave, setMunicipioClave] = useState('');
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [datos, setDatos] = useState(VACIO);
  const [franjas, setFranjas] = useState([]);
  // El estado operativo que declara el formulario. Va como texto —antes
  // era una casilla «está cerrado permanentemente»— porque el reporte
  // cuenta `estado` como faltante y hay que poder completarlo.
  const [estado, setEstado] = useState('');
  const [masDatos, setMasDatos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [geo, setGeo] = useState('');

  // La ficha elegida en el reporte. CON ID el envío pasa a modo
  // completar: se escribe en esa ficha, no se crea otra (Fase D).
  const [fichaId, setFichaId] = useState(null);
  const [fichaMunicipio, setFichaMunicipio] = useState('');
  const [faltanFicha, setFaltanFicha] = useState([]);
  const [cargandoFicha, setCargandoFicha] = useState(false);
  const [avisoFicha, setAvisoFicha] = useState(null);

  // El reporte de su municipio: lo que le dice al colaborador que hacer.
  // Se pide con el MISMO token del envio — el backend solo devuelve el
  // renglon de su municipio (§11-i, "ni reportes ajenos").
  const [reporte, setReporte] = useState({
    fila: null, detalle: null, aviso: null, cargando: false,
  });

  // Una sola carga, usada al validar el token y al refrescar: primero la
  // fila del municipio y, si tiene pendientes, el detalle. El detalle va
  // SOLO, sin esperar un clic: el token ya se validó, y eso es lo que
  // hace que el reporte aparezca de inmediato.
  const cargarReporte = async (t, vivo = () => true) => {
    const { data } = await api.get('/pendientes/', {
      headers: { 'X-Colaborador-Token': t },
    });
    if (!Array.isArray(data)) {
      if (vivo()) {
        setReporte({ fila: null, detalle: null, aviso: data?.detail || null, cargando: false });
      }
      return;
    }
    const fila = data[0] || null;
    const espera = Boolean(fila) && fila.con_pendientes > 0;
    if (vivo()) setReporte({ fila, detalle: null, aviso: null, cargando: espera });
    if (!espera) return;
    try {
      const r = await api.get('/pendientes/', {
        params: { municipio: fila.municipio },
        headers: { 'X-Colaborador-Token': t },
      });
      if (vivo()) {
        setReporte((x) => (x.fila === fila ? { ...x, detalle: r.data, cargando: false } : x));
      }
    } catch {
      if (vivo()) setReporte((x) => ({ ...x, cargando: false }));
    }
  };

  useEffect(() => {
    const t = token.trim();
    if (!t) {
      setReporte({ fila: null, detalle: null, aviso: null, cargando: false });
      return undefined;
    }
    let vivo = true;
    // Con retardo: se teclea el token y sin esto se peticiona cada letra.
    const reloj = setTimeout(() => {
      setReporte((r) => ({ ...r, cargando: true }));
      cargarReporte(t, () => vivo).catch((err) => {
        if (!vivo) return;
        // El 400 lo manda el propio backend con su mensaje («este token
        // no tiene municipio»); el 401 es un token que no vale. El resto
        // —malo, bloqueado, caído el servidor— lo dice el envío, que es
        // la única acción que de verdad importa aquí.
        const detalle = err.response?.status === 401
          ? 'Token no válido o bloqueado. Pídelo al coordinador.'
          : err.response?.status === 400
            ? err.response.data?.detail : null;
        setReporte({ fila: null, detalle: null, aviso: detalle, cargando: false });
      });
    }, 400);
    return () => { vivo = false; clearTimeout(reloj); };
  }, [token]);

  const verReporte = () => {
    const t = token.trim();
    setReporte((r) => ({ ...r, cargando: true }));
    cargarReporte(t).catch(() => setReporte((r) => ({
      ...r,
      aviso: 'No se pudo leer el reporte.',
      cargando: false,
    })));
  };

  // Un ficha concreta del reporte -> el formulario ya rellenado. El
  // backend devuelve solo LA que se pidió (y solo si es de su municipio):
  // poblar con las 148 de golpe sería mandar medio municipio a rellenar
  // UNO.
  const elegirFicha = async (e) => {
    const id = e.target.value;
    setResultado(null);
    setAvisoFicha(null);
    if (!id) {
      setFichaId(null);
      setFaltanFicha([]);
      setFichaMunicipio('');
      return;
    }
    setCargandoFicha(true);
    try {
      const { data } = await api.get('/pendientes/', {
        params: { ficha: id },
        headers: { 'X-Colaborador-Token': token.trim() },
      });
      setDatos({
        nombre: data.nombre || '',
        telefono: data.telefono || '',
        calle: data.calle || '',
        sector: data.sector || '',
        descripcion: data.descripcion || '',
        categoria: data.categoria || '',
        whatsapp: data.whatsapp || '',
        correo: data.correo || '',
        web: data.web || '',
      });
      setLat(data.lat === null || data.lat === undefined ? '' : String(data.lat));
      setLng(data.lng === null || data.lng === undefined ? '' : String(data.lng));
      setEstado(data.operativo || '');
      setFranjas((data.horario || []).map((h, i) => ({
        id: `${data.id}-${i}`,
        day: h.dia || '',
        desde: h.desde || '',
        hasta: h.hasta || '',
      })));
      setFaltanFicha(Array.isArray(data.faltan) ? data.faltan : []);
      setFichaMunicipio(data.municipio || '');
      // El municipio sale solo: quien eligió la ficha no debería tener
      // que reelegir lo que ya está claro.
      const c = cabeceras.find((x) => normal(x.municipio) === normal(data.municipio));
      if (c) setMunicipioClave(claveCabecera(c));
      // WhatsApp, correo y web van escondidos detrás de un botón; si es
      // lo que falta, hay que abrirlos sin que nadie lo busque.
      setMasDatos((data.faltan || []).some((x) => CONTACTO.includes(x)));
      setFichaId(Number(id));
    } catch (err) {
      setFichaId(null);
      setFaltanFicha([]);
      setFichaMunicipio('');
      setAvisoFicha(err.response?.data?.detail || 'No se pudo abrir esa ficha.');
    } finally {
      setCargandoFicha(false);
    }
  };

  // El token y las dos listas que rellenan el formulario. Sin token no se
  // puede probar nada, por eso lo primero que se pide.
  useEffect(() => {
    try {
      const guardado = localStorage.getItem(CLAVE_TOKEN);
      if (guardado) setToken(guardado);
    } catch {
      // Sin localStorage (modo privado): se pega el token a mano cada vez.
    }
    api.get('/cabeceras/')
      .then(({ data }) => setCabeceras(Array.isArray(data) ? data : []))
      .catch(() => setCabeceras([]));
    api.get('/categories/')
      .then(({ data }) => setCategorias(data.results || data))
      .catch(() => setCategorias([]));
  }, []);

  const guardarToken = (valor) => {
    setToken(valor);
    try {
      if (valor) localStorage.setItem(CLAVE_TOKEN, valor);
      else localStorage.removeItem(CLAVE_TOKEN);
    } catch {
      // No se puede recordar, pero se puede usar.
    }
  };

  const porProvincia = useMemo(() => {
    const grupos = new Map();
    cabeceras.forEach((c) => {
      if (!grupos.has(c.provincia)) grupos.set(c.provincia, []);
      grupos.get(c.provincia).push(c);
    });
    return Array.from(grupos.entries())
      .map(([provincia, lista]) => ({
        provincia,
        lista: lista.slice().sort((a, b) => a.municipio.localeCompare(b.municipio, 'es')),
      }))
      .sort((a, b) => a.provincia.localeCompare(b.provincia, 'es'));
  }, [cabeceras]);

  // Mientras se completa una ficha, el municipio que manda es el de la
  // ficha; si alguien lo cambia a mano, manda el que eligió.
  const municipioActual = useMemo(() => {
    if (fichaMunicipio) {
      const c = cabeceras.find((x) => normal(x.municipio) === normal(fichaMunicipio));
      if (c) return claveCabecera(c);
    }
    return municipioClave;
  }, [fichaMunicipio, cabeceras, municipioClave]);

  const cabecera = useMemo(
    () => cabeceras.find((c) => claveCabecera(c) === municipioActual) || null,
    [cabeceras, municipioActual],
  );

  const punto = useMemo(() => [aCoordenada(lat), aCoordenada(lng)], [lat, lng]);
  const distancia = useMemo(() => {
    if (!cabecera || punto[0] === null || punto[1] === null) return null;
    return distanciaKm(punto[0], punto[1], cabecera.lat, cabecera.lng);
  }, [cabecera, punto]);

  const dentroDelCirculo = distancia !== null && distancia <= RADIO_KM;

  const elegirPuntoCercano = (nuevaLat, nuevaLng) => {
    setLat(String(nuevaLat.toFixed(6)));
    setLng(String(nuevaLng.toFixed(6)));
    // El municipio de un envio lo declara quien envia, pero elegirlo a mano
    // y equivocarse cuesta un rechazo. Si el punto ya esta en un circulo,
    // el municipio sale solo: el mismo criterio que usa el servidor.
    const cercana = cabeceras
      .map((c) => ({ c, d: distanciaKm(nuevaLat, nuevaLng, c.lat, c.lng) }))
      .filter((x) => x.d <= RADIO_KM)
      .sort((a, b) => a.d - b.d)[0];
    if (cercana) setMunicipioClave(claveCabecera(cercana.c));
  };

  const pedirGps = () => {
    if (!navigator.geolocation) {
      setGeo('Este navegador no tiene GPS. Escribe las coordenadas a mano.');
      return;
    }
    setGeo('');
    navigator.geolocation.getCurrentPosition(
      (p) => {
        elegirPuntoCercano(p.coords.latitude, p.coords.longitude);
        setGeo('');
      },
      () => setGeo('No se pudo leer la ubicación. Escribe las coordenadas a mano.'),
      { maximumAge: 30000, timeout: 15000, enableHighAccuracy: false },
    );
  };

  const cambiar = (campo) => (e) => setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const agregarFranja = () => {
    setFranjas((f) => [...f, { id: `${Date.now()}-${f.length}`, day: '', desde: '', hasta: '' }]);
  };

  const cambiarFranja = (i, campo) => (e) => {
    const valor = e.target.value;
    setFranjas((f) => f.map((fila, j) => (j === i ? { ...fila, [campo]: valor } : fila)));
  };

  const quitarFranja = (i) => setFranjas((f) => f.filter((_, j) => j !== i));

  const limpiarFicha = () => {
    setDatos(VACIO);
    setFranjas([]);
    setEstado('');
    setMasDatos(false);
    // ...y se suelta la ficha elegida: lo que sigue empieza en blanco.
    setFichaId(null);
    setFaltanFicha([]);
    setFichaMunicipio('');
    setAvisoFicha(null);
  };

  const enviar = async (e) => {
    e.preventDefault();
    if (enviando) return;

    setEnviando(true);
    setResultado(null);

    const cuerpo = {
      ...datos,
      municipio: cabecera ? cabecera.municipio : '',
      lat: punto[0],
      lng: punto[1],
      cerrado: estado === 'cerrado' || estado === 'cerrado-permanente',
      estado,
      horario: franjas
        .filter((f) => f.day && f.desde && f.hasta)
        .map((f) => ({ dia: f.day, desde: f.desde, hasta: f.hasta })),
      // Con id el backend va en modo completar: se escribe en ESA ficha
      // (y solo si es del municipio del token).
      ...(fichaId ? { ficha: fichaId } : {}),
    };

    try {
      const { data } = await api.post('/levantamiento/', cuerpo, {
        headers: { 'X-Colaborador-Token': token.trim() },
      });
      setResultado({
        tipo: data.estado,
        motivos: data.motivos || [],
        faltan: data.faltan || [],
        completado: data.completado || [],
      });
      // Listo para el siguiente: solo se borra la ficha, no el token ni
      // el municipio, que son lo que se repite en una ronda de campo.
      limpiarFicha();
    } catch (err) {
      const status = err.response?.status;
      const data = err.response?.data || {};
      if (status === 401) {
        setResultado({ tipo: 'firma', motivos: [data.detail || ''] });
      } else if (status === 403) {
        setResultado({ tipo: 'otro', motivos: [data.detail || ''] });
      } else if (status === 429) {
        setResultado({ tipo: 'techo', motivos: [data.detail || ''] });
      } else if (status === 400) {
        setResultado({
          tipo: data.estado || 'rechazado',
          motivos: data.motivos || [],
          faltan: data.faltan || [],
          completado: [],
        });
      } else {
        setResultado({ tipo: 'sin-red', motivos: [] });
      }
    } finally {
      setEnviando(false);
      // El reporte se relee con CADA envío, también con los que no
      // entraron: lo que se ve arriba tiene que ser lo que hay ahora
      // mismo y no lo que había al abrir la pantalla. Un envío
      // rechazado no mueve la base, pero si un segundo colaborador acaba
      // de completar una ficha de este municipio, el listado viejo
      // engaña — y de ahí salen las dobles cargas.
      if (token.trim()) cargarReporte(token.trim()).catch(() => {});
    }
  };

  const listo = token.trim() !== '' && datos.nombre.trim() !== '' && cabecera;

  // Resaltado de lo que falta. Solo mientras se completa una ficha ya
  // existente: en un alta nueva TODO está vacío y pintar la mitad del
  // formulario sería puro ruido.
  const falta = (campo) => fichaId !== null && faltanFicha.includes(campo);

  const claseFalta = (...campos) => {
    const hitos = campos.filter((c) => falta(c));
    if (hitos.length === 0) return 'lev-field';
    const trio = hitos.some((c) => TRIO.includes(c));
    return `lev-field lev-field--falta${trio ? ' lev-field--trio' : ''}`;
  };

  const marca = (campo) => (falta(campo)
    ? <span className="lev-falta-marca">falta</span>
    : null);

  return (
    <div className="lev-page">
      <header className="lev-top">
        <div>
          <p className="lev-top-eyebrow">Herramienta interna</p>
          <h1 className="lev-top-title">Levantamiento</h1>
        </div>
        <a className="lev-top-volver" href="/">Volver al buscador</a>
      </header>

      <p className="lev-intro">
        Cada envío lo <strong>firma tu token</strong>: no abre nada, solo deja constancia de quién
        lo mandó. El sistema valida, cruza con lo que ya existe y publica solo si trae{' '}
        <strong>nombre + teléfono + punto</strong>. Si falta alguno no se descarta: queda en el
        reporte del municipio para que lo completen.
      </p>

      <form className="lev-form" onSubmit={enviar}>
        <section className="lev-card">
          <h2 className="lev-card-title">Tu firma</h2>
          <div className="lev-field">
            <label htmlFor="lev-token">Token de colaborador</label>
            <div className="lev-token-row">
              <input
                id="lev-token"
                type={tokenVisible ? 'text' : 'password'}
                value={token}
                onChange={(e) => guardarToken(e.target.value)}
                placeholder="Pega aquí el token que te dieron"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                className="lev-btn-ghost"
                onClick={() => setTokenVisible((v) => !v)}
              >
                {tokenVisible ? 'Ocultar' : 'Ver'}
              </button>
            </div>
            <small>Se guarda solo en este navegador.</small>
          </div>
        </section>

        {/* §11.1 + lo decidido: el reporte de incompletas POR MUNICIPIO,
            que es lo que le dice al colaborador que hacer. El backend solo
            devuelve su renglon; los demas municipios no existen aqui. */}
        {token.trim() && (reporte.cargando || reporte.aviso || reporte.fila) && (
          <section className="lev-card">
            <h2 className="lev-card-title">Lo que falta en tu municipio</h2>

            {reporte.aviso && <p className="lev-aviso">{reporte.aviso}</p>}

            {reporte.fila && (
              <>
                <p className="lev-resumen">
                  <strong>
                    {reporte.fila.municipio}
                    {reporte.fila.provincia ? ` (${reporte.fila.provincia})` : ''}
                  </strong>
                  {' — '}
                  {reporte.fila.total === 0
                    ? 'todavía no hay fichas aquí.'
                    : `${reporte.fila.total} ficha${reporte.fila.total !== 1 ? 's' : ''}`
                      + `, ${reporte.fila.con_pendientes} con algo faltando`
                      + `, ${reporte.fila.en_revision} esperando publicarse.`}
                </p>

                {/* El selector: la puerta al modo completar. Elegir una
                    ficha puebla el formulario con lo que ya hay y le marca
                    lo que falta; el envío va con su id. */}
                {reporte.detalle && reporte.detalle.fichas.length > 0 && (
                  <div className="lev-field lev-elegir">
                    <label htmlFor="lev-elegir">Negocio a completar</label>
                    <select id="lev-elegir" value={fichaId ?? ''} onChange={elegirFicha}>
                      <option value="">— Elige uno de la lista —</option>
                      {reporte.detalle.fichas.map((f) => (
                        <option key={f.id} value={f.id}>
                          {f.nombre}
                          {f.faltan.length > 0 ? ` — le falta ${f.faltan.length}` : ''}
                        </option>
                      ))}
                    </select>
                    {cargandoFicha && <p className="lev-aviso">Abriendo la ficha…</p>}
                    {avisoFicha && <p className="lev-aviso">{avisoFicha}</p>}
                    {fichaId !== null && (
                      <small className="lev-elegir-nota">
                        Formulario rellenado con lo que ya había. Lo marcado en amarillo es lo que
                        todavía falta rellenar.
                      </small>
                    )}
                  </div>
                )}

                {reporte.fila.total > 0 && reporte.fila.con_pendientes > 0 && (
                  <button type="button" className="lev-btn-ghost" onClick={verReporte}>
                    {reporte.detalle ? 'Actualizar' : `Ver las ${reporte.fila.con_pendientes} que le falta algo`}
                  </button>
                )}

                {reporte.detalle && (
                  <div className="lev-detalle">
                    <h3>Por campo faltante</h3>
                    <ul className="lev-por-campo">
                      {reporte.detalle.por_campo.map((f) => (
                        <li key={f.campo} className={f.en_trio ? 'es-trio' : ''}>
                          {f.etiqueta}
                          <span className="lev-por-campo-n">{f.cantidad}</span>
                          {f.en_trio && <span className="lev-trio-marca">bloquea</span>}
                        </li>
                      ))}
                    </ul>

                    <h3>Fichas</h3>
                    <ul className="lev-fichas">
                      {reporte.detalle.fichas.map((f) => (
                        <li key={f.id}>
                          <span className="lev-ficha-nombre">{f.nombre}</span>
                          <span className={`lev-ficha-estado ${f.estado}`}>
                            {f.estado === 'publicado' ? 'publicada' : 'sin publicar'}
                          </span>
                          <span className="lev-ficha-falta">
                            Falta: {f.faltan.map((c) => ETIQUETAS[c] || c).join(', ')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}

            {reporte.cargando && <p className="lev-aviso">Cargando…</p>}
          </section>
        )}

        <section className="lev-card">
          <h2 className="lev-card-title">Dónde está</h2>
          <div className="lev-field">
            <label htmlFor="lev-municipio">Municipio</label>
            <select
              id="lev-municipio"
              value={municipioActual}
              onChange={(e) => {
                setMunicipioClave(e.target.value);
                setFichaMunicipio('');
              }}
            >
              <option value="">Elige el municipio</option>
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

          <div className="lev-geo">
            <button type="button" className="lev-btn" onClick={pedirGps}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
              </svg>
              Ubicación del negocio (GPS)
            </button>
            <div className={`lev-coordenadas${falta('punto') ? ' lev-coordenadas--falta' : ''}`}>
              <input
                aria-label="Latitud"
                type="text"
                inputMode="decimal"
                placeholder="Latitud"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
              />
              <input
                aria-label="Longitud"
                type="text"
                inputMode="decimal"
                placeholder="Longitud"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
              />
            </div>
          </div>

          {geo && <p className="lev-aviso">{geo}</p>}

          {cabecera && distancia !== null && (
            <p className={`lev-radio ${dentroDelCirculo ? 'lev-radio--dentro' : 'lev-radio--fuera'}`}>
              {dentroDelCirculo
                ? `A ${distancia.toFixed(2)} km de la cabecera de ${cabecera.municipio} — dentro del círculo de ${RADIO_KM} km.`
                : `A ${distancia.toFixed(2)} km de la cabecera de ${cabecera.municipio}. El envío se rechazará: el círculo es de ${RADIO_KM} km.`}
            </p>
          )}
          {!cabecera && punto[0] !== null && (
            <p className="lev-aviso">Elige el municipio para poder medir la distancia.</p>
          )}

          <div className="lev-row">
            <div className={claseFalta('direccion')}>
              <label htmlFor="lev-calle">Calle {marca('direccion')}</label>
              <input id="lev-calle" type="text" value={datos.calle} onChange={cambiar('calle')} placeholder="Calle 1 #10" />
            </div>
            <div className="lev-field">
              <label htmlFor="lev-sector">Sector</label>
              <input id="lev-sector" type="text" value={datos.sector} onChange={cambiar('sector')} placeholder="Ensanche" />
            </div>
          </div>
        </section>

        <section className="lev-card">
          <h2 className="lev-card-title">El negocio</h2>
          <div className={claseFalta('nombre')}>
            <label htmlFor="lev-nombre">Nombre * {marca('nombre')}</label>
            <input id="lev-nombre" type="text" value={datos.nombre} onChange={cambiar('nombre')} placeholder="Panadería El Trigal" />
          </div>

          <div className="lev-row">
            <div className={claseFalta('telefono')}>
              <label htmlFor="lev-telefono">Teléfono {marca('telefono')}</label>
              <input id="lev-telefono" type="tel" value={datos.telefono} onChange={cambiar('telefono')} placeholder="809-555-1111" />
              <small>Sin teléfono no se publica solo: queda en el reporte.</small>
            </div>
            <div className={claseFalta('categoria')}>
              <label htmlFor="lev-categoria">Categoría {marca('categoria')}</label>
              <select id="lev-categoria" value={datos.categoria} onChange={cambiar('categoria')}>
                <option value="">La que ya exista</option>
                {categorias.map((cat) => (
                  <option key={cat.id} value={cat.name}>{cat.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className={claseFalta('descripcion')}>
            <label htmlFor="lev-descripcion">Descripción {marca('descripcion')}</label>
            <textarea id="lev-descripcion" rows={2} value={datos.descripcion} onChange={cambiar('descripcion')} placeholder="Pan artesanal, venta por libra" />
          </div>

          <div className={claseFalta('estado')}>
            <label htmlFor="lev-estado">Estado {marca('estado')}</label>
            <select id="lev-estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Sin decidir</option>
              <option value="abierto">Abierto</option>
              <option value="cerrado">Cerrado</option>
              <option value="por-horario">Según horario</option>
              <option value="cerrado-permanente">Cerrado permanentemente</option>
            </select>
          </div>

          <div className={`lev-horario${falta('horario') ? ' lev-horario--falta' : ''}`}>
            <div className="lev-horario-head">
              <h3>Horario {marca('horario')}</h3>
              <button type="button" className="lev-btn-ghost" onClick={agregarFranja}>
                + Añadir día
              </button>
            </div>
            {franjas.map((f, i) => (
              <div className="lev-horario-fila" key={f.id}>
                <select aria-label="Día" value={f.day} onChange={cambiarFranja(i, 'day')}>
                  <option value="">Día</option>
                  {DIAS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <input aria-label="Desde" type="time" value={f.desde} onChange={cambiarFranja(i, 'desde')} />
                <span className="lev-horario-sep">—</span>
                <input aria-label="Hasta" type="time" value={f.hasta} onChange={cambiarFranja(i, 'hasta')} />
                <button
                  type="button"
                  className="lev-btn-ghost lev-btn-quitar"
                  onClick={() => quitarFranja(i)}
                  aria-label="Quitar este día"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            className="lev-btn-ghost lev-desplegar"
            onClick={() => setMasDatos((v) => !v)}
          >
            {masDatos ? 'Ocultar otros datos' : 'Añadir WhatsApp, correo o web'}
          </button>

          {masDatos && (
            <div className="lev-row">
              <div className={claseFalta('whatsapp')}>
                <label htmlFor="lev-whatsapp">WhatsApp {marca('whatsapp')}</label>
                <input id="lev-whatsapp" type="tel" value={datos.whatsapp} onChange={cambiar('whatsapp')} />
              </div>
              <div className={claseFalta('correo')}>
                <label htmlFor="lev-correo">Correo {marca('correo')}</label>
                <input id="lev-correo" type="email" value={datos.correo} onChange={cambiar('correo')} />
              </div>
              <div className={claseFalta('web')}>
                <label htmlFor="lev-web">Sitio web {marca('web')}</label>
                <input id="lev-web" type="url" value={datos.web} onChange={cambiar('web')} />
              </div>
            </div>
          )}
        </section>

        <button type="submit" className="lev-enviar" disabled={!listo || enviando}>
          {enviando ? 'Enviando…' : 'Enviar'}
        </button>
        {!listo && (
          <p className="lev-falta">
            {!token.trim() && 'Falta tu token. '}
            {!datos.nombre.trim() && 'Falta el nombre. '}
            {!cabecera && 'Falta el municipio.'}
          </p>
        )}
      </form>

      {resultado && <Resultado r={resultado} />}
    </div>
  );
}

const ETIQUETAS = {
  nombre: 'nombre',
  telefono: 'teléfono',
  punto: 'punto (coordenadas)',
  categoria: 'categoría',
  direccion: 'dirección',
  horario: 'horario',
  whatsapp: 'whatsapp',
  correo: 'correo',
  web: 'sitio web',
  descripcion: 'descripción',
  estado: 'estado operativo',
};

const COMPLETADOS = {
  contacto: 'contacto',
  phone: 'teléfono',
  whatsapp: 'whatsapp',
  email: 'correo',
  website: 'web',
  street: 'calle',
  sector: 'sector',
  horario: 'horario',
  nombre: 'nombre',
  descripcion: 'descripción',
  categoria: 'categoría',
  estado: 'estado operativo',
  punto: 'punto',
};

function Resultado({ r }) {
  // Los tres que el servidor ACEPTO llevan la palomita delante: es la
  // unica señal de que el envío entró, y tiene que leerse de un vistazo.
  const titulo = {
    publicado: ['✓ Aceptado y publicado', 'lev-ok'],
    pendiente: ['✓ Aceptado: se queda en el reporte', 'lev-ok'],
    duplicado: ['✓ Aceptado: ficha existente completada', 'lev-ok'],
    rechazado: ['No se aceptó', 'lev-malo'],
    firma: ['Token no válido', 'lev-malo'],
    otro: ['A este token le toca otro municipio', 'lev-malo'],
    techo: ['Demasiados envíos', 'lev-malo'],
    'sin-red': ['Sin conexión', 'lev-malo'],
  }[r.tipo] || ['Respuesta', 'lev-malo'];

  const aceptado = ['publicado', 'pendiente', 'duplicado'].includes(r.tipo);

  const faltan = (r.faltan || []).map((c) => ETIQUETAS[c] || c);
  const completado = (r.completado || []).map((c) => COMPLETADOS[c] || c);

  return (
    <div className={`lev-resultado ${titulo[1]}`}>
      <h2>{titulo[0]}</h2>

      {r.motivos?.length > 0 && (
        <ul className="lev-lista">
          {r.motivos.map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}

      {completado.length > 0 && (
        <p>
          Se le completó: <strong>{completado.join(', ')}</strong>.
        </p>
      )}

      {r.tipo === 'pendiente' && faltan.length > 0 && (
        <p>
          Está en el reporte de su municipio. Le falta:{' '}
          <strong>{faltan.join(', ')}</strong>.
        </p>
      )}

      {r.tipo === 'duplicado' && completado.length === 0 && (
        <p>
          No había nada nuevo que añadir.
          {faltan.length > 0 && ` Aún le falta: ${faltan.join(', ')}.`}
        </p>
      )}

      {r.tipo === 'publicado' && faltan.length > 0 && (
        <p>Todavía le falta: {faltan.join(', ')}.</p>
      )}

      {r.tipo === 'firma' && (
        <p>Revisa el token o pide que te reactive el tuyo.</p>
      )}
      {r.tipo === 'otro' && (
        <p>Cada token trabaja su municipio. Elige una ficha de tu reporte.</p>
      )}
      {r.tipo === 'techo' && <p>Espera un minuto y vuelve a intentarlo.</p>}
      {r.tipo === 'sin-red' && <p>No se pudo hablar con el servidor. Intenta otra vez.</p>}

      {aceptado && (
        <p className="lev-resultado-nota">
          El reporte de tu municipio <strong>ya se actualizó</strong> con este
          envío: la lista de arriba está al día y el negocio que acabas de
          enviar ya no aparece como pendiente. Elige el siguiente cuando
          quieras.
        </p>
      )}
    </div>
  );
}
