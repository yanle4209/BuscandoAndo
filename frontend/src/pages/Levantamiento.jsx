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
  const [cerrado, setCerrado] = useState(false);
  const [masDatos, setMasDatos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [geo, setGeo] = useState('');

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

  const cabecera = useMemo(
    () => cabeceras.find((c) => claveCabecera(c) === municipioClave) || null,
    [cabeceras, municipioClave],
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
    setCerrado(false);
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
      cerrado,
      horario: franjas
        .filter((f) => f.day && f.desde && f.hasta)
        .map((f) => ({ dia: f.day, desde: f.desde, hasta: f.hasta })),
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
    }
  };

  const listo = token.trim() !== '' && datos.nombre.trim() !== '' && cabecera;

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

        <section className="lev-card">
          <h2 className="lev-card-title">Dónde está</h2>
          <div className="lev-field">
            <label htmlFor="lev-municipio">Municipio</label>
            <select
              id="lev-municipio"
              value={municipioClave}
              onChange={(e) => setMunicipioClave(e.target.value)}
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
              Usar mi ubicación
            </button>
            <div className="lev-coordenadas">
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
            <div className="lev-field">
              <label htmlFor="lev-calle">Calle</label>
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
          <div className="lev-field">
            <label htmlFor="lev-nombre">Nombre *</label>
            <input id="lev-nombre" type="text" value={datos.nombre} onChange={cambiar('nombre')} placeholder="Panadería El Trigal" />
          </div>

          <div className="lev-row">
            <div className="lev-field">
              <label htmlFor="lev-telefono">Teléfono</label>
              <input id="lev-telefono" type="tel" value={datos.telefono} onChange={cambiar('telefono')} placeholder="809-555-1111" />
              <small>Sin teléfono no se publica solo: queda en el reporte.</small>
            </div>
            <div className="lev-field">
              <label htmlFor="lev-categoria">Categoría</label>
              <select id="lev-categoria" value={datos.categoria} onChange={cambiar('categoria')}>
                <option value="">La que ya exista</option>
                {categorias.map((cat) => (
                  <option key={cat.id} value={cat.name}>{cat.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="lev-field">
            <label htmlFor="lev-descripcion">Descripción</label>
            <textarea id="lev-descripcion" rows={2} value={datos.descripcion} onChange={cambiar('descripcion')} placeholder="Pan artesanal, venta por libra" />
          </div>

          <label className="lev-check">
            <input type="checkbox" checked={cerrado} onChange={(e) => setCerrado(e.target.checked)} />
            Está cerrado permanentemente
          </label>

          <div className="lev-horario">
            <div className="lev-horario-head">
              <h3>Horario</h3>
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
              <div className="lev-field">
                <label htmlFor="lev-whatsapp">WhatsApp</label>
                <input id="lev-whatsapp" type="tel" value={datos.whatsapp} onChange={cambiar('whatsapp')} />
              </div>
              <div className="lev-field">
                <label htmlFor="lev-correo">Correo</label>
                <input id="lev-correo" type="email" value={datos.correo} onChange={cambiar('correo')} />
              </div>
              <div className="lev-field">
                <label htmlFor="lev-web">Sitio web</label>
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
};

function Resultado({ r }) {
  const titulo = {
    publicado: ['Publicado', 'lev-ok'],
    pendiente: ['Recibido, le falta el trio', 'lev-ok'],
    duplicado: ['Ya existía: se completó', 'lev-ok'],
    rechazado: ['No se aceptó', 'lev-malo'],
    firma: ['Token no válido', 'lev-malo'],
    techo: ['Demasiados envíos', 'lev-malo'],
    'sin-red': ['Sin conexión', 'lev-malo'],
  }[r.tipo] || ['Respuesta', 'lev-malo'];

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

      {r.tipo === 'pendiente' && faltan.length > 0 && (
        <p>
          Está en el reporte de su municipio. Le falta:{' '}
          <strong>{faltan.join(', ')}</strong>.
        </p>
      )}

      {r.tipo === 'duplicado' && (
        <p>
          {completado.length > 0
            ? `Se le completó: ${completado.join(', ')}.`
            : 'No había nada nuevo que añadir.'}
          {faltan.length > 0 && ` Aún le falta: ${faltan.join(', ')}.`}
        </p>
      )}

      {r.tipo === 'publicado' && faltan.length > 0 && (
        <p>Todavía le falta: {faltan.join(', ')}.</p>
      )}

      {r.tipo === 'firma' && (
        <p>Revisa el token o pide que te reactive el tuyo.</p>
      )}
      {r.tipo === 'techo' && <p>Espera un minuto y vuelve a intentarlo.</p>}
      {r.tipo === 'sin-red' && <p>No se pudo hablar con el servidor. Intenta otra vez.</p>}
    </div>
  );
}
