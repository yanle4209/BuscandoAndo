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

  function copiar(boton, url) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(
        function () { anunciar(boton, 'Enlace copiado'); },
        function () { copiarAPie(boton, url); }
      );
    } else {
      copiarAPie(boton, url);
    }
  }

  function copiarAPie(boton, url) {
    // Sin portapapeles (permiso denegado, contexto no seguro): se abre
    // la caja de texto con el enlace ya puesto para copiarlo a mano.
    window.prompt('Copia el enlace para el colaborador:', url);
    anunciar(boton, 'Copia el enlace');
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
