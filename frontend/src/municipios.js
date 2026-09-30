// Cabeceras municipales: identificador estable de cada municipio.
//
// Se usa como clave del <select> del buscador y para derivar el valor que
// se guarda en localStorage (DISENO.md R3.4), asi que tiene que ser la
// MISMA funcion del buscador y de Home. Dos provincias pueden tener
// municipio con el mismo nombre, por eso entra la provincia en la clave.
export const claveCabecera = (cabecera) =>
  `${cabecera.provincia}~${cabecera.municipio}`;
