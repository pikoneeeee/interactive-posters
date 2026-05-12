# STYLE GUIDE — «Информатика 2»

Единое правило оформления для всех плакатов подпредмета `informatics2`.
Структура — как в `chemistry/ch_102.html`, но в **светлых тонах**.

---

## 1. Обязательные правила

1. **Качество**: плакат — это учебный материал. Текст точный, схемы правильные, примеры рабочие.
2. **Структура ch_102**: header + 3–5 секций + footer, grid-раскладка.
3. **Светлые тона**: белые/голубые/пастельные фоны; тёмный текст на светлом.
4. **Иллюстрации**: SVG-схемы, иконки, мини-диаграммы, примеры кода, картинки-эмодзи где уместно.
5. **Язык** соответствует классу (см. §7).
6. **3 языка**: ru, kk, en — обязательно. Все текстовые блоки через `<span lang="..." class="lang-content">`.

---

## 2. Скелет HTML

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{Название на русском}</title>
  <link rel="stylesheet" href="../../libs/tailwind.min.css">
  <link rel="stylesheet" href="../../libs/fonts.css">
  <style>/* см. §3 */</style>
</head>
<body class="p-6 md:p-10">
<div id="poster-container" class="lang-ru" style="max-width:1500px;margin:auto;">

  <!-- HEADER -->
  <header class="card rounded-custom p-10 mb-8 flex flex-col md:flex-row justify-between items-center border-b-2 border-sky-300">
    <div>
      <p class="text-slate-500 font-light tracking-widest text-sm uppercase mb-2">{X класс · Раздел · Подраздел}</p>
      <h1 lang="kk" class="lang-content heading-font text-3xl md:text-5xl tracking-tight text-sky-700">…</h1>
      <h1 lang="en" class="lang-content heading-font text-3xl md:text-5xl tracking-tight text-sky-700">…</h1>
      <h1 lang="ru" class="lang-content heading-font text-3xl md:text-5xl tracking-tight text-sky-700">…</h1>
    </div>
    <div class="flex gap-2 mt-4 md:mt-0">
      <button onclick="switchLang('ru')" class="lang-btn active">RU</button>
      <button onclick="switchLang('kk')" class="lang-btn">KZ</button>
      <button onclick="switchLang('en')" class="lang-btn">EN</button>
    </div>
  </header>

  <!-- SECTION(S) -->
  <section class="mb-8">
    <h2 class="heading-font text-2xl text-sky-700 uppercase tracking-widest mb-6">…</h2>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="card rounded-custom p-8">…</div>
    </div>
  </section>

  <!-- FOOTER / KEY TAKEAWAY -->
  <footer class="card rounded-custom p-10">…</footer>

