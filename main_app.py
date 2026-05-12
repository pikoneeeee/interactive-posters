# -*- coding: utf-8 -*-
import sys
import os
import json
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile, QWebEngineScript
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, QUrl, Qt, QTimer
from PySide6.QtGui import QIcon

import licensing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONTENT_ROOT = os.path.join(BASE_DIR, 'content')


def _load_app_config():
    """Читает content/app_config.json. Позволяет билд-скрипту настроить поведение:
    {
      "skip_activation": true,      # сразу пропустить окно активации
      "start_subject":  "informatics",  # стартовый предмет (сразу показать его плакаты)
      "window_title":   "..."            # заголовок окна
    }
    """
    default = {"skip_activation": False, "start_subject": None, "window_title": None}
    path = os.path.join(CONTENT_ROOT, 'app_config.json')
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k in default:
            if k in data:
                default[k] = data[k]
    except Exception as e:
        logging.warning(f"Не удалось прочитать app_config.json: {e}")
    return default


APP_CONFIG = _load_app_config()


class Bridge(QObject):
    """Мост между JavaScript и Python для основной навигации"""

    def __init__(self, window):
        super().__init__()
        self.window = window

    @Slot(str)
    def onSubjectSelected(self, subject_id):
        """Пользователь выбрал предмет"""
        print(f"DEBUG: onSubjectSelected({subject_id})")
        self.window.select_subject(subject_id)

    @Slot(str)
    def onTopicClicked(self, topic_id):
        """Пользователь выбрал тему"""
        print(f"DEBUG: onTopicClicked({topic_id})")
        self.window.show_poster_screen(topic_id)

    @Slot()
    def onBackClicked(self):
        """Нажата кнопка 'Назад'"""
        print(f"DEBUG: onBackClicked()")
        self.window.go_back()

    @Slot(str)
    def onLangChanged(self, lang_code):
        """Пользователь переключил язык"""
        print(f"DEBUG: onLangChanged({lang_code})")
        self.window.change_language(lang_code)

    @Slot()
    def onFrontEndReady(self):
        """JavaScript готов получать данные"""
        print(f"DEBUG: onFrontEndReady()")
        self.window.update_content()


