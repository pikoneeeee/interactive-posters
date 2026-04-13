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
        versionCode = 1
        versionName = "1.0.0"
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
            // Полная версия со всеми предметами
            buildConfigField("String", "SUBJECT_ID", "\"all\"")
            buildConfigField("String", "APP_TITLE", "\"Интерактивные плакаты\"")
        }
        create("physics") {
            dimension = "subject"
            applicationIdSuffix = ".physics"
            buildConfigField("String", "SUBJECT_ID", "\"physics\"")
            buildConfigField("String", "APP_TITLE", "\"Физика — Интерактивные плакаты\"")
        }
        create("mathematics") {
            dimension = "subject"
            applicationIdSuffix = ".mathematics"
            buildConfigField("String", "SUBJECT_ID", "\"mathematics\"")
            buildConfigField("String", "APP_TITLE", "\"Математика — Интерактивные плакаты\"")
        }
        create("biology") {
            dimension = "subject"
            applicationIdSuffix = ".biology"
            buildConfigField("String", "SUBJECT_ID", "\"biology\"")
            buildConfigField("String", "APP_TITLE", "\"Биология — Интерактивные плакаты\"")
        }
        create("chemistry") {
            dimension = "subject"
            applicationIdSuffix = ".chemistry"
            buildConfigField("String", "SUBJECT_ID", "\"chemistry\"")
            buildConfigField("String", "APP_TITLE", "\"Химия — Интерактивные плакаты\"")
        }
        create("geography") {
            dimension = "subject"
            applicationIdSuffix = ".geography"
            buildConfigField("String", "SUBJECT_ID", "\"geography\"")
            buildConfigField("String", "APP_TITLE", "\"География — Интерактивные плакаты\"")
        }
        create("informatics") {
            dimension = "subject"
            applicationIdSuffix = ".informatics"
            buildConfigField("String", "SUBJECT_ID", "\"informatics\"")
            buildConfigField("String", "APP_TITLE", "\"Информатика — Интерактивные плакаты\"")
        }
        create("historykaz") {
            dimension = "subject"
            applicationIdSuffix = ".historykaz"
            buildConfigField("String", "SUBJECT_ID", "\"historykaz\"")
            buildConfigField("String", "APP_TITLE", "\"История Казахстана — Интерактивные плакаты\"")
        }
        create("worldhistory") {
            dimension = "subject"
            applicationIdSuffix = ".worldhistory"
            buildConfigField("String", "SUBJECT_ID", "\"worldhistory\"")
            buildConfigField("String", "APP_TITLE", "\"Всемирная история — Интерактивные плакаты\"")
        }
        create("kazakhlang") {
            dimension = "subject"
            applicationIdSuffix = ".kazakhlang"
            buildConfigField("String", "SUBJECT_ID", "\"kazakhlang\"")
            buildConfigField("String", "APP_TITLE", "\"Қазақ тілі — Интерактивные плакаты\"")
        }
        create("russianlang") {
            dimension = "subject"
            applicationIdSuffix = ".russianlang"
            buildConfigField("String", "SUBJECT_ID", "\"russianlang\"")
            buildConfigField("String", "APP_TITLE", "\"Русский язык — Интерактивные плакаты\"")
        }
        create("englishlang") {
            dimension = "subject"
            applicationIdSuffix = ".englishlang"
            buildConfigField("String", "SUBJECT_ID", "\"englishlang\"")
            buildConfigField("String", "APP_TITLE", "\"English — Интерактивные плакаты\"")
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
}
