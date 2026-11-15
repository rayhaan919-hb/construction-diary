import java.net.URI
import java.time.Instant
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) {
        f.inputStream().use(::load)
    }
}

fun propOrEnv(envKey: String, propKey: String, localKey: String? = null): String {
    val fromProp = project.findProperty(propKey)?.toString()?.trim()
    if (!fromProp.isNullOrEmpty()) return fromProp
    val fromEnv = System.getenv(envKey)?.trim()
    if (!fromEnv.isNullOrEmpty()) return fromEnv
    if (localKey != null) {
        val fromLocal = localProps.getProperty(localKey)?.trim()
        if (!fromLocal.isNullOrEmpty()) return fromLocal
    }
    return ""
}

fun requireValidHttpsEndpoint(url: String, envLabel: String, docHint: String) {
    val normalized = url.trim().trimEnd('/')
    if (normalized.isEmpty()) {
        throw GradleException(
            "$envLabel builds require an explicit HTTPS API endpoint ($docHint). " +
                "Refusing to fall back to development or placeholder URLs."
        )
    }
    val parsed = try {
        URI(normalized)
    } catch (e: Exception) {
        throw GradleException("$envLabel API URL is invalid: '$normalized'", e)
    }
    val host = parsed.host?.lowercase() ?: ""
    val isForbiddenHost =
        parsed.scheme?.lowercase() != "https" ||
            host.isEmpty() ||
            host == "localhost" ||
            host == "127.0.0.1" ||
            host == "10.0.2.2" ||
            host == "0.0.0.0" ||
            host == "::1" ||
            host == "example.com" ||
            host.endsWith(".example.com") ||
            host.endsWith(".example.org") ||
            host.endsWith(".example.net")
    if (isForbiddenHost) {
        throw GradleException(
            "$envLabel builds require a non-local HTTPS API endpoint (no http://, localhost, " +
                "emulator loopback, or .example.* placeholder). Got '$normalized'."
        )
    }
}

val debugApiBaseUrl: String = (
    propOrEnv("DEV_API_BASE_URL", "DEV_API_BASE_URL", "api.devBaseUrl")
        .ifEmpty { propOrEnv("API_BASE_URL", "API_BASE_URL", "api.baseUrl") }
        .ifEmpty { "http://10.0.2.2:8000" }
    ).trimEnd('/')

val stagingApiBaseUrl: String = propOrEnv(
    "STAGING_API_BASE_URL",
    "STAGING_API_BASE_URL",
    "api.stagingBaseUrl"
).trimEnd('/')

val prodApiBaseUrl: String = (
    propOrEnv("PROD_API_BASE_URL", "PROD_API_BASE_URL", "api.prodBaseUrl")
        .ifEmpty { propOrEnv("RELEASE_API_BASE_URL", "RELEASE_API_BASE_URL", "api.releaseBaseUrl") }
    ).trimEnd('/')

val appVersionCode: Int = propOrEnv("VERSION_CODE", "VERSION_CODE").toIntOrNull() ?: 1
val appVersionName: String = propOrEnv("VERSION_NAME", "VERSION_NAME").ifEmpty { "1.0.0" }

val keystorePath = propOrEnv("ANDROID_KEYSTORE_PATH", "RELEASE_STORE_FILE")
val keystorePassword = propOrEnv("ANDROID_KEYSTORE_PASSWORD", "RELEASE_STORE_PASSWORD")
val keystoreAlias = propOrEnv("ANDROID_KEY_ALIAS", "RELEASE_KEY_ALIAS")
val keystoreKeyPassword = propOrEnv("ANDROID_KEY_PASSWORD", "RELEASE_KEY_PASSWORD")

val requestedTasks = gradle.startParameter.taskNames
val isStagingTaskRequested = requestedTasks.any {
    it.substringAfterLast(':').contains("Staging", ignoreCase = true)
}
val isReleaseTaskRequested = requestedTasks.any { task ->
    val taskName = task.substringAfterLast(':')
    (taskName != "generateReleaseMetadata" && taskName.contains("Release", ignoreCase = true)) ||
        taskName.equals("assemble", ignoreCase = true) ||
        taskName.equals("bundle", ignoreCase = true)
}

if (isStagingTaskRequested) {
    requireValidHttpsEndpoint(
        stagingApiBaseUrl,
        "Staging",
        "STAGING_API_BASE_URL / -PSTAGING_API_BASE_URL / local.properties api.stagingBaseUrl"
    )
}
if (isReleaseTaskRequested) {
    requireValidHttpsEndpoint(
        prodApiBaseUrl,
        "Production Release",
        "PROD_API_BASE_URL / -PPROD_API_BASE_URL (or RELEASE_API_BASE_URL) in secure release configuration"
    )
}

