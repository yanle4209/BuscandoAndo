package com.herling.buscandoando.core.network

import com.herling.buscandoando.core.data.dto.Business
import com.herling.buscandoando.core.data.dto.BusinessDetail
import com.herling.buscandoando.core.data.dto.Category
import com.herling.buscandoando.core.data.dto.PagedResponse
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Definición de tu API pública.
 *
 * Cada función = una ruta de Django. Retrofit genera el código HTTP
 * a partir de estas anotaciones (igual que decoradores).
 *
 *  Django                       Kotlin
 *  ─────────────────────────    ─────────────────────────────
 *  GET /api/categories/    →    @GET("categories/")
 *  GET /api/businesses/    →    @GET("businesses/")
 *  GET /api/businesses/X/  →    @GET("businesses/{slug}/")
 *
 * "suspend fun" = función que puede pausarse (como async/await).
 *   - No bloquea el hilo → la UI no se congela
 *   - Obliga a quien la llame a manejar la corrutina
 */
interface BuscandoAndoApi {

    /** GET /api/categories/  ->  { count, next, previous, results: [...] } */
    @GET("categories/")
    suspend fun getCategories(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): PagedResponse<Category>

    /**
     * GET /api/businesses/
     *
     * Todos los @Query son OPCIONALES: si el valor es null,
     * Retrofit NO agrega el parámetro a la URL.
     *
     *  Ejemplos reales que genera:
     *   text="hotel"          -> /api/businesses/?text=hotel
     *   lat=19.38&lng=-70.53  -> /api/businesses/?lat=19.38&lng=-70.53&radius=5
     *   sin filtros           -> /api/businesses/?page=1&page_size=12
     */
    @GET("businesses/")
    suspend fun getBusinesses(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 12,
        @Query("text") text: String? = null,
        @Query("category") category: Int? = null,
        @Query("lat") lat: Double? = null,
        @Query("lng") lng: Double? = null,
        @Query("radius") radius: Double? = null,
        @Query("featured") featured: Boolean? = null,
        @Query("operational_status") operationalStatus: String? = null,
    ): PagedResponse<Business>

    /** GET /api/businesses/?featured=true&page_size=20 */
    @GET("businesses/")
    suspend fun getFeatured(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20,
    ): PagedResponse<Business> = getBusinesses(page = page, pageSize = pageSize, featured = true)

    /**
     * GET /api/businesses/<slug>/
     *  @Path sustituye {slug} por el valor real.
     *
     *  ⚠️ Devuelve BusinessDetail (forma ANIDADA), NO Business (forma plana).
     */
    @GET("businesses/{slug}/")
    suspend fun getBusiness(
        @Path("slug") slug: String,
    ): BusinessDetail

    /**
     * GET /api/businesses/featured-by-search/
     *  ⚠️ Este endpoint NO está paginado: devuelve un arreglo plano.
     *  Si no hay filtros, Django responde [] (vacío).
     *
     *  lat/lng/radius van igual que en getBusinesses: los destacados
     *  se filtran dentro del MISMO círculo de 5 km (R1.2). Si no,
     *  "Destacados" podría enseñar un sitio a 12 km de quien busca.
     */
    @GET("businesses/featured-by-search/")
    suspend fun getFeaturedBySearch(
        @Query("text") text: String? = null,
        @Query("category") category: Int? = null,
        @Query("lat") lat: Double? = null,
        @Query("lng") lng: Double? = null,
        @Query("radius") radius: Double? = null,
    ): List<Business>
}
