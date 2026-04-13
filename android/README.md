# Android — Интерактивные плакаты для DigiTouch

Android-приложение (WebView) для интерактивных досок DigiTouch.  
Каждый предмет собирается в **отдельный APK**.

## Быстрый старт

### 1. Установите Android Studio
Скачайте с https://developer.android.com/studio

### 2. Синхронизируйте контент
```bash
cd android
python sync_content.py
```
Это скопирует все плакаты, переводы и шрифты из `content/` в Android assets.

### 3. Откройте в Android Studio
- File → Open → выберите папку `android/`
- Дождитесь завершения синхронизации Gradle
- Выберите нужный Build Variant (например, `physicsDebug`)
- Нажмите Run

### 4. Сборка APK из командной строки
```bash
# Один предмет:
python build_apks.py physics

# Несколько предметов:
python build_apks.py physics math bio

# Все 11 предметов:
python build_apks.py all

# Debug-сборка:
python build_apks.py --debug physics

# Список предметов:
python build_apks.py --list
```

Готовые APK появятся в папке `dist/`.

### 5. Установка на устройство
```bash
adb install dist/physics-release.apk
```

---

## Добавление новых плакатов

### Шаг 1: Добавьте HTML-файл плаката
Положите файл в `content/posters/<предмет>/<topic_id>.html`

Например: `content/posters/physics/ph_new_topic.html`

### Шаг 2: Обновите subjects.json
Откройте `content/subjects.json` и добавьте новую тему в массив `topics` нужного предмета:

```json
{
  "id": "ph_new_topic",
  "name": "Новая тема",
  "name_key": "p_topic_new",
  "title_ru": "Новая тема по физике"
}
```

### Шаг 3: Синхронизируйте и соберите
```bash
cd android
python sync_content.py physics
python build_apks.py physics
```

Всё! Новый плакат будет в APK.

---

## Добавление нового предмета

### Шаг 1: Создайте папку с плакатами
```
content/posters/newsubject/
    ns_1.html
    ns_2.html
    ...
```

### Шаг 2: Добавьте предмет в subjects.json
```json
{
  "id": "newsubject",
  "name": "newsubject",
  "name_key": "newsubject",
  "topics": [
    { "id": "ns_1", "name": "Topic 1", "title_ru": "Тема 1" },
    { "id": "ns_2", "name": "Topic 2", "title_ru": "Тема 2" }
  ]
}
```

### Шаг 3: Добавьте flavor в Gradle
В `app/build.gradle.kts` добавьте:
```kotlin
create("newsubject") {
    dimension = "subject"
    applicationIdSuffix = ".newsubject"
    buildConfigField("String", "SUBJECT_ID", "\"newsubject\"")
    buildConfigField("String", "APP_TITLE", "\"Новый предмет — Интерактивные плакаты\"")
}
```

### Шаг 4: Обновите sync_content.py
Добавьте `'newsubject'` в список `ALL_SUBJECTS`.

### Шаг 5: Синхронизируйте и соберите
```bash
python sync_content.py newsubject
python build_apks.py newsubject
```

---

## Структура проекта

```
android/
├── app/
│   ├── src/
│   │   ├── main/                          # Общий код
│   │   │   ├── java/kz/digitouch/posters/ # Kotlin код
│   │   │   ├── assets/                    # Общие assets
│   │   │   │   ├── templates/             # HTML экраны навигации
│   │   │   │   ├── locales/               # Переводы
│   │   │   │   ├── fonts/                 # Шрифты
│   │   │   │   ├── libs/                  # JS библиотеки
│   │   │   │   └── subjects.json          # Полный список предметов
│   │   │   └── res/                       # Android ресурсы
│   │   │
│   │   ├── physics/assets/                # Flavor: физика
│   │   │   ├── posters/physics/           # Плакаты физики
│   │   │   └── subjects.json              # Только физика
│   │   ├── mathematics/assets/            # Flavor: математика
│   │   │   └── ...
│   │   └── allsubjects/assets/            # Flavor: все предметы
│   │       └── posters/                   # Все плакаты
│   └── build.gradle.kts                   # Product flavors
│
├── sync_content.py     # Синхронизация контента
├── build_apks.py       # Сборка APK
└── dist/               # Готовые APK
```

## Подпись APK для релиза

1. Создайте keystore:
```bash
keytool -genkey -v -keystore keystore/release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias posters
```

2. Раскомментируйте блок `signingConfigs` в `app/build.gradle.kts` и укажите пароли.

---

## Предметы и алиасы

| Предмет | ID | Алиас |
|---|---|---|
| Физика | physics | phys |
| Математика | mathematics | math |
| Биология | biology | bio |
| Химия | chemistry | chem |
| География | geography | geo |
| Информатика | informatics | inf |
| История Казахстана | historykaz | hist |
| Всемирная история | worldhistory | whist |
| Қазақ тілі | kazakhlang | kz |
| Русский язык | russianlang | ru |
| English | englishlang | en |
