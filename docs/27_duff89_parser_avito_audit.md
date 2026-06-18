# Аудит Duff89/parser_avito Для Фонового Мониторинга

Дата: 2026-06-17.

Статус: `poc_candidate_license_blocker`.

Репозиторий:

```text
https://github.com/Duff89/parser_avito
```

Локальная копия для аудита:

```text
/tmp/duff89-parser-avito
```

Коммит:

```text
c6e373c feat: 3.2.15
```

## 1. Цель Аудита

Проверить, можно ли использовать `Duff89/parser_avito` как основу отдельного фонового worker для мониторинга цен Avito без платного SaaS-поставщика.

Важно: аудит выполнялся без запуска parser на Avito.

## 2. Краткий Вывод

Проект технически близок к нужному фоновому мониторингу:

- есть бесконечный background loop;
- есть Docker/docker-compose;
- есть конфигурация URL;
- есть SQLite для уже просмотренных объявлений;
- есть Excel export;
- есть Telegram/VK notification layer;
- есть фильтры по цене, словам, региону, продавцу, возрасту объявления;
- есть обработка 403/429;
- есть cookies/proxy providers.

Но есть блокирующий юридико-инженерный риск:

```text
LICENSE-файл не найден, явная лицензия в README/docs не обнаружена.
```

Поэтому код нельзя просто копировать или включать в наш проект как зависимость. Допустимый следующий шаг - только isolated POC в `/tmp` или отдельном sandbox окружении.

## 3. Техническая Архитектура Проекта

Ключевые файлы:

| Файл | Назначение |
|---|---|
| `parser_cls.py` | основной CLI/background parser |
| `config.toml` | конфигурация URL, фильтров, пауз, proxy/cookies |
| `models.py` | Pydantic-модели Avito embedded JSON |
| `dto.py` | dataclass конфигурации |
| `db_service.py` | SQLite viewed storage |
| `parser/http/client.py` | HTTP client на `curl_cffi` |
| `parser/export/excel.py` | Excel export |
| `filters/ads_filter.py` | фильтрация объявлений |
| `parser/cookies/*` | own/external cookies providers |
| `parser/proxies/*` | no/server/mobile proxy |
| `Dockerfile`, `docker-compose.yml` | запуск в контейнере |

## 4. Как Он Получает Данные

Текущая версия использует:

```text
curl_cffi requests.Session(impersonate=random browser)
```

а не Playwright как основной путь в `parser_cls.py`.

Алгоритм:

1. Делает GET по URL поиска Avito.
2. Ищет в HTML script:

```text
type="mime/invalid"
data-mfe-state="true"
```

3. Извлекает JSON state.
4. Берёт `searchCore` и `context`.
5. Для последующих страниц ходит в:

```text
https://www.avito.ru/web/1/js/items
```

6. Валидирует `catalog.items` через Pydantic `ItemsResponse`.
7. Применяет фильтры.
8. Сохраняет в SQLite как просмотренные и экспортирует в Excel.

Это хорошо для структурированных данных, потому что цена берётся не из текста HTML, а из модели `priceDetailed.value`.

## 5. Поля Данных

Модель `Item` содержит нужные поля:

- `id`;
- `urlPath`;
- `title`;
- `description`;
- `location`;
- `addressDetailed`;
- `sortTimeStamp`;
- `priceDetailed.value`;
- `normalizedPrice`;
- `images`;
- `geo`;
- `coords`;
- `sellerId`;
- `isReserved`;
- `isPromotion`;
- `total_views`;
- `today_views`;
- `phone`.

Для нашего оценщика минимально подходят:

```text
id -> external_id
title -> title
priceDetailed.value -> price
urlPath -> url
location.name -> region/location
sortTimeStamp -> published_at
```

## 6. Фоновый Режим

В `parser_cls.py` есть бесконечный цикл:

```text
while True:
  parser = AvitoParse(config)
  parser.parse()
  sleep(config.pause_general)
```

Если `one_time_start=true`, parser завершает работу после одного прохода.

Для нашего daily monitoring лучше использовать:

```text
one_time_start=true
```

и запускать процесс по расписанию. Причина: нам нужен дневной срез по всем объявлениям, а не бесконечный поток уведомлений.

## 7. Важный Конфликт С Нашей Задачей

`Duff89/parser_avito` оптимизирован под мониторинг новых/изменившихся объявлений.

Он хранит в SQLite:

```sql
viewed(id, price)
```

и фильтрует уже виденные пары `id + price`.

Для нашего расчёта дневного min/max это может быть проблемой:

- нам нужен полный дневной срез;
- повторно видимые объявления тоже важны;
- если объявление не новое, оно всё равно должно участвовать в min/max за день.

Следствие:

```text
Нельзя использовать его output "как есть" для daily min/max.
```

Нужно либо:

