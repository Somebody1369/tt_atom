# brain.com.ua parsers

Тестовое задание: три парсера карточки товара brain.com.ua (Requests + BeautifulSoup, Selenium, Playwright), результаты сохраняются в PostgreSQL через Django ORM.

Версии: Python 3.13, Django 6.1, PostgreSQL 18, Selenium 4.50 + undetected-chromedriver 3.5, Playwright 1.63. Точные версии библиотек в `requirements.txt`.

## Структура проекта

```
braincomua/
    braincomua-env/            виртуальное окружение (в репозиторий не входит)
    braincomua_project/        Django проект
        braincomua_project/    settings.py
        parser_app/            модель Product
        manage.py
    modules/                   скрипты парсеров
        load_django.py         подключение Django для скриптов из modules
        1_parse_bs4.py         Requests + BeautifulSoup
        2_parse_selenium.py    Selenium
        3_parse_playwright.py  Playwright
        test_write.py          проверка записи в модель (вспомогательный, без номера)
        test_read.py           проверка чтения из модели (вспомогательный, без номера)
    results/
        products.csv           выгрузка таблицы через pgAdmin
        braincomua_dump.sql    дамп базы (pg_dump)
    files/                     отладочные скриншоты Selenium/Playwright при таймауте
    requirements.txt
```

## Установка

Нужен установленный **Google Chrome**: Selenium (через undetected-chromedriver) и Playwright (`channel='chrome'`) запускают именно его, а не отдельный Chromium. Поэтому `playwright install chromium` не нужен. undetected-chromedriver сам скачивает chromedriver под версию установленного Chrome; на Mac он берет сборку для Intel, поэтому на Mac с Apple Silicon нужен Rosetta 2.

```
python3 -m venv braincomua-env
source braincomua-env/bin/activate
pip install -r requirements.txt
```

Создать пустую базу `braincomua` в PostgreSQL, при необходимости поменять `USER` и `PASSWORD` в `braincomua_project/braincomua_project/settings.py`, затем:

```
cd braincomua_project
python manage.py migrate
```

Или вместо `migrate` восстановить базу вместе с данными из дампа (в пустую базу `braincomua`, из корня проекта):

```
psql -d braincomua -f results/braincomua_dump.sql
```

Дамп сделан pg_dump 18 без владельца и прав (`--no-owner --no-privileges`), поэтому восстанавливается под любым пользователем. Строку `\restrict` в начале дампа понимает psql 18 и обновления старых версий с августа 2025 года (17.6, 16.10, 15.14 и т.д.).

## Cloudflare

Сайт защищен Cloudflare. Обычный Selenium (chromedriver) Cloudflare распознает, и проверка "Verifying you are human" на нем не заканчивается. Поэтому Selenium запускается через undetected-chromedriver: по документу «Особенности Selenium» он предназначен для обхода Cloudflare, и проверка проходит без ручных действий. Playwright запускает настоящий Chrome (`channel='chrome'`) с флагом `--disable-blink-features=AutomationControlled`, и проверка тоже проходит сама.

Оба скрипта работают с сохраненным профилем Chrome (`modules/chrome_profile` и `modules/playwright_profile`, создаются автоматически, в репозиторий не входят), профиль хранит cookies между запусками. Если проверка все же потребует действия (например, нажать галочку), это можно сделать в окне браузера: скрипт ждет до 2 минут.

Если шаг не выполнился за отведенное время, скрипт печатает название шага, заголовок и адрес страницы и сохраняет скриншот в `files/` (`selenium_debug.png` или `playwright_debug.png`). В базу в этом случае ничего не записывается.

## Запуск

Все скрипты запускаются из папки `modules`:

```
cd modules
python 1_parse_bs4.py
python 2_parse_selenium.py
python 3_parse_playwright.py
```

- `1_parse_bs4.py` открывает страницу Apple iPhone 16 Pro Max 256GB Black Titanium по прямой ссылке.
- `2_parse_selenium.py` и `3_parse_playwright.py` открывают главную страницу, вводят в поиск "Apple iPhone 15 128GB Black", нажимают кнопку "Знайти" и открывают первый результат.

