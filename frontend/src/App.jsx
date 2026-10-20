import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './App.css';

// Code-splitting (DISENO.md 14.6): cada ruta baja su propio chunk y el
// bundle de entrada se queda con react + router + el armazon. Leaflet
// viaja en el chunk del mapa (solo lo monta MapView), no al inicio.
const Home = lazy(() => import('./pages/Home'));
const BusinessDetail = lazy(() => import('./pages/BusinessDetail'));
const Levantamiento = lazy(() => import('./pages/Levantamiento'));

function App() {
  return (
    <Router>
      {/* Accesibilidad (auditoria D): el primer Tab de teclado salta
          el mapa y la barra de busqueda y va derecho a los
          resultados (#contenido es la <main> de cada pagina). */}
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      {/* Mientras la ruta baja su chunk, el fallback mantiene el
          landmark #contenido (el skip-link no apunta a la nada) y el
          role="status" del párrafo avisa al lector de pantalla. */}
      <Suspense
        fallback={
          <main id="contenido" className="ruta-cargando">
            <p role="status">Cargando…</p>
          </main>
        }
      >
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/business/:slug" element={<BusinessDetail />} />
          {/* Herramienta de campo (DISENO.md 11.5): no hay enlace a ella
              desde ninguna parte del sitio publico; se llega escribiendo la
              ruta y el servidor exige el token de colaborador. */}
          <Route path="/levantamiento" element={<Levantamiento />} />
        </Routes>
      </Suspense>
    </Router>
  );
}

export default App;
