# -*- coding: utf-8 -*-
import sys
import os
import json
import logging
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, QUrl, Qt
from PySide6.QtGui import QIcon

import licensing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONTENT_ROOT = os.path.join(BASE_DIR, 'content')


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
        if result:
            self.window.web_view.page().runJavaScript(
                "alert('Активация успешна! Приложение перезагружается.');",
                lambda: self.window.navigate_after_activation()
            )
        else:
            self.window.web_view.page().runJavaScript(f"alert('Ошибка активации: {message}');")


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Интерактивные плакаты")
        self.setWindowIcon(QIcon(os.path.join(BASE_DIR, 'icon.svg')))

        # Переменные состояния
        self.current_lang = 'ru'
        self.current_subject = None
        self.current_topic_id = None
        self.current_screen = 'activation'  # activation, subjects, topics, poster
        self.translations = {}
        self.subjects_structure = {}

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
        self.btn_back_overlay = QPushButton("← Артқа", self.central_widget)
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
        # =======================================================

        # Загрузка данных и навигация
        self.load_all_data()
        self.navigate()

    def _on_page_loaded(self, ok):
        """Вызывается после полной загрузки страницы"""
        if not ok:
            return
        
        # Принудительная перерисовка ПОСЛЕ загрузки страницы
        if self.current_screen == 'poster':
            # Устанавливаем правильный язык для обоих типов плакатов
            # switchLang использует 'kk', setLang использует 'kz'
            lang_kk = 'kk' if self.current_lang == 'kz' else self.current_lang
            lang_js = f"""
                (function() {{
                    var lang = '{self.current_lang}';
                    var langKK = '{lang_kk}';
                    if (typeof switchLang === 'function') {{
                        switchLang(langKK);
                    }}
                    if (typeof setLang === 'function') {{
                        setLang(lang);
                    }}
                }})();
            """
            self.web_view.page().runJavaScript(lang_js)

    def resizeEvent(self, event):
        """Обновляем позиции кнопок при изменении размера окна"""
        super().resizeEvent(event)

        w = self.width()
        h = self.height()

        # 1. Браузер на весь экран
        self.web_view.setGeometry(0, 0, w, h)

        # 2. Позиционируем кнопки внутри навигационных контейнеров по центру
        # (Так как мы удалили _place_nav, нужно центрировать кнопки здесь)
        if hasattr(self, 'btn_prev'):
            self.btn_prev.move(16, h // 2 - 24)
        if hasattr(self, 'btn_next'):
            self.btn_next.move(16, h // 2 - 24)  # внутри контейнера 80px

        # 3. Кнопка "НАЗАД" (Левый верхний угол)
            # 3. Кнопка "НАЗАД"
        if hasattr(self, 'btn_back_overlay'):
            # Было: setGeometry(20, 20, 120, 45)
            # Стало:
            # x = 60  (сдвинули правее, чтобы не липла к краю)
            # y = 20  (высота та же)
            # w = 100 (ширина меньше)
            # h = 35  (высота меньше)
            self.btn_back_overlay.setGeometry(20, 20, 100, 35)
            self.btn_back_overlay.raise_()

        # 4. Стрелка ВЛЕВО (nav_left)
        # ВАЖНО: Начинается с y=80, чтобы не закрывать кнопку "Назад"
        if hasattr(self, 'nav_left'):
            self.nav_left.setGeometry(0, 80, 80, h - 80)
            self.nav_left.raise_()  # Поднимаем над браузером, но она ниже кнопки (т.к. y=80)

        # 5. Стрелка ВПРАВО (nav_right)
        if hasattr(self, 'nav_right'):
            self.nav_right.setGeometry(w - 80, 0, 80, h)
            self.nav_right.raise_()

    def load_all_data(self):
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
        """Главная навигация после запуска"""
        print(f"\n🔄 navigate(): Проверяю лицензию...")
        is_activated = licensing.is_activated()
        print(f"   Лицензия активирована: {is_activated}")

        if is_activated:
            print(f"   ➜ Показываю экран выбора предметов")
            self.show_subjects_screen()
        else:
            print(f"   ➜ Показываю экран активации")
            self.show_activation_screen()

    def navigate_after_activation(self):
        """После успешной активации показываем список предметов"""
        print(f"\n✅ navigate_after_activation()")
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
                self.current_lang = lang_map.get(subject_id, 'kz')
                print(f"   🌐 Языковой предмет, язык: {self.current_lang}")
                logging.info(
                    f"Выбран языковой предмет: {subject_id}, язык: {self.current_lang}")

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
                    self.btn_back_overlay.show()
                    self.btn_back_overlay.raise_()
                # ============================

                # Показываем стрелки
                if hasattr(self, 'nav_left'): self.nav_left.show()
                if hasattr(self, 'nav_right'): self.nav_right.show()

                # ✅ показать стрелки
                if hasattr(self, 'nav_left'):
                    self.nav_left.show()
                if hasattr(self, 'nav_right'):
                    self.nav_right.show()

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

                # === 4. СКРЫВАЕМ КНОПКУ ===
                if hasattr(self, 'btn_back_overlay'):
                    self.btn_back_overlay.hide()
                # ==========================

            self.current_screen = 'topics'
            self.show_topics_screen()

        elif self.current_screen == 'topics':
            print("   ➜ Возвращаюсь на экран предметов")

            self.current_topic = None
            self.current_topic_id = None
            self.current_screen = 'subjects'
            self.show_subjects_screen()

    def change_language(self, lang_code):
        """Пользователь переключил язык"""
        print(f"\n🌐 change_language({lang_code})")
        if lang_code in self.translations:
            self.current_lang = lang_code
            print(f"   ✅ Язык изменен на: {lang_code}")
            logging.info(f"Язык изменен на: {lang_code}")
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

    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.resize(1280, 800)
    main_window.show()
    sys.exit(app.exec())