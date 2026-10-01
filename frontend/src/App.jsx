import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import BusinessDetail from './pages/BusinessDetail';
import Levantamiento from './pages/Levantamiento';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/business/:slug" element={<BusinessDetail />} />
        {/* Herramienta de campo (DISENO.md 11.5): no hay enlace a ella
            desde ninguna parte del sitio publico; se llega escribiendo la
            ruta y el servidor exige el token de colaborador. */}
        <Route path="/levantamiento" element={<Levantamiento />} />
      </Routes>
    </Router>
  );
}

export default App;
