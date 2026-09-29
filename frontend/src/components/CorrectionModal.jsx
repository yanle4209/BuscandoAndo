import { useState } from 'react';
import api from '../api/axios';
import './CorrectionModal.css';

/**
 * Opciones del desplegable.
 *
 * DEBE coincidir con Correction.CAMPOS de backend/businesses/models.py:
 * si anade un dato nuevo a la tarjeta, anadelo aqui Y alla, o el backend
 * rechazara el envio con un 400.
 */
const CAMPOS = [
  ['nombre', 'Nombre del negocio'],
  ['direccion', 'Direccion'],
  ['telefono', 'Telefono / WhatsApp'],
  ['categoria', 'Categoria'],
  ['descripcion', 'Descripcion'],
  ['estado', 'Estado (abierto/cerrado)'],
  ['horario', 'Horario'],
  ['otro', 'Otro'],
];

/** Igual que el backend: validate_mensaje exige 10 caracteres. */
const MIN_CARACTERES = 10;

/**
 * Formulario que abre el boton "Corregir" de BusinessCard.
 *
 * Reutiliza .modal-overlay + .modal-panel de BusinessModal.css, la misma
 * pareja que el resto de modales. Usar una clase inventada
 * (p. ej. .modal-content) deja el panel sin fondo: eso ya nos paso una vez.
 */
export default function CorrectionModal({ business, onClose }) {
  const [campo, setCampo] = useState(CAMPOS[0][0]);
  const [mensaje, setMensaje] = useState('');
  const [fase, setFase] = useState('escribiendo'); // escribiendo | enviando | error | listo
  const [error, setError] = useState('');

  const restantes = MIN_CARACTERES - mensaje.trim().length;

  async function enviar(e) {
    e.preventDefault();
    setFase('enviando');
    setError('');

    try {
      await api.post('/corrections/', {
        business: business.id,
        campo,
        mensaje: mensaje.trim(),
      });
      setFase('listo');
    } catch (err) {
      // DRF responde {campo: [...]} o {mensaje: [...]}.
      const datos = err.response?.data;
      setError(
        datos?.mensaje?.[0] ||
        datos?.campo?.[0] ||
        datos?.business?.[0] ||
        'No se pudo enviar el aviso. Intentalo de nuevo.'
      );
      setFase('error');
    }
  }

  const enviando = fase === 'enviando';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel correction"
        role="dialog"
        aria-modal="true"
        aria-labelledby="correction-title"
        onClick={e => e.stopPropagation()}
      >
        <button className="modal-close" onClick={onClose} aria-label="Cerrar">&#10005;</button>

        {fase === 'listo' ? (
          <div className="correction__ok">
            <h2 className="correction__title" id="correction-title">Gracias por avisar</h2>
            <p className="correction__desc">
              Recibimos tu correccion sobre <strong>{business.name}</strong>. El
              admin la revisara y aplicara el dato correcto.
            </p>
            <button type="button" className="correction__submit" onClick={onClose}>
              Entendido
            </button>
          </div>
        ) : (
          <form onSubmit={enviar} noValidate={false}>
            <h2 className="correction__title" id="correction-title">Corregir información</h2>
            <p className="correction__desc">
              ¿Qué dato de <strong>{business.name}</strong> está mal? Dinos
              cuál es el correcto y lo revisamos.
            </p>

            <label className="correction__label" htmlFor="correction-campo">
              Dato incorrecto
            </label>
            <select
              id="correction-campo"
              className="correction__select"
              value={campo}
              onChange={e => setCampo(e.target.value)}
              disabled={enviando}
            >
              {CAMPOS.map(([valor, texto]) => (
                <option key={valor} value={valor}>{texto}</option>
              ))}
            </select>

            <label className="correction__label" htmlFor="correction-mensaje">
              Qué está mal y cuál es el dato correcto
            </label>
            <textarea
              id="correction-mensaje"
              className="correction__textarea"
              rows={4}
              value={mensaje}
              onChange={e => setMensaje(e.target.value)}
              disabled={enviando}
              placeholder="Ej.: el telefono es 809-555-0000, no el que aparece en la tarjeta."
              required
            />
            {restantes > 0 && (
              <p className="correction__hint" aria-live="polite">
                Mínimo {MIN_CARACTERES} caracteres (te faltan {restantes}).
              </p>
            )}

            {fase === 'error' && (
              <p className="correction__error" role="alert">{error}</p>
            )}

            <div className="correction__actions">
              <button
                type="button"
                className="correction__cancel"
                onClick={onClose}
                disabled={enviando}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="correction__submit"
                disabled={enviando || restantes > 0}
              >
                {enviando ? 'Enviando…' : 'Enviar corrección'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
