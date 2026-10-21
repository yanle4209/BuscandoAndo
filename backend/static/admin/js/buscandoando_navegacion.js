/**
 * BuscandoAndo Admin — Reenganche del JS de stock y salvaguardas de Turbo
 *
 * El panel navega sin recarga (Turbo, DISENO 15): al cambiar el
 * contenido, el JS del propio Django que se engancha UNA vez en
 * DOMContentLoaded queda desenganchado. Aqui se vuelve a llamar lo que
 * el panel usa:
 *
 *   - actions.js: acciones masivas y contadores de los listados
 *     (window.Actions).
 *   - inlines.js: botones "añadir/eliminar" de los inline (jQuery).
 *
 * Turbo evalua los scripts de la pagina ANTES de emitir turbo:load, asi
 * que la primera visita a cada pagina se cubre solo (el ready del propio
 * script); aqui solo falta reengancharse en las REPETIDAS. Las marcas
 * evitan duplicar botones ni enganches si ambos caminos coinciden.
 *
 * Ademas: Turbo navega sin recargar, asi que el aviso del navegador por
 * cambios sin guardar ya no salta. Aqui se restaura esa red de seguridad.
 */
(function () {
  'use strict';

  // Turbo guarda copias de cada pagina para el boton Atras. En un panel
  // interesa mas correccion que prisa (formularios a medio editar, etc.):
  // siempre pagina fresca del servidor.
  if (window.Turbo) {
    Turbo.cache.enable = false;
  }

  // Este fichero vive en la cabecera base: su primer turbo:load es
  // siempre la carga inicial, que ya cubrio el ready de cada script.
  var primeraCarga = true;

  function reengancharAcciones() {
    var formulario = document.querySelector('#changelist-form');
    if (!formulario || formulario.dataset.baAcciones === '1') return;
    if (typeof window.Actions !== 'function') return;
    var cajas = document.querySelectorAll('tr input.action-select');
    if (cajas.length === 0) return;
    formulario.dataset.baAcciones = '1';
    window.Actions(cajas);
  }

  function reengancharInlines() {
    var $ = window.django && window.django.jQuery;
    if (!$ || !$.fn.formset) return;
    $('.js-inline-admin-formset').each(function () {
      var grupo = $(this);
      // Cuando el plugin ya monto el grupo, su boton "añadir" (.add-row)
      // esta en la pagina: con eso no se vuelve a montar (si no, se
      // duplicarian botones y enganches de borrar filas).
      if (grupo.find('.add-row').length) return;
      var datos = grupo.data();
      if (!datos.inlineFormset) return;
      var opciones = datos.inlineFormset;
      var selector;
      if (datos.inlineType === 'stacked') {
        selector = opciones.name + '-group .inline-related';
        $(selector).stackedFormset(selector, opciones.options);
      } else if (datos.inlineType === 'tabular') {
        selector = opciones.name + '-group .tabular.inline-related tbody:first > tr.form-row';
        $(selector).tabularFormset(selector, opciones.options);
      }
    });
  }

  function hayCambiosSinGuardar() {
    var formularios = document.querySelectorAll('#content-main form');
    for (var i = 0; i < formularios.length; i++) {
      var campos = formularios[i].querySelectorAll('input, select, textarea');
      for (var j = 0; j < campos.length; j++) {
        var campo = campos[j];
        if (campo.type === 'hidden' || campo.type === 'file' ||
            campo.readOnly || campo.disabled) continue;
        // Sin nombre no es dato del formulario (el "marcar todo" de las
        // acciones, por ejemplo): al navegar no se pierde nada.
        if (!campo.name) continue;
        // El listado tambien es un formulario (marcar filas, elegir
        // accion): eso NO es editar nada, no se pregunta por ello.
        if (campo.name === '_selected_action' ||
            campo.name === 'select_across' || campo.name === 'action' ||
            campo.classList.contains('action-select')) continue;
        var tocado;
        if (campo.type === 'checkbox' || campo.type === 'radio') {
          tocado = campo.defaultChecked !== campo.checked;
        } else if (campo.tagName === 'SELECT') {
          var opcion = campo.options[campo.selectedIndex];
          tocado = opcion ? !opcion.defaultSelected : false;
        } else {
          tocado = campo.defaultValue !== campo.value;
        }
        if (tocado) return true;
      }
    }
    return false;
  }

  document.addEventListener('turbo:load', function () {
    if (primeraCarga) {
      primeraCarga = false;
      return;
    }
    reengancharAcciones();
    reengancharInlines();
  });

  // Sin esta red, navegar con cambios a medio escribir los pierde sin
  // preguntar (el navegador solo avisa en recargas de verdad).
  document.addEventListener('turbo:before-visit', function (evento) {
    if (hayCambiosSinGuardar() &&
        !window.confirm('Hay cambios sin guardar en esta página. ¿Salir de todos modos?')) {
      evento.preventDefault();
    }
  });
})();
