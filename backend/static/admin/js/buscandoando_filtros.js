/**
 * BuscandoAndo - Los filtros del listado que van con <select>.
 *
 * MUNICIPIOS: trae158 municipios en32 provincias: pintados en una sola
 * lista era ingobernable. Se resuelve con DOS desplegables encadenados
 * —segun pide el admin—: al elegir provincia se recorta el segundo, que
 * solo ofrece los municipios de esa.
 *
 * CATEGORIA: va con UN desplegable y sin encadenar nada, porque las
 * categorias son planas —ninguna tiene hija—. Aqui lo que importa es que
 * las opciones se vean sin desplegar nada, que es lo que no dejaba el
 * <details> de antes.
 *
 * En los dos, los <option> van con su query_string ya montada (la misma
 * que usaban los enlaces viejos), asi que elegir navega y conserva lo
 * demas de la URL (orden, otros filtros, pagina).
 *
 * LA URL MANDA, no el `.selected` del DOM: Chrome guarda en el perfil el
 * ultimo valor elegido en un desplegable y lo restaura DESPUES de este
 * script, lo que dejaban el panel mintiendo (sin filtro en la barra pero
 * "Mao" marcado). Por eso el estado se reconstruye leyendo
 * location.search, y se vuelve a sincronizar en `load`, cuando esa
 * restauracion ya ha pasado.
 *
 * Sin `disabled` en el HTML: si este script fallara, el segundo
 * desplegable sigue listando los municipios en vez de quedar muerto.
 *
 * Corre bajo Turbo (DISENO 15): el panel navega sin recargar, asi que hay
 * que atender turbo:load ademas de DOMContentLoaded, con la misma guarda
 * que business_admin.js.
 */
(function() {
    'use strict';

    var raiz = null;
    var selProvincia = null;
    var selMunicipio = null;
    var opcionTodos = null;
    var opcionesMunicipio = [];

    /** Vuelve a llenar el de municipios segun la provincia. */
    function recortar(provincia) {
        // Se vacia entero y se recoloca lo que toque: un <option> no
        // se puede ocultar de forma fiable entre navegadores.
        while (selMunicipio.firstChild) {
            selMunicipio.removeChild(selMunicipio.firstChild);
        }
        if (opcionTodos) {
            selMunicipio.appendChild(opcionTodos);
        }
        opcionesMunicipio.forEach(function(op) {
            var delProvincia = op.getAttribute('data-provincia');
            if (delProvincia && (!provincia || delProvincia === provincia)) {
                selMunicipio.appendChild(op);
            }
        });
    }

    /**
     * El municipio que trae la barra, o null si no trae ninguno.
     *
     * Se lee SOLO ese trozo de la URL, no la query_string entera de la
     * opcion: `cl.params` no arrastra el `p` de pagina ni el `o` de orden,
     * asi que con la comparacion entera una URL paginada no llegaba nunca
     * a coincidir y el panel se quedaba en "Todos" mintiendo.
     */
    function municipioDeLaUrl() {
        var trozo = /[?&]location__municipality=([^&]*)/
            .exec(window.location.search);
        if (!trozo) return null;
        try {
            // El servidor lo recibe ya decodificado, y con `+` para el
            // espacio: el panel tiene que mirarlo igual.
            return decodeURIComponent(trozo[1].replace(/\+/g, ' '));
        } catch (e) {
            // Un % a medias no deberia tumbar el panel entero.
            return null;
        }
    }

    /**
     * Reconstruye el estado a partir de la URL.
     *
     * Cada opcion trae como value la query_string completa de su
     * municipio —eso es con lo que NAVEGA—, pero para identificarla se
     * usa su `data-valor`, que es el municipio sin codificar.
     */
    function sincronizar() {
        var municipio = municipioDeLaUrl();
        var elegida = null;
        var provincia = '';

        if (municipio) {
            opcionesMunicipio.some(function(op) {
                if (op.getAttribute('data-valor') === municipio) {
                    elegida = op;
                    return true;
                }
                return false;
            });
            if (elegida) {
                provincia = elegida.getAttribute('data-provincia') || '';
            }
        }

        selProvincia.value = provincia;
        recortar(provincia);

        // Se fuerza a mano: la restauracion del navegador puede haber
        // dejado marcado un municipio que ya no corresponde.
        if (elegida) {
            elegida.selected = true;
        } else if (opcionTodos) {
            opcionTodos.selected = true;
        }
    }

    /** Cablea el filtro una sola vez. Devuelve false si ya estaba. */
    function montar() {
        raiz = document.querySelector('[data-filtro-municipio]');
        if (!raiz) return false;
        // Guarda contra Turbo: si ya quedo cableado, no cablear dos veces.
        if (raiz.dataset.listo === '1') return false;

        selProvincia = raiz.querySelector('[data-provincia]');
        selMunicipio = raiz.querySelector('[data-municipio]');
        if (!selProvincia || !selMunicipio) return false;

        raiz.dataset.listo = '1';

        // Todos los municipios tal cual vienen del servidor. Se guarda el
        // nodo, no el HTML, para poder recolocarlo sin reparsear.
        var todos = Array.prototype.slice.call(selMunicipio.options);
        opcionesMunicipio = todos.filter(function(op) {
            return op.hasAttribute('data-provincia');
        });
        opcionTodos = todos.filter(function(op) {
            return op.hasAttribute('data-todos');
        })[0] || null;

        selProvincia.addEventListener('change', function() {
            // Cambiar de provincia no navega: solo recorta. El municipio
            // vuelve a "Todos" porque el anterior dejo de existir aqui.
            recortar(selProvincia.value);
            if (opcionTodos) {
                opcionTodos.selected = true;
            }
        });

        selMunicipio.addEventListener('change', function() {
            var elegida = selMunicipio.options[selMunicipio.selectedIndex];
            var destino = elegida ? elegida.value : '';
            // "Todos los municipios" tambien navega: es como se quita el
            // filtro, y su value ya trae la URL sin el parametro.
            if (destino) {
                window.location.assign(destino);
            }
        });

        return true;
    }

    function arrancar() {
        if (montar()) {
            sincronizar();
        }
    }

    var yaCargoElDom = false;

    document.addEventListener('DOMContentLoaded', function() {
        yaCargoElDom = true;
        arrancar();
    });

    // La restauracion de formularios del navegador llega DESPUES de
    // DOMContentLoaded: aqui se recupera lo que haya pisado.
    window.addEventListener('load', function() {
        if (raiz) sincronizar();
    });

    document.addEventListener('turbo:load', function() {
        if (yaCargoElDom) {
            yaCargoElDom = false;
            return;
        }
        arrancar();
    });
})();


