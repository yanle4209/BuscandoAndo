import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  // Sin techo, una peticion colgada (wifi que no contesta, backend que no
  // responde) dejaba el esqueleto de carga visible PARA SIEMPRE: no hay
  // timeout natural que lo saque de ahi. Con el techo, la peticion cae en
  // el catch de cada caller, que ya sabe distinguir "sin red" de
  // "sin resultados" y ofrecer reintento.
  // No rompe nada lento: todo el frontend manda JSON (sin subidas
  // multipart, verificado), y las consultas de listado tardan milisegundos.
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    // Las metricas de uso distinguen web de app por esta cabecera
    // (el backend la prefiere a mirar el User-Agent).
    'X-Plataforma': 'web',
  },
});

export default api;
