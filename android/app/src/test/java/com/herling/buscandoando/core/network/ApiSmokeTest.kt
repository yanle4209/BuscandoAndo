package com.herling.buscandoando.core.network

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * PRUEBA DE HUMO (smoke test)
 *
 * No prueba logica: solo verifica que la cadena
 *   Retrofit -> HTTP -> JSON -> data class
 * funciona contra tu servidor REAL.
 *
 * Se ejecuta en la JVM de tu PC (no en el emulador),
 * asi que puede tocar internet directo.
 *
 *  Ejecutar:  gradlew.bat test --tests "*ApiSmokeTest"
 */
class ApiSmokeTest {

    @Test
    fun `las categorias llegan desde el servidor`() = runBlocking {
        val resp = ApiClient.api.getCategories(pageSize = 5)

        println("=== CATEGORIAS (count=${resp.count}) ===")
        resp.results.forEach { println("   ${it.icon}  ->  ${it.name}") }

        assertTrue("El API no devolvio categorias", resp.results.isNotEmpty())
    }

    @Test
    fun `los negocios se parsean sin crashear`() = runBlocking {
        val resp = ApiClient.api.getBusinesses(page = 1, pageSize = 12)

        println("=== NEGOCIOS (count=${resp.count}) ===")
        resp.results.forEach { b ->
            println(
                "   ${b.name} | cat=${b.category_name} | ${b.effective_status_name} " +
                    "| phone=${b.phone} | lat=${b.latitude} | imgs=${b.images.size}"
            )
        }

        assertTrue("El API no devolvio negocios", resp.results.isNotEmpty())
        assertTrue("Faltan campos obligatorios", resp.results.all { it.name.isNotBlank() })
    }

    @Test
    fun `la busqueda por texto filtra`() = runBlocking {
        val resp = ApiClient.api.getBusinesses(text = "hospital", pageSize = 5)

        println("=== BUSQUEDA 'hospital' -> ${resp.count} resultados ===")
        resp.results.forEach { println("   ${it.name}") }

        assertTrue("El filtro 'text' no funciono", resp.count > 0)
    }

    /**
     * PRUEBA DEL DETALLE ANIDADO.
     * Verifica los 3 campos que aprendiste a escribir:
     *   location { }  ->  LocationDto?
     *   contact  { }  ->  ContactDto?
     *   hours    [ ]  ->  List<HourDto>
     */
    @Test
    fun `el detalle anidado se parsea sin crashear`() = runBlocking {
        val slug = ApiClient.api.getBusinesses(pageSize = 1).results.first().slug
            ?: error("El Business no trae slug")

        val d = ApiClient.api.getBusiness(slug)

        println("=== DETALLE: ${d.name} ===")
        println("   slug      : ${d.slug}")
        println("   direccion : ${d.location?.full_address}")
        println("   persona   : ${d.contact?.contact_person}")
        println("   phone     : ${d.contact?.phone}")
        println("   dias      : ${d.hours.size}")
        d.hours.forEach { h ->
            println(
                "      ${h.day}: ${h.open_time ?: "--:--"} -> ${h.close_time ?: "--:--"}" +
                    "   cerrado=${h.is_closed}  feriado=${h.is_holiday}"
            )
        }
        println("   imagenes  : ${d.images.size}")

        assertTrue("location vino null -> el objeto { } no se parseo", d.location != null)
        assertTrue("contact vino null -> el objeto { } no se parseo", d.contact != null)
        assertTrue("hours debia traer los 7 dias", d.hours.size >= 7)
        assertTrue("open_time debia ser TEXTO", d.hours.any { it.open_time == "08:00:00" })
        assertTrue("algun dia cerrado debia venir null", d.hours.any { it.open_time == null })
        assertTrue("falta street dentro de location", !d.location?.street.isNullOrBlank())
    }
}