/**
 * El de categoria: un solo desplegable, sin encadenar nada.
 *
 * Cada opcion trae su query_string montada —eso es con lo que NAVEGA— y
 * ademas su categoria en `data-valor`, que es con lo que se identifica
 * leyendo la URL: se compara SOLO el trozo `?category=` de
 * location.search, nunca la query_string entera, que ademas del filtro
 * trae el `p` de pagina y el `o` de orden.
 *
 * Sin JS el desplegable sigue listando las categorias —lo mismo que el de
 * municipio—: no se puede elegir, pero nada queda escondido.
 */
(function() {
    'use strict';

    var sel = null;

    /** Devuelve el `category` de la barra, o vacio si no lo trae. */
    function categoriaDeLaUrl() {
        var trozo = /[?&]category=([^&]*)/.exec(window.location.search);
        if (!trozo) return '';
        try {
            // El servidor lo recibe ya decodificado: el panel tiene que
            // mirarlo igual para que los dos digan lo mismo.
            return decodeURIComponent(trozo[1].replace(/\+/g, ' '));
        } catch (e) {
            // Un % a medias: se mira tal cual, que no coincide con nada.
            return trozo[1];
        }
    }

    /**
     * Reconstruye el estado a partir de la URL.
     *
     * La restauracion del navegador llega despues de DOMContentLoaded y
     * puede dejar marcada una categoria que ya no corresponde: si no hay
     * coincidencia manda la primera ("Todas las categorias").
     */
    function sincronizar() {
        var valor = categoriaDeLaUrl();
        var elegida = null;
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].getAttribute('data-valor') === valor) {
                elegida = sel.options[i];
                break;
            }
        }
        (elegida || sel.options[0]).selected = true;
    }

    function arrancar() {
        sel = document.querySelector('[data-filtro-categoria]');
        if (!sel) return;
        // Guarda contra Turbo: si ya quedo cableado, no cablear dos veces.
        if (sel.dataset.listo === '1') {
            sincronizar();
            return;
        }
        sel.dataset.listo = '1';

        sel.addEventListener('change', function() {
            var opcion = sel.options[sel.selectedIndex];
            // "Todas las categorias" tambien navega: es como se quita el
            // filtro, y su value ya trae la URL sin el parametro.
            if (opcion && opcion.value) {
                window.location.assign(opcion.value);
            }
        });

        sincronizar();
    }

    var yaCargoElDom = false;

    document.addEventListener('DOMContentLoaded', function() {
        yaCargoElDom = true;
        arrancar();
    });

    window.addEventListener('load', function() {
        if (sel) sincronizar();
    });

    document.addEventListener('turbo:load', function() {
        if (yaCargoElDom) {
            yaCargoElDom = false;
            return;
        }
        arrancar();
    });
})();
