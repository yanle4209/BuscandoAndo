plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    // Activa @Serializable: convierte data classes <-> JSON
    alias(libs.plugins.kotlin.serialization)
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

    buildTypes {
        release {
            optimization {
                enable = false
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
