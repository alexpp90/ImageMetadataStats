plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt.android)
    alias(libs.plugins.ksp)
    alias(libs.plugins.room)
}

android {
    namespace = "com.photoselectortoolbox"
    compileSdk = 36

    // Uniform product layout: every product in this repository exposes `src/`
    // and `tests/`, whatever its language. That overrides Gradle's default
    // src/main | src/test | src/androidTest convention on purpose — see
    // docs/README.md. Keep these four blocks in sync across the Android modules.
    sourceSets {
        getByName("main") {
            java.setSrcDirs(listOf("src"))
            res.setSrcDirs(listOf("res"))
            jniLibs.setSrcDirs(listOf("jniLibs"))
            manifest.srcFile("AndroidManifest.xml")
        }
        getByName("test") {
            java.setSrcDirs(listOf("tests/unit"))
        }
        getByName("androidTest") {
            java.setSrcDirs(listOf("tests/instrumented"))
        }
    }

    defaultConfig {
        applicationId = "com.photoselectortoolbox"
        minSdk = 26
        targetSdk = 36
        val baseVersion = System.getenv("VERSION_CODE")?.toIntOrNull() ?: 5
        val offset = System.getenv("TOOLBOX_VERSION_CODE_OFFSET")?.toIntOrNull()
            ?: System.getenv("VERSION_CODE_OFFSET")?.toIntOrNull()
            ?: 0
        versionCode = baseVersion + offset
        // Overridable from CI (e.g. derived from the git tag on release builds).
        versionName = System.getenv("TOOLBOX_VERSION_NAME")
            ?: System.getenv("VERSION_NAME")
            ?: "0.4.0"

        testInstrumentationRunner = "com.photoselectortoolbox.HiltTestRunner"

        ndk {
            abiFilters.addAll(setOf("arm64-v8a", "x86_64"))
        }
    }

    signingConfigs {
        create("release") {
            // App-scoped env vars so each app uses its own upload key (full isolation).
            val keystorePath = System.getenv("TOOLBOX_KEYSTORE_FILE")
            if (!keystorePath.isNullOrEmpty()) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("TOOLBOX_STORE_PASSWORD")
                keyAlias = System.getenv("TOOLBOX_KEY_ALIAS")
                keyPassword = System.getenv("TOOLBOX_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            val keystorePath = System.getenv("TOOLBOX_KEYSTORE_FILE")
            if (!keystorePath.isNullOrEmpty()) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests {
            isIncludeAndroidResources = true
        }
    }

    lint {
        abortOnError = false
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
        jniLibs {
            // Preserve 16 KB page alignment of native .so files (required for Android 15+)
            useLegacyPackaging = false
        }
    }
}

room {
    schemaDirectory("$projectDir/schemas")
}

dependencies {
    // Shared Android baseline (EXIF model + readers, storage detection)
    implementation(project(":core"))

    // AndroidX Core
    implementation(libs.androidx.core.ktx)

    // Compose BOM
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material3.window.size)
    implementation(libs.androidx.compose.material.icons.extended)
    debugImplementation(libs.androidx.compose.ui.tooling)

    // Activity & Navigation
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)

    // Lifecycle
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)

    // Room
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    // Window
    implementation(libs.androidx.window)

    // ExifInterface
    implementation(libs.androidx.exifinterface)

    // WorkManager
    implementation(libs.androidx.work.runtime.ktx)

    // DataStore
    implementation(libs.androidx.datastore.preferences)

    // DocumentFile
    implementation(libs.androidx.documentfile)

    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.android.compiler)
    implementation(libs.androidx.hilt.navigation.compose)


    // Coil (image loading)
    implementation(libs.coil.compose)

    // Vico (charts)
    implementation(libs.vico.core)
    implementation(libs.vico.compose)
    implementation(libs.vico.compose.m3)

    // OpenCV
    implementation(libs.opencv.android)

    // TensorFlow Lite — on-device NIMA aesthetic scoring.
    // The .tflite model is loaded from assets at runtime; if absent the
    // AestheticAnalyzer degrades gracefully (no aesthetic score shown).
    implementation("org.tensorflow:tensorflow-lite:2.14.0")

    // Testing — JVM unit tests
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.turbine)
    testImplementation(libs.mockk)
    testImplementation(libs.robolectric)
    testImplementation(libs.hilt.android.testing)
    testImplementation(libs.androidx.room.testing)
    kspTest(libs.hilt.android.compiler)

    // Testing — instrumented (androidTest)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.kotlinx.coroutines.test)
    androidTestImplementation(libs.hilt.android.testing)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.room.testing)
    kspAndroidTest(libs.hilt.android.compiler)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}
