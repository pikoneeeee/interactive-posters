// Общий скрипт для всех плакатов informatics2.
// Надёжное переключение языка: не зависит от event.target.
(function () {
  function switchLang(lang) {
    if (!lang) return;
    if (lang === 'kz') lang = 'kk';
    var c = document.getElementById('poster-container');
    if (!c) return;
    c.className = c.className.replace(/\blang-\w+\b/g, '').trim() + ' lang-' + lang;
    var btns = document.querySelectorAll('.lang-btn');
    btns.forEach(function (b) {
      var bl = (b.getAttribute('data-lang') || b.textContent || '').trim().toLowerCase();
      if (bl === 'kz') bl = 'kk';
      b.classList.toggle('active', bl === lang);
    });
    try { localStorage.setItem('poster_lang', lang === 'kk' ? 'kz' : lang); } catch (e) {}
  }
  // Экспорт в глобал, чтобы inline onclick="switchLang(...)" продолжал работать.
  window.switchLang = switchLang;

  // Авто-инициализация: читаем сохранённый язык.
  function init() {
    var saved = 'ru';
    try { saved = localStorage.getItem('poster_lang') || 'ru'; } catch (e) {}
    if (saved === 'kz') saved = 'kk';
    switchLang(saved);

    // На всякий случай: если кнопки не имеют data-lang, ставим по тексту.
    document.querySelectorAll('.lang-btn').forEach(function (b) {
      if (!b.getAttribute('data-lang')) {
        var t = (b.textContent || '').trim().toLowerCase();
        if (t === 'kz' || t === 'kk') b.setAttribute('data-lang', 'kk');
        else if (t === 'en') b.setAttribute('data-lang', 'en');
        else if (t === 'ru') b.setAttribute('data-lang', 'ru');
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
