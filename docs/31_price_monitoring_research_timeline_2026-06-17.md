# Хронология Исследования Оценщика

Дата: 2026-06-17.

Цель: зафиксировать, как прошли от идеи модуля оценки/мониторинга цен до текущего решения по отдельному research POC.

## 1. Исходный Запрос

Пользователь предложил будущий дополнительный модуль:

```text
мониторинг цен на позицию в списке, инструмент оценщика
```

Бизнес-смысл:

- компания продаёт оборудование на вторичном рынке;
- нужно отслеживать рыночные цены на аналоги;
- основной источник интереса - Avito;
- нужны дневные min/max цены, история и графики.

Сразу зафиксировано ограничение:

```text
MVP не трогать, код MVP не писать.
```

## 2. Первичная Проработка ТЗ И Архитектуры

Создан базовый документ:

```text
docs/14_price_monitoring_module.md
```

В нём описаны:

- сущности модуля;
- позиции мониторинга;
- daily snapshots;
- объявления;
- дашборды;
- экспорт;
- API;
- архитектурные границы.

Затем добавлены:

```text
docs/15_price_monitoring_mvp_plan.md
docs/16_price_monitoring_decisions.md
docs/17_price_monitoring_developer_handoff.md
```

Ключевое уточнение:

```text
поиск сначала по всей России
```

означает региональный фильтр Avito, а не местонахождение нашего оборудования.

## 3. Переоценка Приоритета

Пользователь справедливо указал:

```text
если не решить механизм парсинга, нет смысла делать базовые компоненты
```

После этого порядок работ изменён:

```text
сначала источник данных Avito
потом БД/UI/scheduler
```

Создан discovery-план:

```text
docs/18_avito_data_source_discovery.md
```

## 4. Официальный Avito API И Прямой Доступ

Проверены официальные материалы Avito Developers:

- developer portal;
- API catalog;
- OpenAPI list;
- `item` API;
- API Terms;
- robots.txt;
- прямой search URL.

Результаты:

```text
docs/19_avito_data_source_discovery_results.md
```

Вывод:

- API для поиска публичных объявлений рынка не найден;
- найденные API относятся к своим объявлениям, статистике, продвижению, сообщениям и т.п.;
- прямой серверный запрос к Avito search получил `HTTP 429` / CAPTCHA;
- robots.txt ограничивает поисковые URL.

Статус:

```text
official_api_not_found
direct_simple_http_blocked
```

## 5. Промежуточные Сервисы

Проверены варианты:

- Exa;
- SERP API;
- Apify;
- Bright Data;
- MarketParser;
- SPFA;
- ShopAPIS.

Документ:

```text
docs/20_intermediary_avito_data_services.md
```

Вывод:

- Exa/SERP не подходят для daily snapshot, потому что это поисковая выдача/индекс, а не структурированный источник Avito listings;
- Apify технически близок;
- Bright Data/MarketParser/ShopAPIS могут быть промышленными вариантами;
- но это платные или vendor-зависимые решения.

## 6. Vendor Track И Отказ От Общения С Поставщиками

Сначала был подготовлен vendor spike:

```text
docs/21_avito_vendor_spike_requests.md
```

Затем пользователь уточнил:

```text
не хочу общаться с людьми, надо техническое решение
```

Документ `21` переведён в fallback:

```text
fallback_vendor_track
```

Создан self-service technical spike:

```text
docs/22_avito_self_service_technical_spike.md
```

## 7. Apify Token И Технический Spike

Пользователь получил Apify API token.

Проведён технический spike:

- проверена авторизация;
- запущен actor `server0/avito-scraper`;
- получены dataset results по тестовым позициям;
- проверены поля `title`, `price`, `url`, `location`, `postedDate`, `scrapedAt`.

Документ:

```text
docs/23_apify_avito_spike_results.md
```

Вывод:

- Apify технически работает;
- возвращает структурированные listings;
- но выдача содержит расходники, запчасти и шум;
- нужен relevance filter.

После уточнения пользователя:

```text
платный сервис не подходит
```

Apify получил статус:

```text
no_go_paid_service
```

## 8. Бесплатные И Self-Hosted Варианты

Создан документ:

```text
docs/24_free_avito_source_options.md
```

Рассмотрены:

- ручной CSV/Excel импорт;
- self-hosted parser research;
- готовые URL поиска;
- браузерная сессия оператора;
- альтернативные источники.

Вывод:

```text
полностью автоматический бесплатный источник не подтверждён
```

## 9. Агентский Браузерный Режим

Пользователь запросил:

```text
полностью автоматический и/или агентский режим
исследуй возможность прикинуться пользователем
```

Создан документ:

```text
docs/25_agentic_browser_avito_mode.md
```

Вывод:

