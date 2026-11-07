import { useEffect, useMemo, useRef, useState } from 'react';
import { claveCabecera } from '../municipios';
import { partirTelefono } from '../telefono';
import api from '../api/axios';
import './Levantamiento.css';

// Donde se guarda el token en este navegador. Es una firma, no una
// sesion: si se borra, se vuelve a pegar. Nada de lo que hace la pagina
// depende de que este guardado.
const CLAVE_TOKEN = 'buscandoando.levantamiento.token';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

const VACIO = {
  nombre: '',
  // El telefono no vive en `datos`: va como lista (`telefonos`), porque
  // el negocio con mas de uno pide mas de un campo. Al enviar se une en
  // la cadena que el servidor entiende.
  calle: '',
  sector: '',
  referencias: '',
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

// Los siete dias, SIEMPRE en pantalla, igual que en el formulario de
// creacion del negocio: lo que ya se sabe del horario se coloca solo y
// lo que falta queda vacio esperando. Un mismo dia con dos franjas
// (manana y tarde) entra como fila de mas, para no partir el horario de
// la ficha para que quepa en la pantalla.
const diasBase = (horario = []) => {
  const usados = new Set();
  const filas = DIAS.map((dia, i) => {
    const h = horario.find((x) => !usados.has(x) && normal(x.dia) === normal(dia));
    if (h) usados.add(h);
    return {
      id: `dia-${i}`,
      day: dia,
      desde: (h && h.desde) || '',
      hasta: (h && h.hasta) || '',
    };
  });
  horario.forEach((h, i) => {
    if (usados.has(h)) return;
    filas.push({
      id: `dia-extra-${i}`,
      day: h.dia || '',
      desde: h.desde || '',
      hasta: h.hasta || '',
    });
  });
  return filas;
};

// Lo que sin esto no se publica solo (§10-f): nombre, direccion, telefono,
// imagen y punto. Marcarlo distinto al resto porque completarlo es lo que
// saca la ficha de la lista de revision.
const OBLIGATORIOS = ['nombre', 'direccion', 'telefono', 'imagen', 'punto'];

const CONTACTO = ['whatsapp', 'correo', 'web'];

// Los doce campos del reporte, en el mismo orden que pendientes.py. Aqui
// solo se usan para medir en vivo cuanto le queda a la ficha abierta (el
// «imagen» lo decide el servidor con las fotos que la ficha ya tenga).
const CAMPOS = [
  'nombre', 'direccion', 'telefono', 'imagen', 'punto', 'categoria',
  'horario', 'whatsapp', 'correo', 'web', 'descripcion', 'estado',
];

// El techo de fotos por ficha: el MISMO que en el admin (modelo
// BusinessImage). Aqui solo se cuenta y se corta el selector; quien
// corta de verdad es el servidor.
const MAX_FOTOS = 5;
// El mismo techo que en el servidor (validacion.MAX_TELEFONOS): cinco
// es un negocio con varios numeros, no un directorio telefonico.
const MAX_TELEFONOS = 5;

// Valor centinela del desplegable: no es una categoria, es la opcion
// que abre el campo de texto para crear una.
const CATEGORIA_NUEVA = '__nueva__';

const aCoordenada = (valor) => {
  if (valor === '' || valor === null || valor === undefined) return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
};

export default function Levantamiento() {
  const [token, setToken] = useState('');
  const [tokenVisible, setTokenVisible] = useState(false);
  // Dos pantallas: primero SOLO el token y, cuando el servidor lo
  // acepta, la de trabajo. El formulario no puede vivir dentro del
  // login: el acceso es una cosa y el trabajo otra.
  const [dentro, setDentro] = useState(false);
  const [validando, setValidando] = useState(false);
  const [errorAcceso, setErrorAcceso] = useState(null);
  const [cabeceras, setCabeceras] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [datos, setDatos] = useState(VACIO);
  const [franjas, setFranjas] = useState(() => diasBase());
  // El estado operativo que declara el formulario. Va como texto —antes
  // era una casilla «está cerrado permanentemente»— porque el reporte
  // cuenta `estado` como faltante y hay que poder completarlo.
  const [estado, setEstado] = useState('');
  const [masDatos, setMasDatos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);
  // Que dia pide copiar el horario de otro (null = ninguno). El popup es
  // de React, no del DOM: sin eso habria dos formas de ver lo mismo.
  const [copiarDe, setCopiarDe] = useState(null);

  // La ficha elegida en el reporte. CON ID el envío pasa a modo
  // completar: se escribe en esa ficha, no se crea otra (Fase D).
  const [fichaId, setFichaId] = useState(null);
  const [fichaMunicipio, setFichaMunicipio] = useState('');
  const [faltanFicha, setFaltanFicha] = useState([]);
  const [cargandoFicha, setCargandoFicha] = useState(false);
  const [avisoFicha, setAvisoFicha] = useState(null);

  // ------------------------------ las fotos ---------------------------
  // Las fotos nuevas que estan por mandar, con su URL de preview para
  // poder verlas y quitarlas antes de enviar. El techo es MAX_FOTOS por
  // ficha CONTANDO las que la ficha ya tiene: `fotosExistentes` viene
  // en el detalle del reporte (`imagenes`) y es lo que hace el limite
  // 5 - N del formulario.
  const [fotos, setFotos] = useState([]);
  const [fotosExistentes, setFotosExistentes] = useState(0);

  // «Crear categoría nueva…» elegido en el desplegable. El nombre se
  // teclea en el MISMO datos.categoria y al enviar se manda la bandera
  // `categoria_nueva`: el servidor la valida y la da de alta en el
  // momento (sin ella solo se busca, que es lo de siempre).
  const [creandoCategoria, setCreandoCategoria] = useState(false);

  // Varios telefonos, uno por campo: se editan como lista y al enviar
  // se mandan como la cadena `; ` que el backend guarda en
  // contact.phone (la convencion de OSM, que ya partia asi).
  const [telefonos, setTelefonos] = useState(['']);

  const fotosTotal = fotosExistentes + fotos.length;
  const fotosLlenas = fotosTotal >= MAX_FOTOS;
  // La obligatoria: hasta que la ficha tenga UNA foto no se puede
  // enviar. Si ya tiene (fotosExistentes > 0) no hace falta mandar mas.
  const faltaFoto = fotosTotal === 0;

  const agregarFotos = (e) => {
    const elegidas = Array.from(e.target.files || []);
    e.target.value = '';
    if (elegidas.length === 0) return;
    setFotos((fs) => {
      const cupo = Math.max(0, MAX_FOTOS - fotosExistentes - fs.length);
      return [
        ...fs,
        ...elegidas.slice(0, cupo).map((file, i) => ({
          id: `${Date.now()}-${fs.length}-${i}`,
          file,
          url: URL.createObjectURL(file),
        })),
      ];
    });
  };

  const quitarFoto = (id) => {
    const fuera = fotos.find((f) => f.id === id);
    if (fuera) URL.revokeObjectURL(fuera.url);
    setFotos((fs) => fs.filter((f) => f.id !== id));
  };

  // Soltar las pendientes (y sus previews): al cambiar de ficha, al
  // limpiar y al salir. Pertenecian a lo que estaba en pantalla.
  const soltarFotos = () => {
    fotos.forEach((f) => URL.revokeObjectURL(f.url));
    setFotos([]);
  };

  // Cada apertura de ficha se numera, igual que en Home y en la ficha
  // completa: elegir dos seguido (o cambiar de ficha mientras la otra
  // vuela) podia resolverse AL REVES y el formulario quedarse poblado
  // con la ficha equivocada, diciendo ademas "falta" lo que en realidad
  // sobra.
  const fichaRef = useRef(0);

  // El reporte de su municipio: lo que le dice al colaborador que hacer.
  // Se pide con el MISMO token del envio — el backend solo devuelve el
  // renglon de su municipio (§11-i, "ni reportes ajenos").
  const [reporte, setReporte] = useState({
    fila: null, detalle: null, aviso: null, cargando: false,
  });

  // El filtro de categoria de la tarjeta ('' = todas): solo cambia el
  // DETALLE —listas, chips y desglose—; el renglon del municipio sigue
  // siendo el suyo y, con filtro, el resumen cuenta lo de la categoria.
  const [categoria, setCategoria] = useState('');

  // Las fichas que YA no le deben nada en ESTA sesion. El backend solo
  // manda lo que falta —revision y publicadas con faltantes—, y sin este
  // registro la fila se borraria en vez de ponerse verde: es la
  // confirmacion del trabajo hecho, no un dato del servidor.
  const [hechas, setHechas] = useState([]);

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
    // Dos listas mas la de pospuestos: hay trabajo mientras quede
    // ALGO en revision, algo publicado con faltantes o algo pospuesto.
    const espera = Boolean(fila)
      && (fila.con_revision > 0 || fila.con_publicadas > 0
        || fila.con_pospuestos > 0);
    // El detalle anterior se conserva mientras llega el nuevo: sin eso la
    // lista parpadearia vacia con cada envio y se perdia justo la
    // confirmacion que el colaborador acaba de ganarse. Solo si sigue
    // siendo su municipio y todavia hay pendientes; si ya no queda nada,
    // el reporte vacio es exactamente lo que hay que enseñar.
    if (vivo()) {
      setReporte((x) => ({
        fila,
        detalle: espera && x.detalle && normal(x.detalle.municipio) === normal(fila.municipio)
          ? x.detalle
          : null,
        aviso: null,
        cargando: espera,
      }));
    }
    if (!espera) return;
    try {
      const r = await api.get('/pendientes/', {
        params: {
          municipio: fila.municipio,
          ...(categoria ? { categoria } : {}),
        },
        headers: { 'X-Colaborador-Token': t },
      });
      if (vivo()) {
        setReporte((x) => (x.fila === fila ? { ...x, detalle: r.data, cargando: false } : x));
      }
    } catch {
      if (vivo()) setReporte((x) => ({ ...x, cargando: false }));
    }
  };

  // La validacion ES la carga del reporte: se manda el token y, si el
  // servidor lo acepta, la pantalla de trabajo se abre con el reporte de
  // SU municipio ya cargado. Si lo rechaza no se abre nada y el error se
  // queda debajo del campo, en el login.
  const entrarConToken = async (t) => {
    setValidando(true);
    setErrorAcceso(null);
    setReporte((r) => ({ ...r, cargando: true }));
    try {
      await cargarReporte(t);
      setDentro(true);
      return true;
    } catch (err) {
      setReporte({ fila: null, detalle: null, aviso: null, cargando: false });
      // El 400 lo manda el propio backend con su mensaje («este token no
      // tiene municipio»); el 401 es un token que no vale.
      setErrorAcceso(
        err.response?.status === 401
          ? 'Token no válido o bloqueado. Pídelo al coordinador.'
          : err.response?.status === 400
            ? (err.response.data?.detail || 'Este token no tiene municipio asignado.')
            : 'No se pudo hablar con el servidor. Intenta otra vez.',
      );
      return false;
    } finally {
      setValidando(false);
    }
  };

  const verReporte = () => {
    const t = token.trim();
    setReporte((r) => ({ ...r, cargando: true }));
    cargarReporte(t).catch(() => setReporte((r) => ({
      ...r,
      aviso: 'No se pudo leer el reporte.',
      cargando: false,
    })));
  };

  // El filtro de categoria: solo cambia el DETALLE (listas, chips y
  // desglose), asi que se pide otra vez con el slug nuevo sin tocar el
  // renglon. Las demas cargas —envio, refresco, posponer— reusan la
  // categoria abierta.
  const cambiarCategoria = async (cat) => {
    setCategoria(cat);
    const fila = reporte.fila;
    if (!fila) return;
    const t = token.trim();
    setReporte((x) => ({ ...x, cargando: true }));
    try {
      const r = await api.get('/pendientes/', {
        params: {
          municipio: fila.municipio,
          ...(cat ? { categoria: cat } : {}),
        },
        headers: { 'X-Colaborador-Token': t },
      });
      setReporte((x) => (x.fila === fila
        ? { ...x, detalle: r.data, cargando: false }
        : x));
    } catch {
      setReporte((x) => ({ ...x, cargando: false }));
    }
  };

  // Posponer/retomar: el gesto de «esta no la voy a completar» —o no
  // se puede, que da igual—. El servidor lo guarda por dueno y el
  // reporte entero se relee, para que listas, chips y contadores
  // digan siempre lo mismo.
  const posponer = async (id, valor) => {
    const t = token.trim();
    try {
      await api.post(
        '/pospuesto/',
        { ficha: id, pospuesto: valor },
        { headers: { 'X-Colaborador-Token': t } },
      );
      await cargarReporte(t);
    } catch (err) {
      setReporte((x) => ({
        ...x,
        aviso: err.response?.data?.detail || 'No se pudo actualizar la lista.',
      }));
    }
  };

  // Una ficha concreta del reporte -> el formulario ya rellenado. El
  // backend devuelve solo LA que se pidio (y solo si es de su
  // municipio): poblar con las 148 de golpe seria mandar medio
  // municipio a rellenar UNO. Lo comparten el desplegable y las listas
  // clicables: revision y publicadas con faltantes abren la misma
  // ficha.
  const abrirFichaPorId = async (id) => {
    setResultado(null);
    setAvisoFicha(null);
    if (!id) {
      setFichaId(null);
      setFaltanFicha([]);
      setFichaMunicipio('');
      setFotosExistentes(0);
      soltarFotos();
      setCreandoCategoria(false);
      return;
    }
    const peticion = fichaRef.current + 1;
    fichaRef.current = peticion;
    const vigente = () => fichaRef.current === peticion;
    setCargandoFicha(true);
    try {
      const { data } = await api.get('/pendientes/', {
        params: { ficha: id },
        headers: { 'X-Colaborador-Token': token.trim() },
      });
      // Otra persona ya abrio otra ficha mientras esta volaba: lo que
      // llega ahora pertenece a una seleccion que ya no esta en pantalla.
      if (!vigente()) return;
      setDatos({
        nombre: data.nombre || '',
        calle: data.calle || '',
        sector: data.sector || '',
        referencias: data.referencias || '',
        descripcion: data.descripcion || '',
        categoria: data.categoria || '',
        whatsapp: data.whatsapp || '',
        correo: data.correo || '',
        web: data.web || '',
      });
      // La ficha puede traer varios numeritos en su cadena: cada uno
      // vuelve a su propio campo.
      setTelefonos(
        partirTelefono(data.telefono).length > 0
          ? partirTelefono(data.telefono)
          : [''],
      );
      setLat(data.lat === null || data.lat === undefined ? '' : String(data.lat));
      setLng(data.lng === null || data.lng === undefined ? '' : String(data.lng));
      setEstado(data.operativo || '');
      // Los siete dias en pantalla, con los que la ficha ya trae
      // puestos en su sitio.
      setFranjas(diasBase(data.horario || []));
      setFaltanFicha(Array.isArray(data.faltan) ? data.faltan : []);
      // El municipio sale solo: es el del reporte, el que trae el token.
      // No hay desplegable que rellenar.
      setFichaMunicipio(data.municipio || '');
      // WhatsApp, correo y web van escondidos detrás de un botón; si es
      // lo que falta, hay que abrirlos sin que nadie lo busque.
      setMasDatos((data.faltan || []).some((x) => CONTACTO.includes(x)));
      // Las fotos de la ficha (para el techo de 5) y las pendientes:
      // al cambiar de ficha se sueltan las segundas —pertenecian a la
      // anterior— y se cuentan las primeras.
      setFotosExistentes(Number(data.imagenes) || 0);
      soltarFotos();
      setCreandoCategoria(false);
      setFichaId(Number(id));
    } catch (err) {
      // El aviso de la peticion vieja tampoco debe salir: si la ultima
      // eleccion fue correcta, nadie tiene que leer un error de la anterior.
      if (!vigente()) return;
      setFichaId(null);
      setFaltanFicha([]);
      setFichaMunicipio('');
      setFotosExistentes(0);
      setAvisoFicha(err.response?.data?.detail || 'No se pudo abrir esa ficha.');
    } finally {
      // El "cargando" solo lo apaga quien sigue mandando; si no, la ficha
      // vieja lo apagaria mientras la nueva aun vuela.
      if (vigente()) setCargandoFicha(false);
    }
  };

  // El desplegable del reporte: mismo camino, el id llega como cadena.
  const elegirFicha = (e) => abrirFichaPorId(e.target.value);

  // La API pagina (12 por hoja): con solo la primera, el desplegable
  // esconde categorias reales — y quien teclea una que existe en otra
  // hoja no la encuentra, el servidor la reutiliza en silencio y queda
  // con la sensacion de que "no la creo". Se recorren TODAS las hojas
  // hasta que `next` venga vacio.
  const cargarCategorias = async () => {
    const todas = [];
    let pagina = null;
    do {
      const { data } = await api.get(
        '/categories/', pagina ? { params: { page: pagina } } : {},
      );
      const hoja = data.results || data;
      if (Array.isArray(hoja)) todas.push(...hoja);
      pagina = data.next
        ? new URL(data.next, window.location.origin).searchParams.get('page')
        : null;
    } while (pagina);
    setCategorias(todas);
  };

  // El token y las dos listas que rellenan el formulario. Sin token no se
  // puede probar nada, por eso lo primero que se pide.
  useEffect(() => {
    try {
      const guardado = localStorage.getItem(CLAVE_TOKEN);
      if (guardado) {
        setToken(guardado);
        // Token ya usado en este navegador: se valida en silencio y, si
        // vale, la pantalla de trabajo se abre sola. Si no vale, se queda
        // en el acceso con el error debajo del campo.
        entrarConToken(guardado);
      }
    } catch {
      // Sin localStorage (modo privado): se pega el token a mano cada vez.
    }
    api.get('/cabeceras/')
      .then(({ data }) => setCabeceras(Array.isArray(data) ? data : []))
      .catch(() => setCabeceras([]));
    cargarCategorias().catch(() => setCategorias([]));
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

  // Botón «Entrar» del login: valida y, si pasa, abre la pantalla de
  // trabajo. No se peticiona cada letra como antes — se manda una vez.
  const entrar = async (e) => {
    e.preventDefault();
    const t = token.trim();
    if (!t) {
      setErrorAcceso('Pega el token que te dieron.');
      return;
    }
    guardarToken(t);
    await entrarConToken(t);
  };

  // Se vuelve al acceso. No hay sesión que cerrar (el token sigue en
  // este navegador): se sale del trabajo y se deja el formulario limpio.
  const salir = () => {
    limpiarFicha();
    setReporte({ fila: null, detalle: null, aviso: null, cargando: false });
    setCategoria('');
    setHechas([]);
    setResultado(null);
    setErrorAcceso(null);
    setDentro(false);
  };

  // El municipio ya no se elige: es el del reporte — el que trae el
  // token— y, si la ficha abierta trae otro (no deberia), manda el de la
  // ficha. Sin desplegable no hay manera de equivocarse tecleandolo.
  const municipioActual = useMemo(() => {
    const propio = fichaMunicipio
      || reporte.detalle?.municipio
      || reporte.fila?.municipio
      || '';
    if (!propio) return '';
    const c = cabeceras.find((x) => normal(x.municipio) === normal(propio));
    return c ? claveCabecera(c) : '';
  }, [fichaMunicipio, cabeceras, reporte.detalle, reporte.fila]);

  const cabecera = useMemo(
    () => cabeceras.find((c) => claveCabecera(c) === municipioActual) || null,
    [cabeceras, municipioActual],
  );

  const punto = useMemo(() => [aCoordenada(lat), aCoordenada(lng)], [lat, lng]);

  const cambiar = (campo) => (e) => setDatos((d) => ({ ...d, [campo]: e.target.value }));

  const cambiarTelefono = (i, valor) => {
    setTelefonos((ts) => ts.map((t, j) => (j === i ? valor : t)));
  };

  const agregarTelefono = () => {
    setTelefonos((ts) => (ts.length >= MAX_TELEFONOS ? ts : [...ts, '']));
  };

  const quitarTelefono = (i) => {
    setTelefonos((ts) => ts.filter((_, j) => j !== i));
  };

  const agregarFranja = () => {
    setFranjas((f) => [...f, { id: `${Date.now()}-${f.length}`, day: '', desde: '', hasta: '' }]);
  };

  const cambiarFranja = (i, campo) => (e) => {
    const valor = e.target.value;
    setFranjas((f) => f.map((fila, j) => (j === i ? { ...fila, [campo]: valor } : fila)));
  };

  const quitarFranja = (i) => setFranjas((f) => f.filter((_, j) => j !== i));

  // Copiar el horario de OTRO dia al que se esta rellenando: el mismo
  // gesto del formulario del admin. Solo dias que ya tengan las dos
  // horas; el resto no hay nada que copiar.
  const fuentesDeCopia = useMemo(
    () => franjas
      .map((f, i) => ({ f, i }))
      .filter(({ f, i }) => i !== copiarDe && f.desde && f.hasta),
    [franjas, copiarDe],
  );

  const copiarHorario = (origen) => {
    setFranjas((fs) => fs.map((f, i) => (i === copiarDe
      ? { ...f, desde: fs[origen].desde, hasta: fs[origen].hasta }
      : f)));
    setCopiarDe(null);
  };

  const limpiarFicha = () => {
    setDatos(VACIO);
    setTelefonos(['']);
    setFranjas(diasBase());
    setEstado('');
    setMasDatos(false);
    soltarFotos();
    setFotosExistentes(0);
    setCreandoCategoria(false);
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

    // Se anota ANTES de esperar: limpiarFicha() suelta la ficha al
    // terminar, y hace falta saber cual se acaba de completar.
    const idFicha = fichaId;
    const nombreFicha = datos.nombre.trim();

    const cuerpo = {
      ...datos,
      // Los varios numeros del negocio, unidos en la cadena que el
      // servidor guarda tal cual en contact.phone.
      telefono: telefonos.map((t) => t.trim()).filter(Boolean).join('; '),
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

    // Multipart, como el formulario de verdad: un solo POST con los
    // campos y los archivos. El horario viaja como su JSON en texto y
    // las casillas como 'true'/'false' — el servidor los lee asi (y el
    // campo `imagenes` lleva las fotos, una por parte).
    const fd = new FormData();
    Object.entries(cuerpo).forEach(([clave, valor]) => {
      if (valor === null || valor === undefined) return;
      fd.append(
        clave,
        typeof valor === 'object' ? JSON.stringify(valor) : String(valor),
      );
    });
    if (creandoCategoria) fd.append('categoria_nueva', 'true');
    fotos.forEach((f) => fd.append('imagenes', f.file));

    try {
      const { data } = await api.post('/levantamiento/', fd, {
        headers: {
          'X-Colaborador-Token': token.trim(),
          // La instancia manda JSON por defecto: sin avisar, axios
          // convierte el FormData a JSON y las fotos se pierden por el
          // camino. Con esta cabecera pasa el multipart entero y el
          // navegador pone el boundary.
          'Content-Type': 'multipart/form-data',
        },
      });
      // Verde solo cuando el servidor dio la ficha por TERMINADA:
      // publicada y ya sin nada que completar. La publicada con
      // faltantes NO se pinta verde —sigue pendiente, en su lista
      // aparte—, asi la fila verde siempre dice la verdad. Se conserva
      // aqui para que la fila no desaparezca sino que CAMBIE DE COLOR;
      // al volver a entrar, la terminada ya no aparece en ninguna lista.
      const quedoCompleta = data.estado === 'publicado'
        && (data.faltan || []).length === 0;
      setResultado({
        tipo: data.estado,
        motivos: data.motivos || [],
        faltan: data.faltan || [],
        completado: data.completado || [],
        categoriaCreada: data.categoria_creada || null,
        categoriaReusada: data.categoria_reusada || null,
        verde: idFicha !== null && quedoCompleta,
      });
      if (idFicha !== null && quedoCompleta) {
        setHechas((h) => (h.some((x) => x.id === idFicha)
          ? h
          : [...h, {
            id: idFicha,
            nombre: nombreFicha || `Ficha ${idFicha}`,
            municipio: cabecera ? cabecera.municipio : '',
          }]));
      }
      // La categoria quedo resuelta en el servidor: el desplegable se
      // entera recargando TODAS las hojas (estaba solo con la primera)
      // y, ademas, se queda con esa categoria elegida — ahi esta la
      // confirmacion visible de que existia o de que acaba de nacer.
      const categoriaServidor = data.categoria_creada || data.categoria_reusada;
      if (categoriaServidor) {
        await cargarCategorias().catch(() => {});
      }
      // Listo para el siguiente: solo se borra la ficha, no el token ni
      // el municipio, que son lo que se repite en una ronda de campo.
      limpiarFicha();
      if (categoriaServidor) {
        setDatos((d) => ({ ...d, categoria: categoriaServidor }));
      }
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

  const listo = token.trim() !== ''
    && datos.nombre.trim() !== ''
    && cabecera
    && !faltaFoto
    && (!creandoCategoria || datos.categoria.trim() !== '');

  // Resaltado de lo que falta. Solo mientras se completa una ficha ya
  // existente: en un alta nueva TODO está vacío y pintar la mitad del
  // formulario sería puro ruido.
  const falta = (campo) => fichaId !== null && faltanFicha.includes(campo);

  const claseFalta = (...campos) => {
    const hitos = campos.filter((c) => falta(c));
    if (hitos.length === 0) return 'lev-field';
    const obligatorio = hitos.some((c) => OBLIGATORIOS.includes(c));
    return `lev-field lev-field--falta${obligatorio ? ' lev-field--obligatorio' : ''}`;
  };

  const marca = (campo) => (falta(campo)
    ? <span className="lev-falta-marca">falta</span>
    : null);

  // Lo que todavia le falta a la ficha abierta, medido con el formulario
  // de AHORA: la fila cambia de color mientras se teclea, sin esperar a
  // que el servidor conteste.
  const restanFicha = useMemo(() => {
    if (fichaId === null) return faltanFicha;
    const lleno = {
      nombre: datos.nombre.trim() !== '',
      direccion: datos.calle.trim() !== '',
      telefono: telefonos.some((t) => t.trim() !== ''),
      // Las fotos de la ficha mas las nuevas: el «imagen» del servidor
      // se mide igual, con las que la ficha YA tiene.
      imagen: !faltaFoto,
      punto: punto[0] !== null && punto[1] !== null,
      categoria: datos.categoria !== '',
      horario: franjas.some((f) => f.day && f.desde && f.hasta),
      whatsapp: datos.whatsapp.trim() !== '',
      correo: datos.correo.trim() !== '',
      web: datos.web.trim() !== '',
      descripcion: datos.descripcion.trim() !== '',
      estado: estado !== '',
    };
    return CAMPOS.filter((c) => !lleno[c]);
  }, [fichaId, faltanFicha, datos, telefonos, punto, franjas, estado, faltaFoto]);

  // El conteo por campo con la ficha abierta descontada en vivo: cuando
  // ya no le falta telefono a NINGUNA, el chip se tacha y pasa a verde.
  const porCampoVivo = useMemo(() => {
    if (!reporte.detalle) return [];
    const hechos = new Set(
      fichaId !== null ? faltanFicha.filter((c) => !restanFicha.includes(c)) : [],
    );
    return reporte.detalle.por_campo.map((f) => ({
      ...f,
      cantidad: Math.max(0, f.cantidad - (hechos.has(f.campo) ? 1 : 0)),
    }));
  }, [reporte.detalle, fichaId, faltanFicha, restanFicha]);

  // Lo que se ve en REVISION: las que quedaron verdes en esta sesion (el
  // backend deja de mandarlas) unidas a las que faltan, ordenadas por
  // nombre para que NADA se mueva de sitio al completarse — el color es
  // la confirmacion, y una confirmacion que salta de lugar no se lee.
  const filas = useMemo(() => {
    const muni = reporte.detalle?.municipio || reporte.fila?.municipio || '';
    const listas = hechas.filter((h) => normal(h.municipio) === normal(muni));
    const quedan = (reporte.detalle?.fichas || [])
      .filter((f) => !listas.some((h) => h.id === f.id))
      .map((f) => ({
        id: f.id,
        nombre: f.nombre,
        estado: f.estado,
        activa: f.id === fichaId,
        restan: f.id === fichaId ? restanFicha : f.faltan,
        hecha: false,
      }));
    const yaHechas = listas.map((h) => ({
      id: h.id, nombre: h.nombre, activa: false, restan: [], hecha: true,
    }));
    return [...quedan, ...yaHechas]
      .sort((a, b) => (a.nombre || '').localeCompare(b.nombre || '', 'es'));
  }, [reporte.detalle, reporte.fila, hechas, fichaId, restanFicha]);

  // La lista aparte: publicadas con todos los obligatorios y aun con
  // algo de lo demas sin rellenar. Las que quedaron verdes en esta
  // sesion NO se repiten aqui —su verde vive en la lista de revision—
  // para que una misma ficha nunca salga dos veces.
  const filasPublicadas = useMemo(() => {
    const muni = reporte.detalle?.municipio || reporte.fila?.municipio || '';
    const listas = hechas.filter((h) => normal(h.municipio) === normal(muni));
    return (reporte.detalle?.publicadas || [])
      .filter((f) => !listas.some((h) => h.id === f.id))
      .map((f) => ({
        id: f.id,
        nombre: f.nombre,
        activa: f.id === fichaId,
        restan: f.id === fichaId ? restanFicha : f.faltan,
        hecha: false,
      }))
      .sort((a, b) => (a.nombre || '').localeCompare(b.nombre || '', 'es'));
  }, [reporte.detalle, reporte.fila, hechas, fichaId, restanFicha]);

  // El avance se mide sobre las DOS listas: lo que ya quedo sin nada
  // pendiente (verdes de revision + publicadas que se completaron en
  // vivo) sobre todo lo que habia que tocar.
  const listasAhora = filas.filter((f) => f.restan.length === 0).length
    + filasPublicadas.filter((f) => f.restan.length === 0).length;
  const avanceTotal = filas.length + filasPublicadas.length;
  const avance = avanceTotal > 0
    ? Math.round((listasAhora / avanceTotal) * 100)
    : 0;

  // El resumen: sin filtro, el renglon del municipio; con filtro, lo
  // que hay en la categoria elegida — el renglon no sabe de filtros.
  const nombreCategoria = reporte.detalle
    ? (reporte.detalle.categorias || [])
      .find((c) => c.slug === categoria)?.nombre
    : null;
  const resumenCategoria = reporte.detalle
    ? `${reporte.detalle.total} ficha${reporte.detalle.total !== 1 ? 's' : ''}`
      + `, ${reporte.detalle.con_revision} en revisión`
      + `, ${reporte.detalle.con_publicadas} publicada${reporte.detalle.con_publicadas !== 1 ? 's' : ''}`
        + ' con faltantes'
      + `, ${reporte.detalle.en_revision} esperando publicarse.`
    : '';

  const claseFila = (f) => {
    let base = 'lev-ficha--curso';
    if (f.restan.length === 0) base = 'lev-ficha--hecha';
    else if (f.restan.some((c) => OBLIGATORIOS.includes(c))) base = 'lev-ficha--bloquea';
    return f.activa ? `${base} lev-ficha--activa` : base;
  };

  // -------------------------- pantalla de acceso ----------------------
  // Solo el token. Nada de formulario ni de reporte aqui: eso es la
  // pantalla de trabajo, que se abre cuando el servidor acepta el token.
  if (!dentro) {
    return (
      // <main> con id para el "Saltar al contenido" (auditoria D).
      <main className="lev-page lev-acceso" id="contenido" tabIndex={-1}>
        <header className="lev-top">
          <div>
            <p className="lev-top-eyebrow">Herramienta interna</p>
            <h1 className="lev-top-title">Levantamiento</h1>
          </div>
          <a className="lev-top-volver" href="/">Volver al buscador</a>
        </header>

        <section className="lev-card lev-acceso-card">
          <h2 className="lev-acceso-titulo">Acceso del colaborador</h2>
          <p className="lev-acceso-texto">
            Pega el token que te dieron. El sistema lo valida, carga el reporte de{' '}
            <strong>tu municipio</strong> y te abre la pantalla de trabajo.
          </p>

          <form className="lev-acceso-form" onSubmit={entrar}>
            <div className="lev-field">
              <label htmlFor="lev-token">Token de colaborador</label>
              <div className="lev-token-row">
                <input
                  id="lev-token"
                  type={tokenVisible ? 'text' : 'password'}
                  value={token}
                  onChange={(e) => {
                    guardarToken(e.target.value);
                    if (errorAcceso) setErrorAcceso(null);
                  }}
                  placeholder="Pega aquí el token que te dieron"
                  autoComplete="off"
                  spellCheck={false}
                  autoFocus
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

            {errorAcceso && <p className="lev-acceso-error">{errorAcceso}</p>}

            <button type="submit" className="lev-enviar" disabled={validando}>
              {validando ? 'Validando…' : 'Entrar'}
            </button>
          </form>
        </section>
      </main>
    );
  }

  // ------------------------- pantalla de trabajo ----------------------
  return (
    // <main> con id para el "Saltar al contenido" (auditoria D).
    <main className="lev-page lev-page--lado" id="contenido" tabIndex={-1}>
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
        <strong>nombre, dirección, teléfono, imagen y punto</strong>. Si falta alguno no se
        descarta: queda en la lista de revisión para que lo completen. Lo demás (horario,
        WhatsApp, web…) se puede rellenar más adelante: esas fichas van en la lista aparte de
        publicadas con faltantes. Puedes <strong>filtrar por categoría</strong> para trabajar
        solo con unas fichas y <strong>posponer</strong> las que no vayas a completar.
      </p>

      <form
        className="lev-form lev-form--lado"
        onSubmit={enviar}
      >
        <section className="lev-card lev-firma">
          <h2 className="lev-card-title">Tu firma</h2>
          {/* Quien esta firmando: el nombre que le dio el admin al token
              (lo trae el propio renglon del reporte) y el municipio que
              le toca. */}
          <p className="lev-firma-quien">
            <strong>{reporte.fila?.colaborador || 'Colaborador'}</strong>
            <span className="lev-firma-municipio">
              {reporte.fila?.municipio || fichaMunicipio || 'Municipio del token'}
              {reporte.fila?.provincia ? ` (${reporte.fila.provincia})` : ''}
            </span>
            <span className="lev-firma-token">
              {token.trim() ? `token ••••${token.trim().slice(-4)}` : 'sin token'}
            </span>
          </p>
          <button type="button" className="lev-btn-ghost" onClick={salir}>
            Salir
          </button>
        </section>

        {/* §11.1 + lo decidido: el reporte POR MUNICIPIO con sus dos
            listas —en revisión y publicadas con faltantes—, que es lo
            que le dice al colaborador que hacer. El backend solo
            devuelve su renglon; los demas municipios no existen aqui.
            Con token se coloca AL LADO del formulario (grid-template-areas
            en el CSS); en el telefono sigue debajo, en el orden de siempre. */}
        <section className="lev-card lev-reporte">
          <h2 className="lev-card-title">Lo que falta en tu municipio</h2>

          {reporte.aviso && <p className="lev-aviso">{reporte.aviso}</p>}

          {/* Token valido pero sin nada que contar: que se note que el
              reporte se leyo, no que se rompio. */}
          {!reporte.aviso && !reporte.cargando && !reporte.fila && (
            <p className="lev-aviso">Todavía no hay fichas en tu municipio.</p>
          )}

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
                  : categoria && reporte.detalle
                    ? `categoría ${nombreCategoria || categoria} — ${resumenCategoria}`
                    : `${reporte.fila.total} ficha${reporte.fila.total !== 1 ? 's' : ''}`
                      + `, ${reporte.fila.con_revision} en revisión`
                      + `, ${reporte.fila.con_publicadas} publicada${reporte.fila.con_publicadas !== 1 ? 's' : ''}`
                        + ' con faltantes'
                      + `, ${reporte.fila.en_revision} esperando publicarse.`}
              </p>

              {/* El filtro de categoria: solo cambia el detalle —
                  listas, chips y desglose—; el renglon de arriba sigue
                  siendo el del municipio entero, y con filtro el
                  resumen cuenta lo de la categoria. */}
              {reporte.detalle && (reporte.detalle.categorias || []).length > 0 && (
                <div className="lev-field lev-filtro">
                  <label htmlFor="lev-categoria">Categoría</label>
                  <select
                    id="lev-categoria"
                    value={categoria}
                    onChange={(e) => cambiarCategoria(e.target.value)}
                  >
                    <option value="">Todas las categorías</option>
                    {(reporte.detalle.categorias || []).map((c) => (
                      <option key={c.slug} value={c.slug}>
                        {c.nombre} ({c.con_revision + c.con_publicadas})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Sin nada pendiente el reporte NO desaparece: se
                  explica. Con categoria, el vacio es de la categoria;
                  sin ella, el del municipio — contando los pospuestos,
                  que no son «todo completo» sino «nada de lo mio». */}
              {!categoria && reporte.fila.total > 0
                && reporte.fila.con_revision === 0
                && reporte.fila.con_publicadas === 0 && (
                <p className="lev-vacio">
                  {reporte.fila.con_pospuestos > 0
                    ? `✓ No queda nada en tu lista de trabajo: ${reporte.fila.con_pospuestos} pospuesta${reporte.fila.con_pospuestos !== 1 ? 's' : ''} siguen aparte.`
                    : '✓ Todo completo en tu municipio: no hay ninguna ficha esperando publicarse ni publicadas con faltantes.'}
                </p>
              )}

              {categoria && reporte.detalle
                && reporte.detalle.fichas.length === 0
                && (reporte.detalle.publicadas || []).length === 0 && (
                <p className="lev-vacio">
                  ✓ No queda nada pendiente en esta categoría
                  {(reporte.detalle.pospuestos || []).length > 0
                    ? `: las ${reporte.detalle.pospuestos.length} que quedan están pospuestas.`
                    : '.'}
                </p>
              )}

              {/* El selector: la puerta al modo completar. Elegir una
                  ficha puebla el formulario con lo que ya hay y le marca
                  lo que falta; el envío va con su id. Entra con las de
                  AMBAS listas: si no, abrir una publicada dejaria en el
                  desplegable un valor que no esta en sus opciones. */}
              {reporte.detalle && (
                reporte.detalle.fichas.length > 0
                || (reporte.detalle.publicadas || []).length > 0
              ) && (
                <div className="lev-field lev-elegir">
                  <label htmlFor="lev-elegir">Negocio a completar</label>
                  <select id="lev-elegir" value={fichaId ?? ''} onChange={elegirFicha}>
                    <option value="">— Elige uno de la lista —</option>
                    {[...reporte.detalle.fichas, ...(reporte.detalle.publicadas || [])].map((f) => (
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

              {(reporte.fila.con_revision > 0 || reporte.fila.con_publicadas > 0
                || reporte.fila.con_pospuestos > 0) && (
                <button
                  type="button"
                  className="lev-btn-ghost"
                  onClick={verReporte}
                  // Sin esta senal, el clic se pierde: la lista vieja se
                  // conserva mientras llega la nueva (para que no
                  // parpadee) y si no cambia nada parece que el boton
                  // no hizo nada.
                  disabled={reporte.cargando}
                >
                  {reporte.cargando
                    ? 'Actualizando…'
                    : reporte.detalle
                      ? 'Actualizar'
                      : `Ver las ${reporte.fila.con_revision + reporte.fila.con_publicadas} con algo faltando`}
                </button>
              )}

              {(reporte.detalle || filas.length > 0) && (
                <div className="lev-detalle">
                  {reporte.detalle && (
                    <>
                      <h3>Por campo faltante</h3>
                      {/* El conteo baja SOLO cuando la ficha abierta
                          completa ese campo: el chip se tacha y pasa a
                          verde antes de enviar. */}
                      <ul className="lev-por-campo">
                        {porCampoVivo.map((f) => (
                          <li
                            key={f.campo}
                            className={[
                              f.en_obligatorio ? 'es-obligatorio' : '',
                              f.cantidad === 0 ? 'es-hecho' : '',
                            ].filter(Boolean).join(' ')}
                          >
                            {f.etiqueta}
                            <span className="lev-por-campo-n">{f.cantidad}</span>
                            {f.en_obligatorio && f.cantidad > 0 && (
                              <span className="lev-obligatorio-marca">bloquea</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  <h3>En revisión</h3>

                  {/* La confirmacion visual: barra + fila que cambia de
                      color sin moverse de sitio. El avance cuenta las
                      DOS listas: lo resuelto de todo lo que habia. */}
                  <p className="lev-avance">
                    <span className="lev-avance-barra">
                      <i style={{ width: `${avance}%` }} />
                    </span>
                    <span className={avance === 100 ? 'lev-avance-texto es-listo' : 'lev-avance-texto'}>
                      {listasAhora} de {avanceTotal} sin nada pendiente
                    </span>
                  </p>

                  <ul className="lev-fichas">
                    {filas.map((f) => (
                      <li key={f.id} className={`lev-ficha ${claseFila(f)}`}>
                        <span className="lev-ficha-nombre">{f.nombre}</span>
                        <span className={`lev-ficha-estado ${f.hecha ? 'hecha' : f.estado}`}>
                          {f.hecha ? 'completada' : f.estado === 'publicado' ? 'publicada' : 'sin publicar'}
                        </span>
                        <span className="lev-ficha-falta">
                          {f.restan.length === 0
                            ? (f.hecha ? '✓ Sin nada pendiente' : '✓ Lista para enviar')
                            : `Falta: ${f.restan.map((c) => ETIQUETAS[c] || c).join(', ')}`}
                        </span>
                        {/* Solo lo que aun se puede apartar: la que esta
                            abierta se esta trabajando y la verde ya se
                            hizo. */}
                        {!f.activa && !f.hecha && (
                          <button
                            type="button"
                            className="lev-ficha-posponer"
                            title="No completar ahora: a la lista de pospuestos"
                            onClick={() => posponer(f.id, true)}
                          >
                            Posponer
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>

                  {/* La segunda lista, en la MISMA tarjeta: publicadas
                      que ya tienen todo lo obligatorio y aun les falta
                      algo de lo demas. Son clicables —abren el mismo
                      formulario— porque rellenarlas tarde tambien es el
                      trabajo. */}
                  {filasPublicadas.length > 0 && (
                    <>
                      <h3>Publicadas con faltantes</h3>
                      <p className="lev-publicadas-nota">
                        Ya tienen todo lo obligatorio; les queda rellenar lo demás cuando se pueda.
                      </p>
                      <ul className="lev-fichas lev-fichas--publicadas">
                        {filasPublicadas.map((f) => (
                          <li key={f.id} className={`lev-ficha ${claseFila(f)}`}>
                            <button
                              type="button"
                              className="lev-ficha-abrir"
                              onClick={() => abrirFichaPorId(String(f.id))}
                            >
                              <span className="lev-ficha-nombre">{f.nombre}</span>
                            </button>
                            <span className="lev-ficha-estado publicado">publicada</span>
                            <span className="lev-ficha-falta">
                              {f.restan.length === 0
                                ? '✓ Completa'
                                : `Falta: ${f.restan.map((c) => ETIQUETAS[c] || c).join(', ')}`}
                            </span>
                            {!f.activa && !f.hecha && (
                              <button
                                type="button"
                                className="lev-ficha-posponer"
                                title="No completar ahora: a la lista de pospuestos"
                                onClick={() => posponer(f.id, true)}
                              >
                                Posponer
                              </button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  {/* La tercera lista: lo que el editor decidio no
                      completar. Sale de las dos de arriba y de todos
                      los contadores; «Retomar» la devuelve. */}
                  {(reporte.detalle?.pospuestos || []).length > 0 && (
                    <>
                      <h3>Pospuestos</h3>
                      <p className="lev-pospuestos-nota">
                        Los que decidiste no completar ahora: no cuentan como pendientes.
                      </p>
                      <ul className="lev-fichas lev-fichas--pospuestos">
                        {(reporte.detalle.pospuestos || []).map((f) => (
                          <li key={f.id} className="lev-ficha lev-ficha--pospuesto">
                            <span className="lev-ficha-nombre">{f.nombre}</span>
                            <span className="lev-ficha-estado pospuesto">pospuesta</span>
                            <span className="lev-ficha-falta">
                              {f.faltan.length === 0
                                ? '✓ Lista para enviar'
                                : `Falta: ${f.faltan.map((c) => ETIQUETAS[c] || c).join(', ')}`}
                            </span>
                            <button
                              type="button"
                              className="lev-ficha-posponer lev-ficha-retomar"
                              title="Volver a la lista de trabajo"
                              onClick={() => posponer(f.id, false)}
                            >
                              Retomar
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
            </>
          )}

          {reporte.cargando && <p className="lev-aviso">Cargando…</p>}
        </section>

        <section className="lev-card lev-donde">
          <h2 className="lev-card-title">Dónde está</h2>

          <div className="lev-geo">
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

          {/* No es pendiente ni decide nada: sirve para llegar a pie una
              vez esten las coordenadas. */}
          <div className="lev-field">
            <label htmlFor="lev-referencias">Referencias</label>
            <input
              id="lev-referencias"
              type="text"
              value={datos.referencias}
              onChange={cambiar('referencias')}
              placeholder="Frente a la parada de bus, al lado de la farmacia"
            />
          </div>
        </section>

        <section className="lev-card lev-negocio">
          <h2 className="lev-card-title">El negocio</h2>
          <div className={claseFalta('nombre')}>
            <label htmlFor="lev-nombre">Nombre * {marca('nombre')}</label>
            <input id="lev-nombre" type="text" value={datos.nombre} onChange={cambiar('nombre')} placeholder="Panadería El Trigal" />
          </div>

          <div className="lev-row">
            <div className={claseFalta('telefono')}>
              <label htmlFor="lev-telefono">Teléfono {marca('telefono')}</label>
              {telefonos.map((valor, i) => (
                <div className="lev-telefono-fila" key={i}>
                  <input
                    id={i === 0 ? 'lev-telefono' : `lev-telefono-${i}`}
                    type="tel"
                    value={valor}
                    onChange={(e) => cambiarTelefono(i, e.target.value)}
                    placeholder={i === 0 ? '809-555-1111' : 'Otro número'}
                  />
                  {telefonos.length > 1 && (
                    <button
                      type="button"
                      className="lev-btn-ghost lev-btn-quitar"
                      onClick={() => quitarTelefono(i)}
                      aria-label="Quitar este teléfono"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                className="lev-btn-ghost"
                onClick={agregarTelefono}
                disabled={telefonos.length >= MAX_TELEFONOS}
              >
                {telefonos.length >= MAX_TELEFONOS
                  ? `Máximo ${MAX_TELEFONOS} teléfonos`
                  : '+ Añadir teléfono'}
              </button>
              <small>
                Sin teléfono no se publica solo: queda en el reporte.
                {telefonos.length === 1 && ' Si tiene más de uno, añade otro campo.'}
              </small>
            </div>
            <div className={claseFalta('categoria')}>
              <label htmlFor="lev-categoria">Categoría {marca('categoria')}</label>
              <select
                id="lev-categoria"
                value={creandoCategoria ? CATEGORIA_NUEVA : datos.categoria}
                onChange={(e) => {
                  if (e.target.value === CATEGORIA_NUEVA) {
                    setCreandoCategoria(true);
                    setDatos((d) => ({ ...d, categoria: '' }));
                  } else {
                    setCreandoCategoria(false);
                    setDatos((d) => ({ ...d, categoria: e.target.value }));
                  }
                }}
              >
                <option value="">La que ya exista</option>
                {categorias.map((cat) => (
                  <option key={cat.id} value={cat.name}>{cat.name}</option>
                ))}
                <option value={CATEGORIA_NUEVA}>➕ Crear categoría nueva…</option>
              </select>
              {creandoCategoria && (
                <>
                  <input
                    id="lev-categoria-nueva"
                    type="text"
                    value={datos.categoria}
                    onChange={cambiar('categoria')}
                    placeholder="Nombre de la categoría nueva"
                    maxLength={100}
                    autoFocus
                  />
                  <small>
                    Se valida al momento: si ya existe —aunque esté escrita
                    distinto— se usa esa y no se crea otra.
                  </small>
                </>
              )}
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
                + Añadir otra franja
              </button>
            </div>
            {franjas.map((f, i) => (
              <div className="lev-horario-fila" key={f.id}>
                <select aria-label="Día" value={f.day} onChange={cambiarFranja(i, 'day')}>
                  <option value="">Día</option>
                  {DIAS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <input aria-label="Desde" type="time" step={60} value={f.desde} onChange={cambiarFranja(i, 'desde')} />
                <span className="lev-horario-sep">—</span>
                <input aria-label="Hasta" type="time" step={60} value={f.hasta} onChange={cambiarFranja(i, 'hasta')} />
                <button
                  type="button"
                  className="lev-horario-copiar"
                  title="Copiar horario de otro día"
                  aria-label="Copiar horario de otro día"
                  onClick={() => setCopiarDe(i)}
                >
                  📋
                </button>
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

          {/* El mismo gesto que en el admin: elegir de que dia se copia
              las horas, en vez de teclearlas otra vez. */}
          {copiarDe !== null && (
            <div className="lev-copiar-overlay" onClick={() => setCopiarDe(null)}>
              <div
                className="lev-copiar-popup"
                role="dialog"
                aria-label="Copiar horario de"
                onClick={(e) => e.stopPropagation()}
              >
                <h3>Copiar horario de:</h3>
                {fuentesDeCopia.length === 0 ? (
                  <p className="lev-copiar-vacio">
                    No hay otros días con horarios definidos para copiar.
                  </p>
                ) : (
                  fuentesDeCopia.map(({ f, i }) => (
                    <button key={f.id} type="button" onClick={() => copiarHorario(i)}>
                      {f.day} ({f.desde} — {f.hasta})
                    </button>
                  ))
                )}
                <button
                  type="button"
                  className="lev-copiar-cancelar"
                  onClick={() => setCopiarDe(null)}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

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

        <section className="lev-card lev-fotos">
          <h2 className="lev-card-title">Fotos</h2>

          <p className="lev-fotos-nota">
            {fotosExistentes > 0 && (
              <>
                Esta ficha ya tiene <strong>{fotosExistentes}</strong>{' '}
                foto{fotosExistentes !== 1 ? 's' : ''}.{' '}
              </>
            )}
            {faltaFoto
              ? 'Obligatoria: hay que mandar al menos una foto para poder enviar.'
              : fotosLlenas
                ? 'Llegaste al máximo de 5: no se aceptan más.'
                : `Se pueden añadir ${MAX_FOTOS - fotosTotal} más (5 por ficha).`}
          </p>

          {fotos.length > 0 && (
            <ul className="lev-fotos-grid">
              {fotos.map((f) => (
                <li key={f.id} className="lev-fotos-item">
                  <img src={f.url} alt={f.file.name} />
                  <button
                    type="button"
                    onClick={() => quitarFoto(f.id)}
                    aria-label={`Quitar ${f.file.name}`}
                    title="Quitar"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          <label className={`lev-fotos-subir${fotosLlenas ? ' lev-fotos-subir--lleno' : ''}`}>
            <input
              type="file"
              accept="image/*"
              multiple
              disabled={fotosLlenas}
              onChange={agregarFotos}
            />
            {fotosLlenas ? `Máximo ${MAX_FOTOS} fotos` : '+ Añadir fotos'} ({fotosTotal}/{MAX_FOTOS})
          </label>
        </section>

        <button type="submit" className="lev-enviar" disabled={!listo || enviando}>
          {enviando ? 'Enviando…' : 'Enviar'}
        </button>
        {!listo && (
          <p className="lev-falta">
            {!token.trim() && 'Falta tu token. '}
            {!datos.nombre.trim() && 'Falta el nombre. '}
            {!cabecera && 'No se reconoce el municipio del reporte. '}
            {faltaFoto && 'Falta al menos una foto. '}
            {creandoCategoria && !datos.categoria.trim() && 'Falta el nombre de la categoría nueva.'}
          </p>
        )}
      </form>

      {resultado && <Resultado r={resultado} />}
    </main>
  );
}

const ETIQUETAS = {
  nombre: 'nombre',
  direccion: 'dirección',
  telefono: 'teléfono',
  imagen: 'imagen',
  punto: 'punto (coordenadas)',
  categoria: 'categoría',
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
  referencias: 'referencias',
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
    pendiente: ['✓ Aceptado: se queda en revisión', 'lev-ok'],
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

  // El cierre de la nota tiene que ser cierto caso por caso: la
  // PUBLICADA con faltantes sale de revision y pasa a la lista aparte;
  // la que quedo COMPLETA ya no sale en ninguna; la que sigue en
  // revision sigue ahi (lo dice su propio renglon de arriba), y el
  // verde solo se promete si el servidor acabo dejandola terminada.
  const cierre = r.tipo === 'publicado'
    ? faltan.length > 0
      ? ': sale de la lista de revisión y pasa a la de publicadas con faltantes'
      + (r.verde ? ', y la que dejaste queda en verde' : '') + '.'
      : ': la ficha publicada ya no sale en ninguna lista'
      + (r.verde ? ', y la que dejaste queda en verde' : '') + '.'
    : '.';

  return (
    <div className={`lev-resultado ${titulo[1]}`}>
      <h2>{titulo[0]}</h2>

      {/* La confirmacion de la categoria: es lo unico que distingue
          "se creo" de "ya existia" — sin esto, quien pide una nueva
          no tiene forma de saber que hizo el servidor. */}
      {r.categoriaCreada && (
        <p>
          Se creó la categoría <strong>{r.categoriaCreada}</strong> y ya
          aparece en el desplegable.
        </p>
      )}
      {r.categoriaReusada && (
        <p>
          La categoría <strong>{r.categoriaReusada}</strong> ya existía: se
          usó esa y no se creó otra.
        </p>
      )}

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
          Sigue en la lista de revisión de su municipio. Le falta:{' '}
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
          envío{cierre} Elige la siguiente cuando quieras.
        </p>
      )}
    </div>
  );
}
