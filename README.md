# Резюме Юлии Петрушиной

Текст резюме редактируется только в `index.html`. При каждом изменении ветки
`main` GitHub Actions собирает оформленный PDF из этого HTML и публикует сайт
и PDF одним артефактом GitHub Pages.

PDF не хранится отдельно в Git. Сборка проверяет, что текстовые блоки HTML
есть в PDF. Если проверка не проходит, новая версия сайта не публикуется.
Ссылка скачивания содержит хеш PDF, чтобы браузер не использовал старую копию.

## Локальная сборка

```sh
python -m pip install -r scripts/requirements.txt
python scripts/test_build.py
python scripts/build_site.py --output _site
python -m http.server --directory _site
```

Весь готовый сайт находится в `_site`, PDF - в
`_site/data/resume/yulia-petrushina-cpp.pdf`. Оформление PDF задается в
`scripts/build_site.py`, оформление веб-страницы - в `styles.css`.

Open Sans распространяется по SIL Open Font License. Файлы шрифта взяты из
[официального репозитория](https://github.com/googlefonts/opensans/tree/main/fonts/ttf),
лицензия находится в `scripts/fonts/OFL.txt`.