</div>
<script>
function switchLang(lang){
  const c=document.getElementById('poster-container');
  c.className=c.className.replace(/lang-\w+/,'')+' lang-'+lang;
  document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('active'));
  event.target.classList.add('active');
}
</script>
<script>/* poster-lang-init */
(function(){var s='ru';try{s=localStorage.getItem('poster_lang')||'ru'}catch(e){}
if(s==='kz')s='kk';if(typeof switchLang==='function')switchLang(s);})()
</script>
</body>
</html>
```

---

## 3. Стили (CSS) — копировать в каждый плакат

```css
body {
  font-family: 'Inter', sans-serif;
  background: radial-gradient(circle at top right, #e0f2fe, #f0f9ff, #ffffff);
  color: #0f172a; min-height: 100vh;
}
.heading-font { font-family: 'Montserrat', sans-serif; }

/* светлая карточка (было glass) */
.card {
  background: rgba(255,255,255,0.85);
  border: 1px solid rgba(14,165,233,0.18);
  box-shadow: 0 4px 20px rgba(14,165,233,0.08);
  backdrop-filter: blur(6px);
}
.card-accent {
  background: rgba(14,165,233,0.08);
  border: 1px solid rgba(14,165,233,0.30);
}
.rounded-custom { border-radius: 2rem; }

/* переключатель языка */
.lang-btn {
  padding: 10px 24px; border-radius: 9999px;
  border: 1px solid rgba(14,165,233,0.30); background: transparent;
  color: #0369a1; font-weight: 700; cursor: pointer; font-size: 1.1rem;
  transition: all 0.2s;
}
.lang-btn.active { background: #0ea5e9; color: #ffffff; font-weight: 800; border-color: #0ea5e9; }
.lang-content { display: none; }
.lang-kk .lang-content[lang="kk"],
.lang-en .lang-content[lang="en"],
.lang-ru .lang-content[lang="ru"] { display: block; }

/* таблицы */
table.t { width: 100%; border-collapse: collapse; }
table.t th {
  background: rgba(14,165,233,0.10); color: #0369a1;
  padding: 16px 20px; font-weight: 700; font-size: 1.15rem; text-align: left;
  border-bottom: 2px solid rgba(14,165,233,0.25);
}
table.t td {
  padding: 14px 20px; border-bottom: 1px solid rgba(15,23,42,0.08);
  font-size: 1.1rem; vertical-align: top; color: #334155;
}
table.t tr:hover td { background: rgba(14,165,233,0.04); }

/* код/формула */
.code-block {
  background: #0f172a; color: #7dd3fc;
  font-family: 'Courier New', monospace;
  padding: 18px 24px; border-radius: 1rem; font-size: 1.1rem; line-height: 1.7;
  white-space: pre; overflow-x: auto; border: 1px solid #1e293b;
}
.code-block .kw   { color: #f472b6; }   /* ключевые слова */
.code-block .str  { color: #a7f3d0; }   /* строки */
.code-block .num  { color: #fde68a; }   /* числа */
.code-block .com  { color: #64748b; font-style: italic; }  /* комментарии */
.code-block .fn   { color: #93c5fd; }   /* функции */

/* плашка/бейдж */
.badge {
  display: inline-block; padding: 5px 14px; border-radius: 999px;
  font-weight: 700; font-size: 0.95rem; margin: 3px;
  background: rgba(14,165,233,0.12); color: #0369a1;
  border: 1px solid rgba(14,165,233,0.30);
}

/* SVG-схема контейнер */
.svg-wrap { background: #f8fafc; border-radius: 1rem; padding: 1rem; border: 1px solid rgba(14,165,233,0.18); }
```

---

## 4. Цветовая палитра (светлая)

| Назначение        | Цвет                     | Tailwind       |
|-------------------|--------------------------|----------------|
| Фон страницы      | `#e0f2fe → #ffffff`      | sky-100 → white|
| Карточка          | `rgba(255,255,255,0.85)` | bg-white/85    |
| Основной текст    | `#0f172a`                | slate-900      |
| Вторичный текст   | `#334155` / `#64748b`    | slate-700/500  |
| Заголовок/акцент  | `#0369a1`                | sky-700        |
| Акцент тёплый     | `#c2410c` / `#d97706`    | orange-700     |
| Успех             | `#047857`                | emerald-700    |
| Предупреждение    | `#b45309`                | amber-700      |
| Опасность         | `#b91c1c`                | rose-700       |
| Линии/границы     | `rgba(14,165,233,0.18)`  | sky-500/18     |

---

## 5. Структура по секциям

Для каждого плаката — 3–5 секций + footer:

- **Секция 1**: главное определение / общая концепция (большой «что это»)
- **Секция 2**: ключевые свойства / классификация / таблица
- **Секция 3**: пример / схема / код / диаграмма
- **Секция 4**: применение / использование / практика
- **Footer**: 3-колоночный вывод (алгоритм / запомни / интересный факт)

---

## 6. Иллюстрации

1. **SVG-схемы** — предпочтительно (масштабируются, работают офлайн).
2. **Эмодзи** — для заголовков разделов (🖥️ 🔐 🧠 🤖 и т.д.), в умеренном количестве.
3. **Картинки-символы** (Unicode): ▲▼◆⬢⬡⬣ для схем.
4. **ASCII-схемы** в `.code-block` для блок-схем, деревьев, сетей.
5. **Диаграммы** Chart.js использовать только когда реально добавляет смысл.

Все схемы оборачивать в `.svg-wrap` или `.card` для единого вида.

---

## 7. Уровень языка по классам

### 5 класс — простой, образный
- Короткие предложения (до 12 слов).
- Аналогии из быта: «файл — как лист в папке».
- Термины обязательно с пояснением в скобках.
- Больше иконок и визуала.

### 6 класс — простой, с терминами
- Вводим базовые термины Python, эргономики, 3D-графики.
- По-прежнему с простыми аналогиями.

### 7 класс — учебный
- Нормальная учебная лексика.
- Можно использовать термины без постоянных пояснений.

### 8 класс — учебный, строже
- Формулы, таблицы истинности не требуются — но логика чёткая.
- Алгоритмы описываем точно.

### 9 класс — полный учебный
- Можно сложные формулировки.
- Рабочие примеры кода Python 12+ строк, с комментариями.

### 10 класс — академический
- Технические термины, без упрощений.
- Полные определения (CIA-триада, нормальные формы).

### 11 класс — научно-популярный / академический
- Концепции уровня introductory course в университете.
- ML, Blockchain, IoT: термины сохраняем в оригинале.

---

## 8. Нейминг файлов и ID

- Папка: `content/posters/informatics2/`
- Файл: `i2_<N>.html`, где N — порядковый номер (1…158)
- `id` в subjects.json: `"i2_N"`
- `name_key` в subjects.json: `"i2_topic_N"`
- Путь по классам: сортировка по `grade` возрастает (5 → 11)

---

## 9. Чек-лист перед коммитом плаката

- [ ] 3 языка присутствуют во **всех** текстовых блоках
- [ ] Подзаголовок в header указывает класс и раздел
- [ ] Светлый фон, тёмный текст
- [ ] Минимум одна иллюстративная схема / картинка / код-пример
- [ ] Таблицы стилизованы через `.t`
- [ ] Формулы/код — через `.code-block`
- [ ] Уровень языка соответствует классу (§7)
- [ ] Скрипт `switchLang` и `poster-lang-init` в конце
