// El estado de un negocio, IGUAL en la tarjeta, en el modal y en la
// ficha (/business/:slug): mismo slug para la clase de CSS y la misma
// etiqueta para el texto. Las tres vistas llamaban a lo mismo por su
// cuenta y la ficha se quedaba con el estado DECLARADO en la base
// (lo que dice el dueño) en vez del calculado (lo que dice el
// horario de hoy), con lo que la tarjeta podia decir "Cerrado" y la
// ficha "Abierto" del mismo negocio.
//
// El que manda es `effective_status`: lo calcula el backend con los
// horarios del dia (abierto / cerrado / por-horario). Si no llega
// (respuesta vieja en caché, endpoint que no lo traiga) se cae al
// estado declarado en la base; y si no hay ninguno, a 'default'
// neutro: mejor un "Sin estado" sin color que un color que miente.

export function slugDeEstado(biz) {
  return biz.effective_status || biz.operational_status_slug || 'default';
}

export function nombreDeEstado(biz) {
  return biz.effective_status_name || biz.operational_status_name || 'Sin estado';
}