if (isStagingTaskRequested || isReleaseTaskRequested) {
    val label = if (isReleaseTaskRequested) "Production release" else "Staging release"
    if (keystorePath.isEmpty() ||
        !file(keystorePath).exists() ||
        keystorePassword.isEmpty() ||
        keystoreAlias.isEmpty() ||
        keystoreKeyPassword.isEmpty()
    ) {
        throw GradleException(
            "$label builds require ANDROID_KEYSTORE_PATH (existing file), ANDROID_KEYSTORE_PASSWORD, " +
                "ANDROID_KEY_ALIAS, and ANDROID_KEY_PASSWORD (or -PRELEASE_STORE_FILE / " +
                "-PRELEASE_STORE_PASSWORD / -PRELEASE_KEY_ALIAS / -PRELEASE_KEY_PASSWORD). " +
                "Refusing to emit an unsigned or falsely labelled release artifact."
        )
    }
}

android {
    namespace = "com.sitediary.mobile"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.sitediary.mobile"
        minSdk = 26
        targetSdk = 36
        versionCode = appVersionCode
        versionName = appVersionName

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "API_BASE_URL", "\"$debugApiBaseUrl\"")
        buildConfigField("String", "API_ENV", "\"dev\"")
    }

    signingConfigs {
        create("release") {
            if (keystorePath.isNotEmpty() && file(keystorePath).exists()) {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                keyAlias = keystoreAlias
                keyPassword = keystoreKeyPassword
            }
        }
    }

    buildTypes {
        debug {
            buildConfigField("String", "API_BASE_URL", "\"$debugApiBaseUrl\"")
            buildConfigField("String", "API_ENV", "\"dev\"")
        }
        create("staging") {
            matchingFallbacks += listOf("release")
            applicationIdSuffix = ".staging"
            versionNameSuffix = "-staging"
            buildConfigField("String", "API_BASE_URL", "\"$stagingApiBaseUrl\"")
            buildConfigField("String", "API_ENV", "\"staging\"")
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        release {
            buildConfigField("String", "API_BASE_URL", "\"$prodApiBaseUrl\"")
            buildConfigField("String", "API_ENV", "\"prod\"")
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests {
            isReturnDefaultValues = true
        }
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
    arg("room.incremental", "true")
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    debugImplementation(libs.androidx.compose.ui.tooling)

    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)
    implementation(libs.androidx.hilt.navigation.compose)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.exifinterface)

    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)

    implementation(libs.coil.compose)

    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.kotlinx.serialization)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)

    testImplementation(libs.junit)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.androidx.room.testing)
    testImplementation(libs.androidx.work.testing)
}

tasks.register("generateReleaseMetadata") {
    group = "verification"
    description = "Emits build metadata and version manifest for staging/release verification."
    doLast {
        val requestedEnv = if (isReleaseTaskRequested) "prod" else if (isStagingTaskRequested) "staging" else "dev"
        val variantDir = if (requestedEnv == "prod") "release" else if (requestedEnv == "staging") "staging" else "debug"
        val apiEndpoint = when (requestedEnv) {
            "prod" -> prodApiBaseUrl
            "staging" -> stagingApiBaseUrl
            else -> debugApiBaseUrl
        }
        val apiHost = runCatching { URI(apiEndpoint).host ?: "" }.getOrDefault("")
        val gitSha = System.getenv("GITHUB_SHA")?.takeIf { it.isNotBlank() } ?: "local-working-tree"
        val outDir = layout.buildDirectory.dir("outputs/release-metadata/$variantDir").get().asFile
        outDir.mkdirs()
        val metadataFile = File(outDir, "build-metadata.json")
        metadataFile.writeText(
            """
            {
              "applicationId": "com.sitediary.mobile${if (requestedEnv == "staging") ".staging" else ""}",
              "buildType": "$variantDir",
              "apiEnvironment": "$requestedEnv",
              "apiHost": "$apiHost",
              "compileSdk": 37,
              "targetSdk": 36,
              "minSdk": 26,
              "versionCode": $appVersionCode,
              "versionName": "$appVersionName${if (requestedEnv == "staging") "-staging" else ""}",
              "signedWithExternalKeystore": ${keystorePath.isNotEmpty()},
              "productionReady": ${requestedEnv == "prod" && keystorePath.isNotEmpty() && prodApiBaseUrl.isNotEmpty()},
              "gitSha": "$gitSha",
              "generatedAtUtc": "${Instant.now()}"
            }
            """.trimIndent() + "\n"
        )
        println("Wrote Android release metadata to ${metadataFile.absolutePath}")
    }
}