- корректный вариант - отдельный браузерный профиль и stop-on-block;
- не закладывать обход CAPTCHA, stealth fingerprinting, proxy rotation;
- подход возможен, но слишком тяжёлый как основной следующий шаг.

Попытка подготовить Playwright POC остановлена пользователем как слишком сложная.

## 10. Поиск Готовых Self-Hosted Parser

Продолжен поиск фонового решения.

Найден главный кандидат:

```text
Duff89/parser_avito
```

Документ:

```text
docs/26_self_hosted_avito_background_monitoring.md
```

Почему интересен:

- open-source;
- Python;
- активный проект;
- Docker;
- фоновый режим;
- Excel export;
- Telegram/VK уведомления;
- отслеживание новых объявлений и изменения цены.

## 11. Аудит Duff89/parser_avito

Репозиторий склонирован в:

```text
/tmp/duff89-parser-avito
```

Аудит без запуска:

```text
docs/27_duff89_parser_avito_audit.md
```

Вывод:

- архитектурно близок;
- использует `curl_cffi` и embedded JSON;
- умеет фоновый loop;
- есть filters/export/sqlite;
- но нет явного LICENSE;
- модель заточена под новые/изменившиеся объявления, а не daily full snapshot.

Решение:

```text
использовать как reference implementation + isolated POC candidate
```

## 12. Реальный POC Duff89/parser_avito

Пользователь справедливо отметил:

```text
надо быть уверенным, что Duff89 работает
```

Выполнен isolated POC:

- отдельный venv в `/tmp`;
- нормализован UTF-16 requirements;
- один URL `Kyocera ECOSYS M2040dn`;
- без cookies;
- без proxy;
- без телефонов;
- без уведомлений;
- `one_time_start=true`.

Документ:

```text
docs/28_duff89_parser_avito_poc_results.md
```

Результат первого запуска:

```text
Хорошие запросы: 1
Плохие запросы: 0
Объявлений перед чисткой: 50
Сохранено: 49
```

Результат второго запуска:

```text
Объявлений перед чисткой: 50
После viewed-фильтра: 3
Сохранено: 2
```

Вывод:

- подход реально работает;
- но готовый parser не подходит как целевой daily snapshot, потому что фильтрует viewed.

## 13. Решение: Clean-Room Parser

Пользователь предложил:

```text
взять идею и написать свой parser улучшенный и целевой
```

Принято решение:

```text
clean-room parser-worker
```

Документ:

```text
docs/29_clean_room_avito_parser_design.md
```

Принципы:

- не копировать код Duff89;
- использовать только подтверждённые архитектурные идеи;
- one-shot worker;
- full daily snapshot;
- JSON output;
- relevance filter;
- stop-on-block;
- не трогать MVP.

## 14. Clean-Room POC

Создан POC в:

```text
/tmp/avito-monitor-worker-poc
```

Затем перенесён как research-пакет:

```text
research/avito-monitor-worker-poc/
```

Содержит:

```text
README.md
config/search_jobs.example.json
src/worker.py
.gitignore
```

Документ:

```text
docs/30_clean_room_avito_parser_poc_results.md
```

Результаты:

- live HTTP нестабилен: были `HTTP 200` и `HTTP 403`;
- на сохранённом live HTML extractor получил 50 карточек;
- нормализация работает;
- raw snapshot сохраняется до фильтрации;
- daily snapshot считается.

## 15. Улучшение Relevance Filter

Первый snapshot дал подозрительный min:

```text
min_price: 7500
```

Причина: в relevant попала запчасть `Блок проявки Kyocera DV-1150`.

Фильтр доработан offline без новых запросов:

- добавлен статус `unknown`;
- добавлены причины `repair_or_incomplete`;
- добавлены причины `accessory_or_consumable`;
- accessory detection переведён на title;
- `unknown` исключён из min/max/median.

Последний offline результат:

```text
raw: 50
normalized: 50
relevant: 37
unknown: 3
rejected: 10
min_price: 15000
max_price: 65000
median_price: 23995
```

## 16. Текущее Решение

Текущий статус:

```text
research_poc_ready_for_endurance_test
```

MVP не тронут.

Платные источники исключены.

Официальный API не найден.

Готовый parser подтвердил жизнеспособность подхода.

Собственный clean-room POC подготовлен как isolated research-пакет.

Главный нерешённый риск:

```text
live HTTP stability без cookies/proxy
```

## 17. Следующая Сессия

Не делать частые live-запросы.

Следующий live run:

```text
не чаще 1 раза в день
```

План:

1. Расширить `search_jobs.example.json` до 3 тестовых позиций.
2. Сделать один осторожный live run.
3. Если не blocked, запустить endurance test:
   - 3 позиции;
   - 1 запуск в день;
   - 3-5 дней;
   - без cookies/proxy.
4. По итогам решить:
   - `go_worker_prototype`;
   - `hold_http_unstable`;
   - `browser_profile_research`.

