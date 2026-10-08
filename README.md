# brain.com.ua parsers

Тестовое задание: три парсера карточки товара brain.com.ua (Requests + BeautifulSoup, Selenium, Playwright), результаты сохраняются в PostgreSQL через Django ORM.

Версии: Python 3.13, Django 6.1, PostgreSQL 18, Selenium 4, Playwright 1.63.

## Структура проекта

```
braincomua/
    braincomua_project/        Django проект
        braincomua_project/    settings.py
        parser_app/            модель Product
        manage.py
    modules/                   скрипты парсеров
        load_django.py         подключение Django для скриптов из modules
        1_parse_bs4.py         Requests + BeautifulSoup
        2_parse_selenium.py    Selenium
        3_parse_playwright.py  Playwright
        test_write.py          проверка записи в модель
        test_read.py           проверка чтения из модели
    results/
        products.csv           выгрузка таблицы через pgAdmin
        braincomua_dump.sql    дамп базы (pg_dump)
```

## Установка

```
python3 -m venv braincomua-env
source braincomua-env/bin/activate
pip install django "psycopg[binary]" requests beautifulsoup4 lxml selenium playwright
playwright install chromium
```

Создать базу `braincomua` в PostgreSQL, при необходимости поменять `USER` и `PASSWORD` в `braincomua_project/braincomua_project/settings.py`, затем:

```
cd braincomua_project
python manage.py migrate
```

Восстановить данные из дампа (вместо migrate):

```
psql braincomua < results/braincomua_dump.sql
```

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

## Собираемые данные

Полное название, цвет, объем памяти, производитель, цена обычная, цена акционная, все фото (список ссылок), код товара, количество отзывов, диагональ экрана, разрешение дисплея, все характеристики (словарь).

## Решения по неоднозначным моментам

1. Одна модель `Product` для всех трех парсеров. Поле `source` показывает, каким парсером собрана запись (`bs4`, `selenium`, `playwright`).
2. Цены сохраняются числом. Если на странице есть зачеркнутая цена, она записывается в `price` (цена обычная), а текущая в `sale_price` (цена акционная). Если скидки нет, текущая цена записывается в `price`, а `sale_price` = None.
3. iPhone 16 Pro Max снят с производства, поэтому блок цены на странице скрыт. В HTML цена есть, она и сохраняется.
4. Характеристики сохраняются плоским словарем `{название: значение}` со всех групп вкладки "Характеристики". Названия на украинском, как на сайте (страницы `/ukr/`).
5. Цвет, память, производитель, диагональ и разрешение ищутся по подписи характеристики и следующему за ней тегу, без порядковых индексов.
6. Поле `link` не уникальное: Selenium и Playwright собирают один и тот же товар. Запись через `get_or_create(**data)` без `defaults`.
7. На сайте два поля поиска с одинаковым классом, используется видимое (в блоке `header-bottom`). После ввода текста открывается окно быстрого поиска, которое перекрывает кнопку в шапке, поэтому нажимается кнопка "Знайти" этого окна.
8. Сайт защищен Cloudflare. Selenium и Playwright запускают Chrome с сохраненным профилем (`modules/chrome_profile`, `modules/playwright_profile`, в репозиторий не входят). При первом запуске проверку нужно пройти вручную в окне браузера, дальше профиль ее запоминает.
9. В Playwright используется `sync_playwright`, а запись в базу выполняется после закрытия браузера: внутри `sync_playwright` работает event loop, и Django ORM там вызывает ошибку `SynchronousOnlyOperation`.
10. В `INSTALLED_APPS` добавлен `django.contrib.postgres`: в Django 6 без него нельзя использовать `ArrayField` (поле `photos`).
11. Если значение не найдено, в поле записывается None.