Каждый скрипт печатает собранные данные через pprint и сохраняет их в модель `Product`.

Нумерация файлов: по правилу «Оформление проекта» у каждого основного скрипта в `modules` в начале стоит цифра очередности запуска, вспомогательные скрипты без номера. Три парсера не зависят друг от друга, номер задает рекомендуемый порядок: Requests/BS4 → Selenium → Playwright, как в задании.

## Собираемые данные

Полное название, цвет, объем памяти, производитель, цена обычная, цена акционная, все фото (список ссылок), код товара, количество отзывов, диагональ экрана, разрешение дисплея, все характеристики (словарь).

## Решения по неоднозначным моментам

1. **Один Django проект и одна модель `Product` для трех парсеров.** По правилу «Оформление проекта» папка проекта называется по домену сайта (`braincomua_project`), а все скрипты парсера лежат в `modules`. Все три парсера работают с одним сайтом, поэтому проект один. Поле `source` показывает, каким парсером собрана запись (`bs4`, `selenium`, `playwright`).
2. **Поле `link` не уникальное.** Selenium и Playwright собирают один и тот же товар с одной ссылкой. Запись идет через `get_or_create(**data)` без `defaults`, как требует документ «Ошибки» (п. 4). С `unique=True` запись второго парсера упала бы с `IntegrityError`, потому что `get_or_create` создает новую запись, если отличается хотя бы одно поле (здесь `source`).
3. **Цены сохраняются числом.** Если на странице есть зачеркнутая цена, она записывается в `price` (цена обычная), а текущая в `sale_price` (цена акционная). Если скидки нет, текущая цена записывается в `price`, а `sale_price` = None.
4. **iPhone 16 Pro Max снят с производства**, поэтому блок цены на странице скрыт. В HTML цена есть, она и сохраняется.
5. **Характеристики сохраняются плоским словарем** `{название: значение}` со всех групп вкладки "Характеристики": названия в разных группах не повторяются, поэтому при объединении групп ничего не теряется (проверено: 43 из 43 у iPhone 16 Pro Max, 40 из 40 у iPhone 15). Названия на украинском, как на сайте (страницы `/ukr/`). В Postgres это `jsonb`, он хранит ключи в своем порядке, а не в порядке сайта.
6. **Цвет, память, производитель, диагональ и разрешение** ищутся по подписи характеристики и следующему за ней тегу, без порядковых индексов. Количество отзывов берется только из блока текущего товара: на странице есть еще счетчики отзывов серии с тем же классом.
7. **Поиск.** На сайте два поля поиска с одинаковым классом, используется видимое (в блоке `header-bottom`). После ввода текста открывается окно быстрого поиска, которое перекрывает кнопку в шапке, поэтому нажимается кнопка "Знайти" этого окна (у кнопки в шапке нет текста, только иконка).
8. **Playwright: запись в базу после закрытия браузера.** Используется `sync_playwright` (документ «Особенности playwright»: простой скрипт в стиле Selenium без асинхронности). В документе сказано, что с `sync_playwright` Django ORM работает как обычно, но в Django 6 внутри блока `with sync_playwright()` запущен event loop, и любой запрос к базе выдает `SynchronousOnlyOperation: You cannot call this from an async context` (проверено). Для одного товара проще всего собрать данные, закрыть браузер и потом записать их. Для многих страниц нужен вариант из `async_playwright_example.py`: `async_playwright` и запись через `sync_to_async`.
9. В `INSTALLED_APPS` добавлен `django.contrib.postgres`: в Django 6 без него нельзя использовать `ArrayField` (поле `photos`), проверка `postgres.E005`.
10. Если значение не найдено (в том числе пустой список фото или пустой словарь характеристик), в поле записывается None. Для `characteristics` (JSONField) перед `get_or_create` ключ `characteristics=None` заменяется на `characteristics__isnull=True`: в Django 6.1 `characteristics=None` в запросе означает JSON-значение `null`, а не пустое поле, поэтому сохраненная запись не находилась и при каждом запуске создавался дубль (проверено на тестовой базе). В саму запись при этом попадает обычный NULL.
11. CSV выгружен через pgAdmin, без отдельного скрипта (документ «CSV - Выгрузка»).
