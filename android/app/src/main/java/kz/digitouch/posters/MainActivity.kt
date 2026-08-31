package kz.digitouch.posters

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.app.AlertDialog
import android.widget.Button
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.FileNotFoundException
import java.io.IOException

/**
 * Главная Activity — полноэкранный WebView с навигацией по плакатам.
 *
 * Навигация: subjects → topics → poster
 * JS-мост: Android.* (заменяет QWebChannel из PySide6)
 *
 * Защита (новое ядро v4): контент предметов в assets ЗАШИФРОВАН (OLENC2/AES-GCM) и
 * отдаётся через WebViewAssetLoader с расшифровкой В ПАМЯТИ ключом из активной
 * лицензии — в распакованном APK исходных плакатов нет. Активация — лицензией v4
 * (Ed25519) по QR-коду или строкой OL1-…; вариант лицензии = предмет (см. VARIANT_ID).
 * Бесплатные предметы (REQUIRES_ACTIVATION=false) не шифруются и отдаются как есть.
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "Posters"
        private const val DOMAIN = "appassets.androidplatform.net"
    }

    private lateinit var webView: WebView
    private lateinit var btnBack: Button
    private lateinit var btnDeviceId: Button
    private lateinit var btnPrev: ImageButton
    private lateinit var btnNext: ImageButton
    private lateinit var headerBar: LinearLayout
    private lateinit var tvTitle: TextView

    // Состояние навигации
    private var currentScreen = "subjects"   // activation | subjects | topics | poster
    private var currentSubject: String? = null
    private var currentTopicId: String? = null
    private var currentLang = "ru"
    private var currentTopicForScroll: String? = null

    // Данные
    private var subjectsStructure = mutableMapOf<String, JSONObject>()
    private var translations = mutableMapOf<String, JSONObject>()

    // Предметы сборки из BuildConfig. SUBJECT_ID = "all" (все предметы),
    // один предмет ("physics") или несколько через запятую ("historykaz,worldhistory").
    private val flavorSubjectId: String by lazy { BuildConfig.SUBJECT_ID }
    private val isAllSubjects: Boolean by lazy { flavorSubjectId == "all" }
    private val flavorSubjects: List<String> by lazy {
        flavorSubjectId.split(",").map { it.trim() }.filter { it.isNotEmpty() }
    }
    /** true — если в сборке ровно один предмет: экран тем сразу домашний. */
    private val isSingleSubject: Boolean by lazy { !isAllSubjects && flavorSubjects.size == 1 }

    // ── QR-сканер лицензии + разрешение камеры ──────────────────────
    private val scanLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { res ->
        if (res.resultCode == RESULT_OK) {
            val text = res.data?.getStringExtra("qr")
            if (text != null) activateWith(text)
        }
    }
    private val cameraPermLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        // Без разрешения камера не нужна для «QR из файла» и ручного ввода —
        // открываем сканер в режиме no_camera, а не глухую ошибку.
        if (granted) launchScan() else launchScan(noCamera = true)
    }
    private fun launchScan(noCamera: Boolean = false) {
        scanLauncher.launch(Intent(this, QrScanActivity::class.java)
            .putExtra(QrScanActivity.EXTRA_NO_CAMERA, noCamera))
    }

    /** Активация лицензией v4 (из QR или строки). При успехе — переход к плакатам.
     *  Проверку соответствия предмета (variant) делает сам Licensing по BuildConfig.VARIANT_ID. */
    private fun activateWith(key: String) {
        val (ok, message) = Licensing.activateLicense(this, key)
        val esc = message.replace("\\", "\\\\").replace("'", "\\'").replace("\"", "\\\"")
        runOnUiThread {
            if (ok) {
                webView.evaluateJavascript("if(typeof onActivationSuccess==='function')onActivationSuccess('$esc');", null)
                webView.postDelayed({ navigateAfterActivation() }, 1500)
            } else {
                webView.evaluateJavascript("if(typeof onActivationError==='function')onActivationError('$esc');", null)
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Полноэкранный режим
        window.setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        )
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        // ── Защита от скриншотов / записи экрана / кастинга ──────────
        // FLAG_SECURE блокирует на уровне SurfaceFlinger. Без root обойти невозможно.
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)

        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        btnBack = findViewById(R.id.btnBack)
        btnDeviceId = findViewById(R.id.btnDeviceId)
        btnPrev = findViewById(R.id.btnPrev)
        btnNext = findViewById(R.id.btnNext)
        headerBar = findViewById(R.id.headerBar)
        tvTitle = findViewById(R.id.tvTitle)

        // ── Лицензирование v4: публичный ключ + product_id из product_config.json,
        //    вариант (предмет) — из BuildConfig.VARIANT_ID ──
        val cfg = loadConfig()
        val pub = cfg.optJSONArray("public_key")
        val productId = cfg.optInt("product_id", 1)
        // Встроенный ключ контента есть только в запасных сборках (--legacy20):
        // по нему принимается короткий ключ из 20 символов. Лежит в assets
        // не открыто, а как XOR двух массивов.
        var embeddedKey: ByteArray? = null
        val ckMask = cfg.optJSONArray("ck_mask")
        val ckData = cfg.optJSONArray("ck_data")
        if (ckMask != null && ckData != null && ckMask.length() == 32 && ckData.length() == 32) {
            embeddedKey = ByteArray(32) { ((ckMask.getInt(it) xor ckData.getInt(it)) and 0xFF).toByte() }
        }
        Licensing.init(
            if (pub != null) IntArray(pub.length()) { pub.getInt(it) } else IntArray(0),
            productId, BuildConfig.VARIANT_ID, embeddedKey
        )

        btnDeviceId.setOnClickListener {
            val deviceId = Licensing.getDeviceId(this)
            AlertDialog.Builder(this)
                .setTitle("Device ID")
                .setMessage("ID этого устройства:\n\n$deviceId\n\nСообщите этот ID для получения лицензионного ключа.")
                .setPositiveButton("OK", null)
                .show()
        }

        // Настройка WebView — оптимизация для слабых досок DigiTouch
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            setSupportZoom(true)
            builtInZoomControls = true
            displayZoomControls = false
            loadWithOverviewMode = true
            useWideViewPort = true
            // Производительность
            cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            setRenderPriority(android.webkit.WebSettings.RenderPriority.HIGH)
            mediaPlaybackRequiresUserGesture = false
        }

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                val url = request?.url ?: return null
                if (url.host != DOMAIN) return null
                val path = (url.path ?: "").trimStart('/')
                return serveAsset(path)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                Log.d(TAG, "Page loaded: $url")
                injectAntiCopy()
                if (currentScreen == "activation") {
                    val deviceId = Licensing.getDeviceId(this@MainActivity)
                    view?.evaluateJavascript(
                        "document.getElementById('deviceId').textContent='$deviceId';", null
                    )
                }
                if (currentScreen == "poster") {
                    injectPerformanceFixes()
                } else if (currentScreen == "topics" || currentScreen == "subjects") {
                    injectTopicsPerformanceFixes()
                }
            }
        }
        // Отключаем long-press контекстное меню (копировать/вставить)
        webView.setOnLongClickListener { true }
        webView.isLongClickable = false
        webView.isHapticFeedbackEnabled = false

        // JS-мост: из HTML вызывается Android.onSubjectSelected("physics") и т.д.
        webView.addJavascriptInterface(JsBridge(), "Android")

        // Кнопки навигации
        btnBack.setOnClickListener { goBack() }
        btnPrev.setOnClickListener { goPrevPoster() }
        btnNext.setOnClickListener { goNextPoster() }

        // Загрузка данных
        loadAllData()

        // ── Gate активации ────────────────────────────────────────
        // Для сборок с REQUIRES_ACTIVATION=false (напр. music, grafika)
        // лицензия не проверяется и ключ не запрашивается (контент не шифруется).
        if (BuildConfig.REQUIRES_ACTIVATION) {
            val status = Licensing.getLicenseStatus(this)
            if (!status.valid) {
                Log.i(TAG, "Лицензия не активирована: ${status.reason}")
                showActivationScreen()
                return
            }
            Log.i(TAG, "Лицензия активна, осталось дней: ${status.daysLeft}")
        } else {
            Log.i(TAG, "Активация отключена для этой сборки (REQUIRES_ACTIVATION=false)")
        }

        navigateAfterActivation()
    }

    /** product_config.json (public_key, product_id) — встраивается при сборке (sync_content.py). */
    private fun loadConfig(): JSONObject = try {
        JSONObject(assets.open("product_config.json").bufferedReader().use { it.readText() })
    } catch (e: Exception) {
        Log.w(TAG, "нет product_config.json — активация работать не будет")
        JSONObject()
    }

    private fun assetUrl(path: String): String = "https://$DOMAIN/$path"

    /** Навигация после успешной активации (или если уже активирована). */
    private fun navigateAfterActivation() {
        if (isSingleSubject && subjectsStructure.containsKey(flavorSubjects[0])) {
            currentSubject = flavorSubjects[0]
            showTopicsScreen()
        } else {
            showSubjectsScreen()
        }
    }

    /** Экран ввода лицензионного ключа. */
    private fun showActivationScreen() {
        Log.d(TAG, "showActivationScreen()")
        currentScreen = "activation"
        headerBar.visibility = View.VISIBLE
        btnBack.visibility = View.GONE
        btnPrev.visibility = View.GONE
        btnNext.visibility = View.GONE
        tvTitle.text = ""
        // ID устройства нужен только здесь — для получения ключа
        btnDeviceId.visibility = View.VISIBLE
        webView.loadUrl(assetUrl("templates/activation_screen.html"))
    }

    // =====================================================================
    // ЗАГРУЗКА ДАННЫХ
    // =====================================================================

    private fun loadAllData() {
        try {
            // subjects.json (метаданные — не шифруются)
            val subjectsJson = loadAssetText("subjects.json")
            if (subjectsJson != null) {
                val root = JSONObject(subjectsJson)
                val arr = root.getJSONArray("subjects")
                for (i in 0 until arr.length()) {
                    val subj = arr.getJSONObject(i)
                    subjectsStructure[subj.getString("id")] = subj
                }
                Log.i(TAG, "Loaded ${subjectsStructure.size} subjects")
            }

            // Переводы
            for (lang in listOf("ru", "kz", "en")) {
                val text = loadAssetText("locales/$lang.json")
                if (text != null) {
                    translations[lang] = JSONObject(text)
                    Log.i(TAG, "Loaded translation: $lang")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error loading data", e)
        }
    }

    private fun loadAssetText(path: String): String? {
        return try {
            assets.open(path).bufferedReader().use { it.readText() }
        } catch (e: IOException) {
            Log.w(TAG, "Asset not found: $path")
            null
        }
    }

    // =====================================================================
    // НАВИГАЦИЯ
    // =====================================================================

    private fun showSubjectsScreen() {
        Log.d(TAG, "showSubjectsScreen()")
        currentScreen = "subjects"
        headerBar.visibility = View.GONE

        webView.loadUrl(assetUrl("templates/subjects_screen.html"))
    }

    private fun showTopicsScreen() {
        Log.d(TAG, "showTopicsScreen() subject=$currentSubject")
        currentScreen = "topics"
        // «Назад» на экране тем рисует HTML-шаблон (← Назад). Нативную кнопку прячем,
        // иначе на сборке allsubjects кнопок «Назад» было две (нативная каз. + HTML рус.).
        headerBar.visibility = View.GONE

        webView.loadUrl(assetUrl("templates/topics_screen.html"))
    }

    private fun showPosterScreen(topicId: String) {
        Log.d(TAG, "showPosterScreen($topicId) subject=$currentSubject")
        if (currentSubject == null) return

        currentTopicId = topicId
        currentTopicForScroll = topicId
        currentScreen = "poster"

        // Проверяем наличие файла (читаем сырые — возможно зашифрованные — байты)
        val assetRel = "posters/$currentSubject/$topicId.html"
        val exists = try {
            assets.open(assetRel).close()
            true
        } catch (e: IOException) {
            false
        }

        if (exists) {
            webView.loadUrl(assetUrl("$assetRel?lang=$currentLang"))
            headerBar.visibility = View.VISIBLE
            btnBack.visibility = View.VISIBLE
            btnPrev.visibility = View.VISIBLE
            btnNext.visibility = View.VISIBLE
            btnDeviceId.visibility = View.GONE
            tvTitle.text = topicTitle(topicId)
        } else {
            Log.e(TAG, "Poster not found: $assetRel")
            webView.loadData(
                "<html><body><h1>Плакат не найден</h1><p>$assetRel</p></body></html>",
                "text/html", "UTF-8"
            )
        }
    }

    private fun goBack() {
        Log.d(TAG, "goBack() screen=$currentScreen")
        when (currentScreen) {
            "poster" -> {
                currentScreen = "topics"
                showTopicsScreen()
            }
            "topics" -> {
                currentTopicForScroll = null
                currentTopicId = null
                showSubjectsScreen()
            }
        }
    }

    private fun selectSubject(subjectId: String) {
        Log.d(TAG, "selectSubject($subjectId)")
        if (subjectsStructure.containsKey(subjectId)) {
            currentSubject = subjectId

            val subj = subjectsStructure[subjectId]!!
            if (subj.optBoolean("is_language_subject", false)) {
                currentLang = when (subjectId) {
                    "kazakhlang" -> "kz"
                    "russianlang" -> "ru"
                    "englishlang" -> "en"
                    else -> "kz"
                }
            }
            showTopicsScreen()
        }
    }

    private fun changeLanguage(langCode: String) {
        if (translations.containsKey(langCode)) {
            currentLang = langCode
            Log.d(TAG, "Language changed to: $langCode")
        }
    }

    // =====================================================================
    // СТРЕЛКИ НАВИГАЦИИ (пред./след. плакат)
    // =====================================================================

    /** Название темы для хедера: title_ru, иначе name. */
    private fun topicTitle(topicId: String): String {
        val subj = subjectsStructure[currentSubject] ?: return ""
        val topics = subj.optJSONArray("topics") ?: return ""
        for (i in 0 until topics.length()) {
            val tp = topics.getJSONObject(i)
            if (tp.getString("id") == topicId) {
                val ru = tp.optString("title_ru", "")
                return if (ru.isNotEmpty()) ru else tp.optString("name", "")
            }
        }
        return ""
    }

    private fun getTopicIds(): List<String> {
        val subj = subjectsStructure[currentSubject] ?: return emptyList()
        val topics = subj.optJSONArray("topics") ?: return emptyList()
        return (0 until topics.length()).map { topics.getJSONObject(it).getString("id") }
    }

    private fun goNextPoster() {
        val ids = getTopicIds()
        val idx = ids.indexOf(currentTopicId)
        if (idx >= 0 && idx < ids.size - 1) {
            showPosterScreen(ids[idx + 1])
        }
    }

    private fun goPrevPoster() {
        val ids = getTopicIds()
        val idx = ids.indexOf(currentTopicId)
        if (idx > 0) {
            showPosterScreen(ids[idx - 1])
        }
    }

    // =====================================================================
    // ОБНОВЛЕНИЕ КОНТЕНТА (вызывается после загрузки HTML)
    // =====================================================================

    private fun updateContent() {
        Log.d(TAG, "updateContent() screen=$currentScreen")
        when (currentScreen) {
            "subjects" -> updateSubjectsScreen()
            "topics" -> updateTopicsScreen()
        }
    }

    private fun updateSubjectsScreen() {
        val arr = JSONArray()
        for ((id, subj) in subjectsStructure) {
            // Предметные сборки: показываем только предметы этой сборки
            if (!isAllSubjects && id !in flavorSubjects) continue

            val item = JSONObject()
            item.put("id", id)
            item.put("name", getTranslation(subj.optString("name_key", id)))
            arr.put(item)
        }

        val js = """
            window.subjectsData = $arr;
            if (typeof renderSubjects === 'function') {
                renderSubjects(window.subjectsData);
            }
        """.trimIndent()
        runOnUiThread { webView.evaluateJavascript(js, null) }
    }

    private fun updateTopicsScreen() {
        val subj = subjectsStructure[currentSubject] ?: return
        val subjectName = getTranslation(subj.optString("name_key", currentSubject!!))
        val topics = subj.optJSONArray("topics") ?: return

        val topicsArr = JSONArray()
        for (i in 0 until topics.length()) {
            val t = topics.getJSONObject(i)
            val item = JSONObject()
            item.put("id", t.getString("id"))
            item.put("name", t.optString("title_ru", t.optString("name", t.getString("id"))))
            if (t.has("grade")) item.put("grade", t.get("grade"))
            topicsArr.put(item)
        }

        val isLang = subj.optBoolean("is_language_subject", false)
        val nameEscaped = subjectName.replace("'", "\\'").replace("\"", "\\\"")
        // Однопредметная сборка: экран тем — домашний, HTML-кнопка «Назад» не нужна.
        // Если предметов несколько — назад ведёт к выбору предмета.
        val backDisplay = if (isSingleSubject) "none" else ""

        // Скролл к текущей теме при возврате из плаката
        val scrollScript = if (currentTopicForScroll != null) {
            """
            var card = document.querySelector('.topic-card[data-topic-id="${currentTopicForScroll}"]');
            if (card) {
                card.scrollIntoView({ behavior: 'auto', block: 'center' });
                card.style.transform = 'scale(1.05)';
                card.style.border = '2px solid #FFD700';
                card.style.transition = 'transform 0.3s ease';
                setTimeout(function() { card.style.transform = ''; card.style.border = ''; }, 1000);
            }
            """.trimIndent()
        } else ""

        val js = """
            document.getElementById('subject-title').innerText = '$nameEscaped';
            window.topicsData = $topicsArr;
            window.isLangSubject = $isLang;
            if (typeof renderTopics === 'function') {
                renderTopics(window.topicsData);
                $scrollScript
            }
            var backBtn = document.getElementById('back-btn');
            if (backBtn) { backBtn.style.display = '$backDisplay'; }
            var langSel = document.getElementById('lang-selector');
            if (langSel) {
                langSel.style.display = $isLang ? 'none' : 'flex';
            }
        """.trimIndent()

        runOnUiThread { webView.evaluateJavascript(js, null) }
    }

    // =====================================================================
    // ПЕРЕВОД
    // =====================================================================

    private fun getTranslation(key: String): String {
        val langData = translations[currentLang] ?: return key
        if (langData.has(key)) {
            val v = langData.get(key)
            if (v is JSONObject && v.has("name")) return v.getString("name")
            if (v is String) return v
        }
        return key
    }

    // =====================================================================
    // ОТДАЧА ASSETS С РАСШИФРОВКОЙ В ПАМЯТИ
    // =====================================================================

    /**
     * Отдаёт файл из assets по https://DOMAIN/<path>. Зашифрованные файлы (маркер OLENC2)
     * расшифровываются ключом активной лицензии; без ключа — 403 (контент закрыт).
     * Обычные файлы (templates, libs, fonts, locales) отдаются как есть.
     */
    private fun serveAsset(path: String): WebResourceResponse? {
        if (path.isEmpty()) return null
        return try {
            val raw = assets.open(path).use { it.readBytes() }
            val data = Licensing.decryptContent(raw)
                ?: return WebResourceResponse("text/plain", "UTF-8", 403, "Locked",
                    emptyMap(), ByteArrayInputStream(ByteArray(0)))
            val mime = mimeFor(path)
            WebResourceResponse(mime, if (isText(mime)) "UTF-8" else null, ByteArrayInputStream(data))
        } catch (e: FileNotFoundException) {
            null
        } catch (e: Exception) {
            Log.e(TAG, "ошибка отдачи $path", e); null
        }
    }

    private fun mimeFor(path: String): String = when (path.substringBefore('?').substringAfterLast('.', "").lowercase()) {
        "html", "htm" -> "text/html"; "js", "mjs" -> "application/javascript"; "css" -> "text/css"
        "json", "map" -> "application/json"; "svg" -> "image/svg+xml"; "png" -> "image/png"
        "jpg", "jpeg" -> "image/jpeg"; "gif" -> "image/gif"; "webp" -> "image/webp"; "ico" -> "image/x-icon"
        "woff" -> "font/woff"; "woff2" -> "font/woff2"; "ttf" -> "font/ttf"; "otf" -> "font/otf"
        "glb" -> "model/gltf-binary"; "gltf" -> "model/gltf+json"; "wasm" -> "application/wasm"
        "mp3" -> "audio/mpeg"; "wav" -> "audio/wav"; "ogg" -> "audio/ogg"; "mp4" -> "video/mp4"
        else -> "application/octet-stream"
    }
    private fun isText(m: String) =
        m.startsWith("text/") || m == "application/javascript" || m == "application/json" || m == "image/svg+xml"

    // =====================================================================
    // УТИЛИТЫ (анти-копирование и производительность)
    // =====================================================================

    /**
     * Блокирует выделение текста, копирование, контекстное меню, перетаскивание.
     * Инъецируется на каждой странице.
     */
    private fun injectAntiCopy() {
        val js = """
            (function() {
                var style = document.createElement('style');
                style.textContent = `
                    * {
                        -webkit-user-select: none !important;
                        -moz-user-select: none !important;
                        -ms-user-select: none !important;
                        user-select: none !important;
                        -webkit-touch-callout: none !important;
                    }
                    ::selection { background: transparent !important; }
                    ::-moz-selection { background: transparent !important; }
                    input, textarea {
                        -webkit-user-select: text !important;
                        user-select: text !important;
                    }
                `;
                document.head.appendChild(style);
                document.addEventListener('copy', function(e){ e.preventDefault(); }, true);
                document.addEventListener('cut', function(e){ e.preventDefault(); }, true);
                document.addEventListener('selectstart', function(e){
                    if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA') return;
                    e.preventDefault();
                }, true);
                document.addEventListener('contextmenu', function(e){ e.preventDefault(); }, true);
                document.addEventListener('dragstart', function(e){ e.preventDefault(); }, true);
            })();
        """.trimIndent()
        webView.evaluateJavascript(js, null)
    }

    /**
     * Оптимизация CSS для экрана тем/предметов — убираем backdrop-filter и тяжёлые hover.
     */
    private fun injectTopicsPerformanceFixes() {
        val js = """
            (function() {
                var style = document.createElement('style');
                style.textContent = `
                    * {
                        -webkit-backdrop-filter: none !important;
                        backdrop-filter: none !important;
                    }
                    .topic-card {
                        backdrop-filter: none !important;
                        -webkit-backdrop-filter: none !important;
                        transition: background 0.1s ease !important;
                    }
                    .topic-card:hover {
                        transform: none !important;
                        box-shadow: none !important;
                    }
                    .grade-header {
                        backdrop-filter: none !important;
                        -webkit-backdrop-filter: none !important;
                    }
                    .search-wrap {
                        backdrop-filter: none !important;
                        -webkit-backdrop-filter: none !important;
                    }
                    .scroll-to-top {
                        backdrop-filter: none !important;
                        -webkit-backdrop-filter: none !important;
                    }
                `;
                document.head.appendChild(style);
            })();
        """.trimIndent()
        webView.evaluateJavascript(js, null)
    }

    /**
     * Инъекция CSS/JS оптимизаций для слабых устройств DigiTouch.
     */
    private fun injectPerformanceFixes() {
        val css = """
            (function() {
                var style = document.createElement('style');
                style.textContent = `
                    /* === DigiTouch performance fixes === */
                    * {
                        -webkit-backdrop-filter: none !important;
                        backdrop-filter: none !important;
                    }
                    .glass {
                        background: rgba(30, 30, 60, 0.85) !important;
                        -webkit-backdrop-filter: none !important;
                        backdrop-filter: none !important;
                        box-shadow: none !important;
                    }
                    * {
                        transition-duration: 0.05s !important;
                    }
                    *:hover {
                        transform: none !important;
                    }
                `;
                document.head.appendChild(style);

                // Отключаем shadowBlur на всех canvas
                var origFill = CanvasRenderingContext2D.prototype.fill;
                var _fillHook = function() {
                    this.shadowBlur = 0;
                    this.shadowColor = 'transparent';
                    return origFill.apply(this, arguments);
                };
                CanvasRenderingContext2D.prototype.fill = _fillHook;

                // Устанавливаем правильный язык для обоих типов плакатов
                var lang = '$currentLang';
                var langKK = (lang === 'kz') ? 'kk' : lang;
                if (typeof switchLang === 'function') {
                    switchLang(langKK);
                }
                if (typeof setLang === 'function') {
                    setLang(lang);
                }
            })();
        """.trimIndent()
        webView.evaluateJavascript(css, null)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        when (currentScreen) {
            "poster" -> goBack()
            "topics" -> {
                if (isSingleSubject) super.onBackPressed()
                else goBack()
            }
            else -> super.onBackPressed()
        }
    }

    // =====================================================================
    // JS-МОСТ: вызывается из JavaScript через Android.*
    // =====================================================================

    inner class JsBridge {

        @JavascriptInterface
        fun onSubjectSelected(subjectId: String) {
            Log.d(TAG, "JS → onSubjectSelected($subjectId)")
            runOnUiThread { selectSubject(subjectId) }
        }

        @JavascriptInterface
        fun onTopicClicked(topicId: String) {
            Log.d(TAG, "JS → onTopicClicked($topicId)")
            runOnUiThread { showPosterScreen(topicId) }
        }

        @JavascriptInterface
        fun onBackClicked() {
            Log.d(TAG, "JS → onBackClicked()")
            runOnUiThread { goBack() }
        }

        @JavascriptInterface
        fun onLangChanged(langCode: String) {
            Log.d(TAG, "JS → onLangChanged($langCode)")
            runOnUiThread { changeLanguage(langCode) }
        }

        @JavascriptInterface
        fun onFrontEndReady() {
            Log.d(TAG, "JS → onFrontEndReady()")
            runOnUiThread { updateContent() }
        }

        /**
         * Вызывается с экрана активации (кнопка «Активировать» / ввод ключа OL1-…).
         * Активирует лицензию v4 и переходит к плакатам.
         */
        @JavascriptInterface
        fun activateKey(key: String) {
            Log.d(TAG, "JS → activateKey(${key.take(4)}…)")
            runOnUiThread { activateWith(key) }
        }

        /** Вызывается кнопкой «Сканировать QR-код»: запрос камеры → сканер. */
        @JavascriptInterface
        fun scanQr() {
            runOnUiThread {
                if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) launchScan()
                else cameraPermLauncher.launch(Manifest.permission.CAMERA)
            }
        }
    }
}