- запускать isolated one-shot без фильтра viewed;
- модифицировать фильтр `_filter_viewed`;
- брать данные до фильтрации;
- добавить новый storage, который сохраняет raw/full snapshot.

## 8. Фильтрация

Встроенные фильтры:

- уже просмотренные;
- диапазон цены;
- black keywords;
- white keywords;
- адрес/geo;
- seller blacklist;
- recent time;
- reserved;
- promoted.

Это полезно для борьбы с шумом:

- `keys_word_black_list`: картридж, тонер, печка, плата, блок питания, шлейф и т.п.;
- `keys_word_white_list`: модель и тип оборудования;
- `min_price/max_price`: отсечение запчастей и аномалий.

Но для оценщика нужен отдельный `ListingRelevanceFilter`, потому что один общий список стоп-слов не подойдет для всех категорий.

## 9. Docker И Deploy

Есть `Dockerfile` и `docker-compose.yml`.

Контейнер:

- ставит Python 3.11;
- ставит зависимости из `requirements.txt`;
- ставит `chromium-headless-shell` через Playwright;
- запускает `python parser_cls.py`;
- монтирует `config.toml`, `cookies.json`, `result`, `database.db`.

Это подходит для sidecar worker, но не для прямого включения в MVP.

## 10. Зависимости

Зависимости включают:

- `beautifulsoup4`;
- `curl_cffi`;
- `loguru`;
- `openpyxl`;
- `playwright`;
- `playwright-stealth`;
- `pydantic`;
- `requests`;
- `flet`;
- `httpx`;
- `pyexcel*`.

Минус: `requirements.txt` сохранён в UTF-16/с нулевыми байтами в локальной копии, это надо проверить перед установкой. Возможно, pip справится не всегда.

## 11. Блокировки И Cookies

Есть обработка статусов:

```text
401, 403, 429
```

При достижении `block_threshold` parser вызывает:

- `cookies.handle_block()`;
- `proxy.handle_block()`.

Есть варианты:

- без cookies;
- собственные cookies;
- внешний cookies API;
- server proxy;
- mobile proxy.

Для нашего ограничения "без платного SaaS" приемлемы только:

- без cookies/proxy для POC;
- собственные cookies отдельного технического аккаунта, если это будет принято как риск.

Неподходящие как чисто бесплатный путь:

- внешний cookies API;
- мобильные proxy;
- платные antiblock-сервисы.

## 12. Лицензия

Проверка:

```text
LICENSE* не найден
COPYING* не найден
README/docs не содержат явной лицензии
```

Следствие:

```text
Нельзя копировать код в наш репозиторий и нельзя строить продукт как производную работу без отдельного решения по лицензии.
```

Допустимо:

- изучить архитектуру;
- запустить isolated POC;
- написать собственный worker с нуля, используя общие идеи, а не код;
- запросить у автора лицензию, если когда-нибудь будет принято общаться с автором.

## 13. POC Возможен?

Да, POC возможен технически.

Рекомендуемый POC:

1. Не ставить зависимости в основной `.venv`.
2. Не добавлять код parser в наш repo.
3. Запустить через отдельный venv или Docker в `/tmp`.
4. Использовать `one_time_start=true`.
5. `count=1`, `pause_general` не важен.
6. Уведомления выключить.
7. `save_xlsx=true`.
8. `parse_phone=false`.
9. `use_bypass_api=false`.
10. `use_own_cookies=false` на первом run.
11. URL только один.

Цель POC:

- понять, получает ли parser HTML/JSON без 403/429;
- получить `result/avito.xlsx`;
- проверить поля;
- проверить шум выдачи;
- не строить production.

## 14. Go/Hold/No-Go

### Go На Следующий POC

Если принимаем риск запуска scraping POC:

- можно выполнить один one-shot run;
- без proxy;
- без cookies;
- без телефонов;
- без уведомлений;
- только публичная search page;
- только 1 URL;
- только `/tmp`.

### Hold

Если требуется юридическая чистота или гарантия стабильности:

- проект без лицензии;
- Avito может блокировать;
- нет официального API;
- production без proxy/cookies не подтверждён.

### No-Go

Для прямого включения в MVP:

- нет лицензии;
- output не соответствует daily full snapshot без доработки;
- parser содержит механику обхода блокировок/cookies/proxy;
- сильная зависимость от внутренней структуры Avito.

## 15. Рекомендация

Не включать `Duff89/parser_avito` в продукт.

Использовать его как:

```text
reference implementation + isolated POC candidate
```

Если POC получает данные без блокировки, следующий архитектурный шаг:

```text
написать собственный минимальный avito-monitor-worker
```

с нужным нам поведением:

- one-shot scheduled runs;
- full daily snapshot;
- JSON output;
- no phone parsing;
- no paid bypass;
- stop-on-block;
- explicit relevance filter;
- отдельный process от MVP.

