# Reglas de R8/minificacion para BuscandoAndo.
#
# R8 se QUEDA solo con el codigo que alcanza desde tus pantallas. Aqui se
# protege lo que el R8 NO puede deducir porque se usa por REFLEXION o por
# anotaciones, que es justo donde el shrinker se come lo que hace falta y la
# app compila bien pero CRASHEA al correr en release.

# ── kotlinx.serialization ──
#
# `serializer()` se resuelve en tiempo de ejecucion por reflexion sobre la
# data class @Serializable. Si R8 poda el companion serializer, el primer
# GET revienta con SerializationException aunque el codigo se vea correcto.
# Lo que protegemos son las CLASES con @Serializable del paquete de DTOs.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers @kotlinx.serialization.Serializable class ** {
    *** Companion;
    *** INSTANCE;
    kotlinx.serialization.KSerializer serializer(...);
}
# Los DTO del API (Business, Cabecera, CorrectionPayload...) viven aqui.
# Regla explicita: si anyade un @Serializable en otro paquete, anadirlo.
-keep class com.herling.buscandoando.core.data.dto.** { *; }

# ── Retrofit ──
#
# Retrofit anota los metodos de la interfaz con @GET/@POST y las resuelve
# por reflexion. Sin las firmas intactas, retrofit.create() lanza
# "Could not locate Retrofit annotation" al arrancar.
-keepattributes Signature, Exceptions
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
-dontwarn org.codehaus.mojo.animal_sniffer.IgnoreJRERequirement
-dontwarn javax.annotation.**
-dontwarn kotlin.Unit
-dontwarn retrofit2.KotlinExtensions
-dontwarn retrofit2.KotlinExtensions$*
-if interface * { @retrofit2.http.* <methods>; }
-keep,allowobfuscation interface <1>

# ── osmdroid ──
#
# osmdroid NO trae consumer rules (verificado: el .aar no contiene ningun
# .pro), asi que R8 lo poda COMPLETO por no ver refs estaticas. Medido en
# el APK con R8 y sin estas reglas: GeoPoint, MapView, TileSourceFactory,
# MapController y Polyline aparecian 0 veces en el dex — o sea el mapa
# moria con ClassNotFoundException al abrir MapScreen.kt.
#
# Se conserva el paquete entero: osmdroid se instancia por reflexion desde
# los XML del manifiesto (permisos osmdroid_tiles) y desde MapView(ctx).
-dontwarn org.osmdroid.**
-keep class org.osmdroid.** { *; }
-keep interface org.osmdroid.** { *; }

# ── Coil ──
#
# Coil usa Factory por reflexion para decodificar tipos; podar sus
# componentes rompe la carga de imagenes del carrusel de fotos.
-dontwarn coil.**
-keep class coil.** { *; }
