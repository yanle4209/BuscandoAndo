// Los numeros de un contacto que guardo varios, uno por parte.
//
// El backend los une en una sola cadena con la convencion de OSM
// (`;`, `,`, `/` o `|`) — es lo que cabe en contact.phone — y aqui se
// vuelven a partir para pintar cada uno con su propio enlace `tel:`:
// un href con dos numeros pegados no marca a nadie.
export function partirTelefono(valor) {
  if (!valor) return [];
  return valor
    .split(/[;,/|]/)
    .map((parte) => parte.trim())
    .filter(Boolean);
}
