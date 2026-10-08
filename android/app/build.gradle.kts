import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    // Activa @Serializable: convierte data classes <-> JSON
    alias(libs.plugins.kotlin.serialization)
}

// ── Firma de release (certificado propio) ──
//
// Los datos viven en keystore.properties + keystore/*.jks, los dos
// cubiertos por android/.gitignore (sección 5): NUNCA se suben a git.
//
// Sin esos ficheros, `assembleDebug` sale igual que siempre y
// `assembleRelease` falla a propósito al empaquetar: es preferible
// que falle a que se firme con OTRO certificado y entonces quien ya
// tenga la app instalada no pueda actualizarla (Android rechaza
// cambiar de firma).
val firmaRelease = rootProject.file("keystore.properties")
    .takeIf { it.exists() }
    ?.let { archivo ->
        Properties().apply { archivo.inputStream().use { load(it) } }
    }

android {
    namespace = "com.herling.buscandoando"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.herling.buscandoando"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // ── Fase 7 · URL del API inyectada por Gradle ──
        //
        // Antes estaba escrita a mano en ApiClient. Ahora sale de
        // aquí, así que se puede apuntar a otro backend SIN editar
        // ni olvidarse de revertir ningún archivo de código:
        //
        //   Producción (por defecto):
        //     gradlew assembleDebug
        //
        //   Backend local en el host (10.0.2.2 = el PC visto desde
        //   el emulador de Android):
        //     gradlew assembleDebug -PapiBaseUrl=http://10.0.2.2:8765/api/
        //
        //  providers.gradleProperty() en vez de findProperty() para
        //  que Gradle lo registre en la "configuration cache".
        val apiBaseUrl = providers.gradleProperty("apiBaseUrl").orNull
            ?: "https://buscandoando.onrender.com/api/"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
    }

    signingConfigs {
        if (firmaRelease != null) {
            create("release") {
                storeFile = rootProject.file(firmaRelease.getProperty("storeFile"))
                storePassword = firmaRelease.getProperty("storePassword")
                keyAlias = firmaRelease.getProperty("keyAlias")
                keyPassword = firmaRelease.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
            // Sin keystore (clon limpio / otra máquina) queda sin
            // firmar y el empaquetado fallará; ver el comentario de
            // `firmaRelease`.
            signingConfig = if (firmaRelease != null) {
                signingConfigs.getByName("release")
            } else {
                null
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        // Genera BuildConfig.API_BASE_URL (ver defaultConfig).
        buildConfig = true
    }
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.material.icons.core)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    // Fase 3 — ViewModel + StateFlow conectados a Compose
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)

    // ----- Red (Fase 2) -----
    implementation(libs.retrofit.core)                              // peticiones HTTP
    implementation(libs.retrofit.kotlinx.serialization)             // JSON <-> data class
    implementation(libs.kotlinx.serialization.json)                 // motor de JSON

    // ----- Imágenes (Fase 3) -----
    implementation(libs.coil.compose)                              // AsyncImage en Compose
    implementation(libs.coil.network.okhttp)                       // carga por HTTP

    // ----- Mapa (Fase 5) -----
    implementation(libs.osmdroid)                                  // OpenStreetMap sin API key

    // ----- GPS (Fase 6) -----
    implementation(libs.play.services.location)                    // FusedLocationProvider

    testImplementation(libs.junit)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
