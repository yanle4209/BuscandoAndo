/**
 * BuscandoAndo Admin — Compartir el enlace del levantamiento
 *
 * El panel [data-ba-compartir] entrega al colaborador el enlace de la
 * herramienta de campo. El boton usa Web Share (el boton nativo del
 * movil: WhatsApp, correo, lo que el sistema ofrezca) y, si no lo hay,
 * copia al portapapeles: el admin se abre desde el telefono y desde el
 * escritorio y las dos formas tienen que servir.
 *
 * Sin JS el enlace sigue funcionando: el texto del enlace es un <a>.
 */
(function () {
  'use strict';

  function anunciar(boton, texto) {
    var caja = boton.parentElement
      ? boton.parentElement.querySelector('[data-ba-estado]')
      : null;
    if (!caja) return;
    caja.textContent = texto;
    clearTimeout(caja.__temporizador);
    caja.__temporizador = setTimeout(function () {
      caja.textContent = '';
    }, 4000);
  }

  function enlaceDelPanel(boton) {
    var acciones = boton.parentElement;
    var panel = acciones ? acciones.parentElement : null;
    return panel ? panel.querySelector('a.ba-levantamiento__enlace') : null;
  }

  function copiar(boton, url) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () { anunciar(boton, 'Enlace copiado'); },
        function () { copiarSinPermiso(boton, url); }
      );
    } else {
      copiarSinPermiso(boton, url);
    }
  }

  function copiarSinPermiso(boton, url) {
    // El portapapeles puede estar denegado o no existir (contexto no
    // seguro, navegador viejo). Se selecciona el enlace VISIBLE para
    // copiarlo con Ctrl+C y se intenta copiar a la antigua.
    var enlace = enlaceDelPanel(boton);
    if (enlace && window.getSelection && document.createRange) {
      var seleccion = window.getSelection();
      var rango = document.createRange();
      rango.selectNodeContents(enlace);
      seleccion.removeAllRanges();
      seleccion.addRange(rango);
      try {
        if (document.execCommand('copy')) {
          anunciar(boton, 'Enlace copiado');
          return;
        }
      } catch (e) { /* se sigue por la caja de texto */ }
    }

    try {
      window.prompt('Copia el enlace para el colaborador:', url);
      anunciar(boton, 'Copia el enlace');
    } catch (e) {
      // Navegador sin prompt(): el enlace ya esta seleccionado, el
      // aviso solo tiene que decir que copie de ahi.
      anunciar(boton, 'Enlace seleccionado, copialo');
    }
  }

  document.addEventListener('click', function (evento) {
    var objetivo = evento.target;
    var boton = (objetivo && objetivo.closest)
      ? objetivo.closest('[data-ba-compartir]')
      : null;
    if (!boton) return;

    evento.preventDefault();

    var url = boton.getAttribute('data-ba-url');
    if (!url) return;

    if (navigator.share) {
      navigator.share({
        title: boton.getAttribute('data-ba-titulo') || 'BuscandoAndo',
        text: boton.getAttribute('data-ba-texto') || '',
        url: url
      }).then(function () {
        anunciar(boton, 'Compartido');
      }, function (error) {
        // Cancelado a mitad por el usuario: no se copia nada sin que
        // lo pida. El resto de fallos vuelven al portapapeles.
        if (error && error.name === 'AbortError') return;
        copiar(boton, url);
      });
      return;
    }

    copiar(boton, url);
  });
})();