class ActivationBridge(QObject):
    """Мост для активации лицензии"""

    def __init__(self, window):
        super().__init__()
        self.window = window

    @Slot(str)
    def activate(self, key):
        """Активировать по ключу"""
        print(f"DEBUG: Активирую ключ: {key}")
        result, message = licensing.activate_key(key)
        msg_escaped = message.replace("'", "\\'").replace('"', '\\"')
        if result:
            self.window.web_view.page().runJavaScript(
                f"if(typeof onActivationSuccess==='function')onActivationSuccess('{msg_escaped}');"
            )
            QTimer.singleShot(1500, self.window.navigate_after_activation)
        else:
            self.window.web_view.page().runJavaScript(
                f"if(typeof onActivationError==='function')onActivationError('{msg_escaped}');"
            )


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_CONFIG.get("window_title") or "Интерактивные плакаты")
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, 'icon.svg')))

        # Переменные состояния
        self.current_lang = 'ru'
        self.ui_lang = 'ru'
        self.current_subject = None
        self.current_topic_id = None
        self.current_screen = 'activation'  # activation, subjects, topics, poster
        self.translations = {}
        self.subjects_structure = {}
        self._in_language_subject = False

        self.current_topic = None
        # Построение UI
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_widget)

        self.web_view = QWebEngineView()

        # === КЭШИРОВАНИЕ ДЛЯ БЫСТРОЙ ЗАГРУЗКИ ===
        profile = QWebEngineProfile.defaultProfile()
        cache_path = os.path.join(BASE_DIR, '.cache')
        profile.setCachePath(cache_path)
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        profile.setHttpCacheMaximumSize(100 * 1024 * 1024)  # 100MB кэш
        # ========================================

        # === 1. СОЗДАЕМ КНОПКУ "НАЗАД" ===
        self._back_btn_labels = {'ru': '← Назад', 'kz': '← Артқа', 'en': '← Back'}
        self.btn_back_overlay = QPushButton(self._back_btn_labels.get('ru', '← Назад'), self.central_widget)
        self.btn_back_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        # Стиль кнопки: полупрозрачная, при наведении становится яркой
        # === Стиль кнопки (яркий, заметный) ===
        # === Стиль кнопки: полупрозрачная, компактная ===
        self.btn_back_overlay.setStyleSheet("""
            QPushButton {
                /* Цвет фона: Синий, прозрачность 0.4 (40%) */
                background-color: rgba(102, 126, 234, 0.4); 
                color: rgba(255, 255, 255, 0.9); /* Текст чуть мягче */
                
                /* Тонкая рамка, чтобы кнопку было видно на белом фоне */
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                
                /* Размер шрифта меньше */
                font-size: 14px; 
                font-weight: bold;
                padding: 4px 10px;
                z-index: 99999;
            }
            QPushButton:hover {
                /* При наведении становится полностью непрозрачной (яркой) */
                background-color: rgba(102, 126, 234, 1.0);
                border: 1px solid white;
                box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            }
        """)
        self.btn_back_overlay.clicked.connect(self.go_back)
        self.btn_back_overlay.hide()  # Скрываем при запуске
        # ================================

        self.layout.addWidget(self.web_view)
        # === Overlay навигация (стрелки поверх плаката) ===
        # === КНОПКИ НАВИГАЦИИ (не перекрывают плакат) ===
        self.nav_left = QWidget(self.central_widget)
        self.nav_right = QWidget(self.central_widget)

        self.nav_left.setStyleSheet("background: transparent;")
        self.nav_right.setStyleSheet("background: transparent;")

        self.btn_prev = QPushButton("←", self.nav_left)
        self.btn_next = QPushButton("→", self.nav_right)

        for b in (self.btn_prev, self.btn_next):
            b.setFixedSize(48, 48)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton{
                    border:none; border-radius:24px;
                    background: rgba(0,0,0,160);
                    color:white; font-size:20px; font-weight:700;
                }
                QPushButton:hover{ background: rgba(0,0,0,210); }
            """)

        self.btn_prev.clicked.connect(self.go_prev_poster)
        self.btn_next.clicked.connect(self.go_next_poster)

        self.nav_left.hide()
        self.nav_right.hide()



        # ВАЖНО: Разрешаем загрузку локальных файлов (для Chart.js и других библиотек)
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        print("✅ Настройки QWebEngine: локальные файлы разрешены")

        # Построение WebChannel
        self.channel = QWebChannel()
        self.web_view.page().setWebChannel(self.channel)

        self.bridge = Bridge(self)
        self.activation_bridge = ActivationBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.channel.registerObject("activationBridge", self.activation_bridge)

        # === ФИКС РЕНДЕРИНГА: подключаем сигнал loadFinished ===
        self.web_view.loadFinished.connect(self._on_page_loaded)

        # === Инъекция скрипта: мгновенная установка языка при создании документа ===
        # Предотвращает мерцание неправильного языка (FOUC)
        lang_script = QWebEngineScript()
        lang_script.setName("instant-lang-switch")
        lang_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        lang_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        lang_script.setRunsOnSubFrames(False)
        lang_script.setSourceCode("""
            (function() {
                var params = new URLSearchParams(window.location.search);
                var lang = params.get('lang');
                if (!lang) return;
                // Маппинг: kz -> kk для CSS-классов плакатов
                var cssLang = (lang === 'kz') ? 'kk' : lang;
                // Ждём DOM
                function applyLang() {
                    var container = document.getElementById('poster-container');
                    if (container) {
                        container.className = container.className.replace(/lang-\w+/g, '');
                        container.classList.add('lang-' + cssLang);
                    }
                    // Скрываем body до полной готовности (Python _on_page_loaded покажет)
                    if (document.body) document.body.style.visibility = 'hidden';
                    // Страховка: показать через 300мс если Python не успеет
                    setTimeout(function() {
                        if (document.body) document.body.style.visibility = 'visible';
                    }, 300);
                }
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', applyLang);
                } else {
                    applyLang();
                }
            })();
        """)
        self.web_view.page().scripts().insert(lang_script)
        # =======================================================

        # Загрузка данных и навигация
        self.load_all_data()
        self.navigate()

    def _on_page_loaded(self, ok):
        """Вызывается после полной загрузки страницы"""
        if not ok:
            return

        if self.current_screen == 'poster':
            # Устанавливаем правильный язык для обоих типов плакатов
            lang_kk = 'kk' if self.current_lang == 'kz' else self.current_lang
            lang_js = f"""
                (function() {{
                    var lang = '{self.current_lang}';
                    var langKK = '{lang_kk}';
                    // Скрываем body до переключения языка (антимерцание)
                    if (document.body) document.body.style.visibility = 'hidden';
                    try {{
                        if (typeof switchLang === 'function') switchLang(langKK);
                    }} catch(e) {{}}
                    try {{
                        if (typeof setLang === 'function') setLang(lang);
                    }} catch(e) {{}}
                    // Показываем после переключения
                    requestAnimationFrame(function() {{
                        requestAnimationFrame(function() {{
                            if (document.body) document.body.style.visibility = 'visible';
                        }});
                    }});
                    // Страховка: если rAF не сработает
                    setTimeout(function() {{
                        if (document.body) document.body.style.visibility = 'visible';
                    }}, 50);
                }})();
            """
            self.web_view.page().runJavaScript(lang_js)

        # Запускаем серию принудительных перерисовок
        self._start_repaint_cycle()

    def _start_repaint_cycle(self):
        """Запускает цикл принудительных перерисовок на 600мс после загрузки.
        Решает баг Windows QWebEngineView где compositor не пушит кадры в Qt."""
        self._repaint_ticks = 0
        if not hasattr(self, '_repaint_timer'):
            self._repaint_timer = QTimer(self)
            self._repaint_timer.timeout.connect(self._tick_repaint)
        self._repaint_timer.start(33)  # ~30fps, каждые 33мс

    def _tick_repaint(self):
        """Один тик принудительной перерисовки."""
        self._repaint_ticks += 1
        if self._repaint_ticks > 18:  # 18 * 33ms ≈ 600ms
            self._repaint_timer.stop()
            return

        # Получаем виджет рендеринга Chromium
        render_widget = self.web_view.focusProxy()
        if render_widget is not None:
            render_widget.update()
            render_widget.repaint()

        # Поднять overlay-кнопки
        if hasattr(self, 'nav_left') and self.nav_left.isVisible():
            self.nav_left.raise_()
        if hasattr(self, 'nav_right') and self.nav_right.isVisible():
            self.nav_right.raise_()
        if hasattr(self, 'btn_back_overlay') and self.btn_back_overlay.isVisible():
            self.btn_back_overlay.raise_()

    def resizeEvent(self, event):
        """Обновляем позиции кнопок при изменении размера окна"""
        super().resizeEvent(event)

        w = self.width()
        h = self.height()

        # 1. Браузер на весь экран
        self.web_view.setGeometry(0, 0, w, h)

        # 2. Стрелки навигации
        btn_y = h // 2 - 24
        if hasattr(self, 'nav_left'):
            self.nav_left.setGeometry(0, 0, 80, h)
            self.nav_left.raise_()
        if hasattr(self, 'nav_right'):
            self.nav_right.setGeometry(w - 80, 0, 80, h)
            self.nav_right.raise_()
        if hasattr(self, 'btn_prev'):
            self.btn_prev.move(16, btn_y)
        if hasattr(self, 'btn_next'):
            self.btn_next.move(16, btn_y)

        # 3. Кнопка «НАЗАД» — ВСЕГДА поверх всего (последний raise)
        if hasattr(self, 'btn_back_overlay'):
            self.btn_back_overlay.setGeometry(12, 12, 120, 40)
            self.btn_back_overlay.raise_()

    def load_all_data(self) -> None:
        """Загружаем структуру предметов и переводы"""
        try:
            # Логирование путей
            print(f"\n{'=' * 80}")
            print(f"🔍 DEBUG ЗАГРУЗКА:")
            print(f"{'=' * 80}")
            print(f"BASE_DIR = {BASE_DIR}")
            print(f"CONTENT_ROOT = {CONTENT_ROOT}")
            print(f"CONTENT_ROOT существует: {os.path.exists(CONTENT_ROOT)}")

            if os.path.exists(CONTENT_ROOT):
                print(f"Содержимое CONTENT_ROOT:")
                for item in os.listdir(CONTENT_ROOT):
                    full_path = os.path.join(CONTENT_ROOT, item)
                    is_dir = os.path.isdir(full_path)
                    print(f"  {'📁' if is_dir else '📄'} {item}")
            print(f"{'=' * 80}\n")

            # Загружаем структуру предметов
            subjects_file = os.path.join(CONTENT_ROOT, 'subjects.json')
            print(f"📄 Путь subjects.json: {subjects_file}")
            print(f"   Существует: {os.path.exists(subjects_file)}")

            if os.path.exists(subjects_file):
                with open(subjects_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Преобразуем список в словарь для удобного доступа
                    if isinstance(data, dict) and 'subjects' in data:
                        self.subjects_structure = {s['id']: s for s in data['subjects']}
                    else:
                        self.subjects_structure = data
                print(f"   ✅ Загружено {len(self.subjects_structure)} предметов")
            else:
                print(f"   ❌ ОШИБКА: subjects.json не найден!")
                logging.error(f"Файл {subjects_file} не найден")

            # Загружаем переводы
            print(f"\n🌐 Загрузка переводов:")
            for lang in ['ru', 'kz', 'en']:
                lang_file = os.path.join(CONTENT_ROOT, 'locales', f'{lang}.json')
                print(f"   Путь {lang}.json: {lang_file}")
                print(f"      Существует: {os.path.exists(lang_file)}")

                if os.path.exists(lang_file):
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        self.translations[lang] = json.load(f)
                    print(f"      ✅ Загружен")
                else:
                    print(f"      ❌ Не найден")
                    logging.warning(f"Файл перевода {lang_file} не найден")

            print(f"\n✅ Загружены переводы: {list(self.translations.keys())}")
            print(f"{'=' * 80}\n")

            logging.info(f"Загружено {len(self.subjects_structure)} предметов")
            logging.info(f"Загружены переводы: {list(self.translations.keys())}")

        except Exception as e:
            print(f"\n❌ CRITICAL ERROR при загрузке данных:")
            print(f"   {e}")
            print(f"{'=' * 80}\n")
            logging.critical(f"Ошибка при загрузке данных: {e}", exc_info=True)


    def navigate(self):
        """Главная навигация: skip_activation / start_subject из APP_CONFIG."""
        print("\n🔄 navigate()")
        skip_act = bool(APP_CONFIG.get("skip_activation"))
        start_subj = APP_CONFIG.get("start_subject")
        if skip_act:
            print("   ⏭ skip_activation=true — пропускаю активацию")
            is_activated = True
        else:
            status = licensing.get_license_status()
            is_activated = status['valid']
            print(f"   Лицензия: valid={is_activated}, reason={status['reason']}")
            if is_activated and status.get('days_left') is not None:
                print(f"   Осталось дней: {status['days_left']}")
        if not is_activated:
            self.show_activation_screen()
            return
        if start_subj and start_subj in self.subjects_structure:
            print(f"   ➜ start_subject={start_subj!r} — сразу к списку плакатов")
            self.current_subject = start_subj
            subj = self.subjects_structure[start_subj]
            if subj.get("is_language_subject", False):
                lang_map = {"kazakhlang": "kz", "russianlang": "ru", "englishlang": "en"}
                self.current_lang = lang_map.get(start_subj, self.current_lang)
            self.show_topics_screen()
        else:
            self.show_subjects_screen()

    def navigate_after_activation(self):
        """Вызывается после успешной активации — обычный поток навигации."""
        self.navigate()


    def show_activation_screen(self):
        """Показываем экран активации"""
        print(f"\n🖥️ show_activation_screen()")
        self.current_screen = 'activation'
        template_path = os.path.join(CONTENT_ROOT, 'templates', 'activation_screen.html')

        print(f"   Путь: {template_path}")
        print(f"   Существует: {os.path.exists(template_path)}")

        if os.path.exists(template_path):
            print(f"   ✅ Загружаю HTML")
            url = QUrl.fromLocalFile(template_path)
            self.web_view.setUrl(url)
        else:
            print(f"   ❌ Файл не найден!")
            self.web_view.setHtml(f"""
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial; padding: 50px; background: #f0f0f0;">
                    <h1>❌ Ошибка</h1>
                    <p>Файл активации не найден:</p>
                    <p><code>{template_path}</code></p>
                    <p>Пожалуйста, проверьте наличие файла: <code>content/templates/activation_screen.html</code></p>
                </body>
                </html>
            """)

    def show_subjects_screen(self):
        """Экран выбора предмета из 11 вариантов"""
        print(f"\n🖥️ show_subjects_screen()")
        self.current_screen = 'subjects'
        template_path = os.path.join(CONTENT_ROOT, 'templates', 'subjects_screen.html')


        if hasattr(self, 'btn_back_overlay'):
            self.btn_back_overlay.hide()

        print(f"   Путь: {template_path}")
        print(f"   Существует: {os.path.exists(template_path)}")

        if os.path.exists(template_path):
            print(f"   ✅ Загружаю HTML")
            url = QUrl.fromLocalFile(template_path)
            self.web_view.setUrl(url)
        else:
            print(f"   ❌ Файл не найден!")
            self.web_view.setHtml(f"""
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial; padding: 50px; background: #f0f0f0;">
                    <h1>❌ Ошибка</h1>
                    <p>Файл subjects_screen не найден:</p>
                    <p><code>{template_path}</code></p>
                </body>
                </html>
            """)

    def show_topics_screen(self):
        """Экран выбора темы внутри предмета"""
        print(f"\n🖥️ show_topics_screen()")
        self.current_screen = 'topics'
        template_path = os.path.join(CONTENT_ROOT, 'templates', 'topics_screen.html')

        print(f"   Путь: {template_path}")
        print(f"   Существует: {os.path.exists(template_path)}")

        if os.path.exists(template_path):
            print(f"   ✅ Загружаю HTML")
            url = QUrl.fromLocalFile(template_path)
            self.web_view.setUrl(url)
        else:
            print(f"   ❌ Файл не найден!")
            self.web_view.setHtml(f"""
                <html>
                <head><meta charset="UTF-8"></head>
                <body style="font-family: Arial; padding: 50px; background: #f0f0f0;">
                    <h1>❌ Ошибка</h1>
                    <p>Файл topics_screen не найден:</p>
                    <p><code>{template_path}</code></p>
                </body>
                </html>
            """)

    def select_subject(self, subject_id):
        """Пользователь выбрал предмет"""
        print(f"\n🎯 select_subject({subject_id})")
        if subject_id in self.subjects_structure:
            print(f"   ✅ Предмет найден")
            self.current_subject = subject_id
            subject = self.subjects_structure[subject_id]

            # Определяем язык для языковых предметов
            if subject.get('is_language_subject', False):
                lang_map = {'kazakhlang': 'kz', 'russianlang': 'ru', 'englishlang': 'en'}
                self._in_language_subject = True
                self.current_lang = lang_map.get(subject_id, 'kz')
                print(f"   🌐 Языковой предмет, язык: {self.current_lang} (ui_lang сохранён: {self.ui_lang})")
                logging.info(
                    f"Выбран языковой предмет: {subject_id}, язык: {self.current_lang}")
            else:
                self._in_language_subject = False

            self.show_topics_screen()
        else:
            print(f"   ❌ Предмет {subject_id} не найден!")
            logging.error(f"Предмет {subject_id} не найден в структуре")

    def update_content(self):
        """Обновляем содержимое текущего экрана"""
        print(f"\n📊 update_content() - текущий экран: {self.current_screen}")
        if self.current_screen == 'subjects':
            self.update_subjects_screen()
        elif self.current_screen == 'topics':
            self.update_topics_screen()

    def update_subjects_screen(self):
        """Отправляем данные всех 11 предметов на экран"""
        print(f"   📚 update_subjects_screen()")
        subjects_data = []

        for subject_id, subject in self.subjects_structure.items():
            subject_name = self._get_translation(subject.get('name_key', subject_id))
            subjects_data.append({
                'id': subject_id,
                'name': subject_name
            })

        subjects_json = json.dumps(subjects_data, ensure_ascii=False)
        js_code = f"""
            window.subjectsData = {subjects_json};
            if (typeof renderSubjects === 'function') {{
                renderSubjects(window.subjectsData);
            }}
        """
        print(f"   ✅ Отправляю {len(subjects_data)} предметов в JavaScript")
        self.web_view.page().runJavaScript(js_code)

    def update_topics_screen(self):
        """Отправляем темы и скроллим к нужной МГНОВЕННО"""
        if not self.current_subject:
            return

        subject = self.subjects_structure.get(self.current_subject)
        if not subject:
            return

        subject_name = self._get_translation(subject.get('name_key', self.current_subject))
        topics_data = []
        for topic in subject.get('topics', []):
            topic_name = topic.get('title_ru') or topic.get('name') or topic['id']
            topic_data = {'id': topic['id'], 'name': topic_name}
            # Добавляем класс если есть
            if 'grade' in topic:
                topic_data['grade'] = topic['grade']
            topics_data.append(topic_data)

        topics_json = json.dumps(topics_data, ensure_ascii=False)
        subject_name_escaped = subject_name.replace("'", "\\'").replace('"', '\\"')
        is_lang_subject = subject.get('is_language_subject', False)

        # !!! ЛОГИКА ПРОКРУТКИ (БЕЗ ЗАДЕРЖКИ) !!!
        scroll_script = ""
        if self.current_topic:
            # Мы убрали setTimeout. Код выполняется сразу после renderTopics.
            # behavior: 'auto' - это мгновенный прыжок, без плавной прокрутки.
            scroll_script = f"""
                var card = document.querySelector('.topic-card[data-topic-id="{self.current_topic}"]');
                if (card) {{
                    console.log('⚡ Instant scroll to:', '{self.current_topic}');

                    // 1. Мгновенно скроллим
                    card.scrollIntoView({{ behavior: 'auto', block: 'center' }});

                    // 2. Визуально выделяем (опционально, можно убрать если раздражает)
                    card.style.transform = 'scale(1.05)';
                    card.style.border = '2px solid #FFD700';
                    card.style.transition = 'transform 0.3s ease';

                    setTimeout(() => {{ 
                        card.style.transform = ''; 
                        card.style.border = '';
                    }}, 1000);
                }}
            """

        js_code = f"""
            document.getElementById('subject-title').innerText = '{subject_name_escaped}';
            window.topicsData = {topics_json};
            window.isLangSubject = {str(is_lang_subject).lower()};

            if (typeof renderTopics === 'function') {{
                renderTopics(window.topicsData);
                {scroll_script}
            }}

            // Скрываем селектор языка для языковых предметов
            var langSel = document.getElementById('lang-selector');
            if (langSel) {{
                langSel.style.display = window.isLangSubject ? 'none' : 'flex';
            }}
        """
        self.web_view.page().runJavaScript(js_code)

    def _get_topics_ids(self):
        """Список topic_id в текущем предмете в порядке subjects.json"""
        subj = self.subjects_structure.get(self.current_subject)
        if not subj:
            return []
        topics = subj.get("topics", [])
        ids = []
        for t in topics:
            if isinstance(t, dict) and "id" in t:
                ids.append(t["id"])
            elif isinstance(t, str):
                ids.append(t)
        return ids

    def go_next_poster(self):
        print(f"\n➡️ go_next_poster() current_topic_id={self.current_topic_id}, current_subject={self.current_subject}")
        ids = self._get_topics_ids()
        print(f"   ids count={len(ids)}")
        if not ids or not self.current_topic_id:
            print(f"   ❌ Empty ids or no current_topic_id")
            return
        try:
            i = ids.index(self.current_topic_id)
        except ValueError:
            print(f"   ❌ current_topic_id '{self.current_topic_id}' not found in ids")
            return
        print(f"   Current index={i}, max={len(ids)-1}")
        if i < len(ids) - 1:
            print(f"   ✅ Navigating to {ids[i + 1]}")
            self.show_poster_screen(ids[i + 1])
        else:
            print(f"   ⚠️ Already at last topic")

    def go_prev_poster(self):
        print(f"\n⬅️ go_prev_poster() current_topic_id={self.current_topic_id}, current_subject={self.current_subject}")
        ids = self._get_topics_ids()
        print(f"   ids count={len(ids)}")
        if not ids or not self.current_topic_id:
            print(f"   ❌ Empty ids or no current_topic_id")
            return
        try:
            i = ids.index(self.current_topic_id)
        except ValueError:
            print(f"   ❌ current_topic_id '{self.current_topic_id}' not found in ids")
            return
        print(f"   Current index={i}")
        if i > 0:
            print(f"   ✅ Navigating to {ids[i - 1]}")
            self.show_poster_screen(ids[i - 1])
        else:
            print(f"   ⚠️ Already at first topic")

    def show_poster_screen(self, topic_id):
        """Показываем плакат выбранной темы"""
        print(f"\n🎨 show_poster_screen({topic_id})")

        # ВАЖНО: Запоминаем текущую тему
        self.current_topic = topic_id

        try:
            if not self.current_subject:
                print(f"   ❌ Предмет не выбран")
                logging.error("Предмет не выбран")
                return

            self.current_topic_id = topic_id

            poster_path = os.path.join(
                CONTENT_ROOT, 'posters', self.current_subject, f"{topic_id}.html"
            )

            if os.path.exists(poster_path):
                print(f"   ✅ Загружаю плакат")
                url = QUrl.fromLocalFile(poster_path)
                url.setQuery(f"lang={self.current_lang}")
                self.current_screen = 'poster'  # Устанавливаем ДО загрузки для loadFinished
                self.web_view.setUrl(url)

                # === 3. ПОКАЗЫВАЕМ КНОПКУ ===
                if hasattr(self, 'btn_back_overlay'):
                    self.btn_back_overlay.setText(self._back_btn_labels.get(self.current_lang, '← Назад'))
                    self.btn_back_overlay.show()
                    self.btn_back_overlay.raise_()
                # ============================

                # Показываем стрелки
                if hasattr(self, 'nav_left'): self.nav_left.show()
                if hasattr(self, 'nav_right'): self.nav_right.show()


                logging.info(
                    f"Открыт плакат: {self.current_subject}/{topic_id} на языке {self.current_lang}"
                )
            else:
                error_msg = f"Плакат не найден: {poster_path}"
                print(f"   ❌ {error_msg}")
                # Скрыть стрелки при ошибке
                if hasattr(self, 'nav_left'): self.nav_left.hide()
                if hasattr(self, 'nav_right'): self.nav_right.hide()

                self.web_view.setHtml(
                    f"<html><body><h1>❌ {error_msg}</h1><button onclick='history.back()'>Назад</button></body></html>")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            logging.error(f"Ошибка при открытии плаката: {e}", exc_info=True)
            if hasattr(self, 'nav_left'): self.nav_left.hide()
            if hasattr(self, 'nav_right'): self.nav_right.hide()

    def go_back(self):
        """Кнопка 'Назад' - возвращаемся на уровень выше"""
        print(f"\n⬅️ go_back() - текущий экран: {self.current_screen}")

        if self.current_screen == 'poster':
            print("   ➜ Возвращаюсь на экран тем")

            # 🔴 СКРЫВАЕМ стрелки навигации
            if hasattr(self, 'nav_left'):
                self.nav_left.hide()
            if hasattr(self, 'nav_right'):
                self.nav_right.hide()

            # === СКРЫВАЕМ КНОПКУ «Назад» ===
            if hasattr(self, 'btn_back_overlay'):
                self.btn_back_overlay.hide()

            self.current_screen = 'topics'
            self.show_topics_screen()

        elif self.current_screen == 'topics':
            # Если приложение запущено в режиме одного предмета (start_subject),
            # экрана выбора предметов нет — ничего не делаем.
            if APP_CONFIG.get("start_subject"):
                print("   ⏹ start_subject задан — остаюсь на экране тем")
                return
            print("   ➜ Возвращаюсь на экран предметов")

            # Восстанавливаем язык интерфейса после языкового предмета
            if self._in_language_subject:
                self.current_lang = self.ui_lang
                self._in_language_subject = False
                print(f"   🌐 Восстановлен ui_lang: {self.ui_lang}")

            self.current_topic = None
            self.current_topic_id = None
            self.current_screen = 'subjects'
            self.show_subjects_screen()

    def change_language(self, lang_code):
        """Пользователь переключил язык"""
        print(f"\n🌐 change_language({lang_code})")
        if lang_code in self.translations:
            self.current_lang = lang_code
            self.ui_lang = lang_code
            print(f"   ✅ Язык изменен на: {lang_code}")
            logging.info(f"Язык изменен на: {lang_code}")
            if hasattr(self, 'btn_back_overlay') and hasattr(self, '_back_btn_labels'):
                self.btn_back_overlay.setText(self._back_btn_labels.get(lang_code, '← Назад'))
            if self.current_screen == 'subjects':
                self.update_subjects_screen()
        else:
            print(f"   ❌ Язык {lang_code} не доступен")
            logging.warning(f"Язык {lang_code} не доступен")

    def _get_translation(self, key):
        """Получить перевод по ключу на текущем языке"""
        lang_data = self.translations.get(self.current_lang, {})

        # Если ключ - словарь (с полем 'name'), берем его
        if isinstance(lang_data.get(key), dict) and 'name' in lang_data[key]:
            return lang_data[key]['name']

        # Иначе берем строку напрямую
        return lang_data.get(key, key)


if __name__ == '__main__':
    import os
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ПРИЛОЖЕНИЯ 'Интерактивные плакаты'")
    print("=" * 80 + "\n")

    # === Атрибуты QtWebEngine: обязательны ДО QApplication ===
    # AA_ShareOpenGLContexts — нужен для корректной работы QWebEngineView
    # с оверлейными виджетами (стрелки, кнопка «Назад»).
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.resize(1280, 800)
    main_window.show()
    sys.exit(app.exec())