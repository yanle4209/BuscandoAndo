import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
    // Las metricas de uso distinguen web de app por esta cabecera
    // (el backend la prefiere a mirar el User-Agent).
    'X-Plataforma': 'web',
  },
});

export default api;
