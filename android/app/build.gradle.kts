plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "kz.digitouch.posters"
    compileSdk = 34

    defaultConfig {
        applicationId = "kz.digitouch.posters"
        minSdk = 24
        targetSdk = 34
        versionCode = 2
        versionName = "1.0.1"

        // Сокращаем нативные библиотеки (CameraX/ML Kit) до досочных ABI — иначе APK раздувается.
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }

        // По умолчанию приложение требует активацию лицензионным ключом.
        // Отдельные flavor-сборки могут отключить это (REQUIRES_ACTIVATION = false).
        buildConfigField("Boolean", "REQUIRES_ACTIVATION", "true")
        // Вариант (предмет) сборки для проверки лицензии v4. -1 = любой (переопределяется во flavor).
        buildConfigField("int", "VARIANT_ID", "-1")
    }

    // Подпись релизных APK
    signingConfigs {
        create("release") {
            // Укажите свои пути к keystore:
            // storeFile = file("keystore/release.jks")
            // storePassword = "your_store_password"
            // keyAlias = "your_key_alias"
            // keyPassword = "your_key_password"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Подписываем debug-ключом для sideloading на доски DigiTouch
            signingConfig = signingConfigs.getByName("debug")
        }
        debug {
            isDebuggable = true
        }
    }

    // =====================================================
    // PRODUCT FLAVORS — один flavor = один предмет = один APK
    // При добавлении нового предмета:
    //   1. Добавьте flavor сюда
    //   2. Создайте папку app/src/<id>/assets/posters/<id>/
    //   3. Положите туда HTML-плакаты
    //   4. Добавьте subjects_<id>.json в app/src/<id>/assets/
    // =====================================================
    flavorDimensions += "subject"

    productFlavors {
        create("allsubjects") {
            dimension = "subject"
            applicationIdSuffix = ".all"
            // Полная версия со всеми предметами — ключ «все предметы» (variant 0)
            buildConfigField("String", "SUBJECT_ID", "\"all\"")
            buildConfigField("String", "APP_TITLE", "\"Интерактивные плакаты\"")
            buildConfigField("int", "VARIANT_ID", "0")
        }
        create("physics") {
            dimension = "subject"
            applicationIdSuffix = ".physics"
            buildConfigField("String", "SUBJECT_ID", "\"physics\"")
            buildConfigField("String", "APP_TITLE", "\"Физика\"")
            buildConfigField("int", "VARIANT_ID", "1")
        }
        create("mathematics") {
            dimension = "subject"
            applicationIdSuffix = ".mathematics"
            buildConfigField("String", "SUBJECT_ID", "\"mathematics\"")
            buildConfigField("String", "APP_TITLE", "\"Математика\"")
            buildConfigField("int", "VARIANT_ID", "2")
        }
        create("biology") {
            dimension = "subject"
            applicationIdSuffix = ".biology"
            buildConfigField("String", "SUBJECT_ID", "\"biology\"")
            buildConfigField("String", "APP_TITLE", "\"Биология\"")
            buildConfigField("int", "VARIANT_ID", "3")
        }
        create("chemistry") {
            dimension = "subject"
            applicationIdSuffix = ".chemistry"
            buildConfigField("String", "SUBJECT_ID", "\"chemistry\"")
            buildConfigField("String", "APP_TITLE", "\"Химия\"")
            buildConfigField("int", "VARIANT_ID", "4")
        }
        create("geography") {
            dimension = "subject"
            applicationIdSuffix = ".geography"
            buildConfigField("String", "SUBJECT_ID", "\"geography\"")
            buildConfigField("String", "APP_TITLE", "\"География\"")
            buildConfigField("int", "VARIANT_ID", "5")
        }
        create("informatics") {
            dimension = "subject"
            applicationIdSuffix = ".informatics"
            buildConfigField("String", "SUBJECT_ID", "\"informatics\"")
            buildConfigField("String", "APP_TITLE", "\"Информатика\"")
            buildConfigField("int", "VARIANT_ID", "6")
        }
        create("historykaz") {
            dimension = "subject"
            applicationIdSuffix = ".historykaz"
            buildConfigField("String", "SUBJECT_ID", "\"historykaz\"")
            buildConfigField("String", "APP_TITLE", "\"История Казахстана\"")
            buildConfigField("int", "VARIANT_ID", "7")
        }
        create("worldhistory") {
            dimension = "subject"
            applicationIdSuffix = ".worldhistory"
            buildConfigField("String", "SUBJECT_ID", "\"worldhistory\"")
            buildConfigField("String", "APP_TITLE", "\"Всемирная история\"")
            buildConfigField("int", "VARIANT_ID", "8")
        }
        create("kazakhlang") {
            dimension = "subject"
            applicationIdSuffix = ".kazakhlang"
            buildConfigField("String", "SUBJECT_ID", "\"kazakhlang\"")
            buildConfigField("String", "APP_TITLE", "\"Қазақ тілі\"")
            buildConfigField("int", "VARIANT_ID", "9")
        }
        create("russianlang") {
            dimension = "subject"
            applicationIdSuffix = ".russianlang"
            buildConfigField("String", "SUBJECT_ID", "\"russianlang\"")
            buildConfigField("String", "APP_TITLE", "\"Русский язык\"")
            buildConfigField("int", "VARIANT_ID", "10")
        }
        create("englishlang") {
            dimension = "subject"
            applicationIdSuffix = ".englishlang"
            buildConfigField("String", "SUBJECT_ID", "\"englishlang\"")
            buildConfigField("String", "APP_TITLE", "\"Английский язык\"")
            buildConfigField("int", "VARIANT_ID", "11")
        }
        create("music") {
            dimension = "subject"
            applicationIdSuffix = ".music"
            buildConfigField("String", "SUBJECT_ID", "\"music\"")
            buildConfigField("String", "APP_TITLE", "\"Музыка\"")
            // Без активации — лицензионный ключ не запрашивается
            buildConfigField("Boolean", "REQUIRES_ACTIVATION", "false")
        }
        create("grafika") {
            dimension = "subject"
            applicationIdSuffix = ".grafika"
            buildConfigField("String", "SUBJECT_ID", "\"grafika\"")
            buildConfigField("String", "APP_TITLE", "\"Графика и проектирование\"")
            // Без активации — лицензионный ключ не запрашивается
            buildConfigField("Boolean", "REQUIRES_ACTIVATION", "false")
        }
        create("labor_girls") {
            dimension = "subject"
            applicationIdSuffix = ".laborgirls"
            buildConfigField("String", "SUBJECT_ID", "\"labor_girls\"")
            buildConfigField("String", "APP_TITLE", "\"Художественный труд\"")
            // Без активации — лицензионный ключ не запрашивается
            buildConfigField("Boolean", "REQUIRES_ACTIVATION", "false")
        }
        create("nvp") {
            dimension = "subject"
            applicationIdSuffix = ".nvp"
            buildConfigField("String", "SUBJECT_ID", "\"nvp\"")
            buildConfigField("String", "APP_TITLE", "\"Начальная военная подготовка\"")
            // Без активации — лицензионный ключ не запрашивается
            buildConfigField("Boolean", "REQUIRES_ACTIVATION", "false")
        }
        create("labor_boys") {
            dimension = "subject"
            applicationIdSuffix = ".laborboys"
            buildConfigField("String", "SUBJECT_ID", "\"labor_boys\"")
            buildConfigField("String", "APP_TITLE", "\"Художественный труд (мальчики)\"")
            // Без активации — лицензионный ключ не запрашивается
            buildConfigField("Boolean", "REQUIRES_ACTIVATION", "false")
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
        buildConfig = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.webkit:webkit:1.9.0")
    implementation("com.google.android.material:material:1.11.0")
    // Лицензирование v4: проверка подписи Ed25519 (низкоуровневый API BouncyCastle)
    implementation("org.bouncycastle:bcprov-jdk18on:1.77")
    // QR-сканер активации: CameraX + ML Kit (модель штрих-кодов вшита, офлайн)
    implementation("androidx.camera:camera-core:1.3.1")
    implementation("androidx.camera:camera-camera2:1.3.1")
    implementation("androidx.camera:camera-lifecycle:1.3.1")
    implementation("androidx.camera:camera-view:1.3.1")
    implementation("com.google.mlkit:barcode-scanning:17.2.0")
}
