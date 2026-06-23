package kz.digitouch.posters

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.app.AlertDialog
import android.widget.Button
import android.widget.ImageButton
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

/**
 * Главная Activity — полноэкранный WebView с навигацией по плакатам.
 *
 * Навигация: subjects → topics → poster
 * JS-мост: Android.bridge.* (заменяет QWebChannel из PySide6)
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "Posters"
    }

    private lateinit var webView: WebView
    private lateinit var btnBack: Button
    private lateinit var btnDeviceId: Button
    private lateinit var btnPrev: ImageButton
    private lateinit var btnNext: ImageButton

    // Состояние навигации
    private var currentScreen = "subjects"   // activation | subjects | topics | poster
    private var currentSubject: String? = null
    private var currentTopicId: String? = null
    private var currentLang = "ru"
    private var currentTopicForScroll: String? = null

    // Данные
    private var subjectsStructure = mutableMapOf<String, JSONObject>()
    private var translations = mutableMapOf<String, JSONObject>()

    // ID предмета из BuildConfig (для однопредметных сборок)
    private val flavorSubjectId: String by lazy { BuildConfig.SUBJECT_ID }

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
            allowFileAccess = true
            allowContentAccess = true
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
        // лицензия не проверяется и ключ не запрашивается.
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

    /** Навигация после успешной активации (или если уже активирована). */
    private fun navigateAfterActivation() {
        if (flavorSubjectId != "all" && subjectsStructure.containsKey(flavorSubjectId)) {
            currentSubject = flavorSubjectId
            showTopicsScreen()
        } else {
            showSubjectsScreen()
        }
    }

    /** Экран ввода лицензионного ключа. */
    private fun showActivationScreen() {
        Log.d(TAG, "showActivationScreen()")
        currentScreen = "activation"
        btnBack.visibility = View.GONE
        btnPrev.visibility = View.GONE
        btnNext.visibility = View.GONE
        webView.loadUrl("file:///android_asset/templates/activation_screen.html")
    }

    // =====================================================================
    // ЗАГРУЗКА ДАННЫХ
    // =====================================================================

    private fun loadAllData() {
        try {
            // subjects.json
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
        btnBack.visibility = View.GONE
        btnPrev.visibility = View.GONE
        btnNext.visibility = View.GONE

        webView.loadUrl("file:///android_asset/templates/subjects_screen.html")
    }

    private fun showTopicsScreen() {
        Log.d(TAG, "showTopicsScreen() subject=$currentSubject")
        currentScreen = "topics"
        // В однопредметной сборке кнопка "Назад" из тем не нужна
        btnBack.visibility = if (flavorSubjectId == "all") View.VISIBLE else View.GONE
        btnPrev.visibility = View.GONE
        btnNext.visibility = View.GONE

        webView.loadUrl("file:///android_asset/templates/topics_screen.html")
    }

    private fun showPosterScreen(topicId: String) {
        Log.d(TAG, "showPosterScreen($topicId) subject=$currentSubject")
        if (currentSubject == null) return

        currentTopicId = topicId
        currentTopicForScroll = topicId
        currentScreen = "poster"

        val posterPath = "file:///android_asset/posters/$currentSubject/$topicId.html"

        // Проверяем наличие файла
        val exists = try {
            assets.open("posters/$currentSubject/$topicId.html").close()
            true
        } catch (e: IOException) {
            false
        }

        if (exists) {
            webView.loadUrl("$posterPath?lang=$currentLang")
            btnBack.visibility = View.VISIBLE
            btnPrev.visibility = View.VISIBLE
            btnNext.visibility = View.VISIBLE
        } else {
            Log.e(TAG, "Poster not found: posters/$currentSubject/$topicId.html")
            webView.loadData(
                "<html><body><h1>Плакат не найден</h1><p>posters/$currentSubject/$topicId.html</p></body></html>",
                "text/html", "UTF-8"
            )
        }
    }

    private fun goBack() {
        Log.d(TAG, "goBack() screen=$currentScreen")
        when (currentScreen) {
            "poster" -> {
                currentScreen = "topics"
                btnPrev.visibility = View.GONE
                btnNext.visibility = View.GONE
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
            // Для однопредметных сборок: показываем только свой предмет
            // (На самом деле в однопредметных сборках экран предметов не показывается,
            //  но на всякий случай фильтруем)
            if (flavorSubjectId != "all" && id != flavorSubjectId) continue

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
    // УТИЛИТЫ
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
     * Отключает тяжёлые эффекты: backdrop-filter, box-shadow, canvas shadowBlur,
     * сложные transitions и hover-анимации.
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
                var origArc = CanvasRenderingContext2D.prototype.arc;
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
                if (flavorSubjectId == "all") goBack()
                else super.onBackPressed()
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
         * Вызывается с экрана активации. Проверяет ключ через [Licensing.activateKey],
         * сохраняет лицензию и переходит к плакатам.
         */
        @JavascriptInterface
        fun activateKey(key: String) {
            Log.d(TAG, "JS → activateKey(${key.take(4)}…)")
            // В однопредметной сборке принимаем только ключи для своего предмета.
            // В сборке "all" — любой валидный ключ.
            val expected = if (flavorSubjectId == "all") null else flavorSubjectId
            val (ok, message) = Licensing.activateKey(this@MainActivity, key, expected)
            val esc = message.replace("\\", "\\\\").replace("'", "\\'").replace("\"", "\\\"")
            runOnUiThread {
                if (ok) {
                    webView.evaluateJavascript(
                        "if(typeof onActivationSuccess==='function')onActivationSuccess('$esc');",
                        null
                    )
                    // Небольшая задержка, чтобы пользователь увидел сообщение
                    webView.postDelayed({ navigateAfterActivation() }, 1500)
                } else {
                    webView.evaluateJavascript(
                        "if(typeof onActivationError==='function')onActivationError('$esc');",
                        null
                    )
                }
            }
        }
    }
}
