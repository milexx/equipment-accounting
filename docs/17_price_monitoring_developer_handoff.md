# Developer Handoff: Модуль Мониторинга Цен

Документ предназначен для разработчика, который будет реализовывать post-MVP модуль "Оценщик". Это не ТЗ для бизнеса, а практическая карта работ по коду.

Связанные документы:

- `docs/14_price_monitoring_module.md` - ТЗ и архитектура;
- `docs/15_price_monitoring_mvp_plan.md` - план MVP модуля;
- `docs/16_price_monitoring_decisions.md` - проектные решения.

## 1. Главное Ограничение

Модуль мониторинга цен реализуется как отдельный post-MVP контур.

На первом этапе нельзя:

- менять текущие сценарии `/region`;
- менять текущие сценарии `/equipment`;
- менять статусы оборудования;
- добавлять обязательные поля в карточку оборудования;
- автоматически менять цену продажи;
- связывать все карточки оборудования с оценщиком миграцией;
- ломать текущие admin-экраны.

Допустимо:

- добавить отдельный раздел `/pricing`;
- добавить новые таблицы;
- добавить новые модели;
- добавить новые маршруты;
- добавить новые шаблоны;
- добавить новые сервисы и репозитории;
- добавить пункт навигации для центра/admin после готовности раздела.

## 2. Предлагаемая Структура Модулей

### API / Routes

```text
app/api/pricing.py
```

Назначение:

- HTML-страницы модуля;
- обработка форм;
- ручной запуск сбора;
- CSV-экспорт;
- журнал запусков и ошибок.

### Models

```text
app/models/pricing.py
```

Или отдельные файлы, если модель станет большой:

```text
app/models/price_category.py
app/models/monitored_item.py
app/models/market_source.py
app/models/price_observation.py
app/models/daily_price_snapshot.py
app/models/price_scrape_run.py
app/models/parser_error.py
```

Рекомендация: для первого этапа можно начать с одного `pricing.py`, если это соответствует стилю проекта. Если файл быстро разрастётся, разделить.

### Schemas / Forms

```text
app/schemas/pricing.py
```

Назначение:

- структуры формы позиции;
- структуры фильтров;
- структуры данных графика;
- структуры CSV-экспорта.

### Repositories

```text
app/repositories/pricing_repository.py
```

Если объём станет большим:

```text
app/repositories/monitored_item_repository.py
app/repositories/price_observation_repository.py
app/repositories/price_snapshot_repository.py
app/repositories/price_run_repository.py
```

### Services

```text
app/services/pricing_service.py
app/services/price_monitoring_service.py
app/services/price_snapshot_service.py
```

Назначение:

- бизнес-операции по позициям;
- запуск мониторинга;
- расчёт дневных срезов;
- подготовка данных для графика;
- экспорт.

### Parsers

```text
app/services/pricing_parsers/base.py
app/services/pricing_parsers/registry.py
app/services/pricing_parsers/avito.py
```

Назначение:

- `base.py` - контракт `PriceParser`;
- `registry.py` - выбор парсера по источнику;
- `avito.py` - вся логика Avito.

Важно: Avito-специфика не должна попадать в маршруты, шаблоны, репозитории и расчёт дневных срезов.

### Scheduler

```text
app/services/pricing_scheduler.py
```

Назначение:

- инициализация APScheduler;
- регистрация ежедневной задачи;
- защита от параллельных запусков.

Вопрос запуска scheduler нужно решать аккуратно: при нескольких worker-процессах нельзя запускать одну и ту же задачу несколько раз. Для текущего dev/demo режима с одним uvicorn-процессом допустимо встроенное решение, но это нужно явно задокументировать.

### Templates

```text
app/templates/pricing/index.html
app/templates/pricing/items.html
app/templates/pricing/item_form.html
app/templates/pricing/item_detail.html
app/templates/pricing/dashboard.html
app/templates/pricing/runs.html
app/templates/pricing/run_detail.html
app/templates/pricing/errors.html
```

### Static

Если используется Chart.js локально:

```text
app/static/vendor/chart.js
```

Если подключение внешних CDN нежелательно, хранить статический файл локально.

## 3. Таблицы И Миграции

Создать Alembic-миграцию для новых таблиц:

```text
price_categories
monitored_items
market_sources
price_scrape_runs
price_observations
daily_price_snapshots
parser_errors
```

### Минимальные Связи

```text
monitored_items.category_id -> price_categories.id
price_scrape_runs.source_id -> market_sources.id
price_observations.item_id -> monitored_items.id
price_observations.source_id -> market_sources.id
price_observations.run_id -> price_scrape_runs.id
daily_price_snapshots.item_id -> monitored_items.id
daily_price_snapshots.source_id -> market_sources.id
daily_price_snapshots.run_id -> price_scrape_runs.id
parser_errors.source_id -> market_sources.id
parser_errors.item_id -> monitored_items.id
parser_errors.run_id -> price_scrape_runs.id
```

### Важные Ограничения

Рекомендуемые уникальности:

```text
price_categories.slug unique
market_sources.code unique
daily_price_snapshots(item_id, source_id, snapshot_date) unique
```

Для объявлений:

```text
price_observations(source_id, listing_external_id) unique nullable
```

Если `listing_external_id` недоступен, дубль можно определять позже по URL.

### Индексы

```text
monitored_items(is_active, category_id)
monitored_items(brand, model)
price_observations(item_id, source_id, observed_at)
price_observations(listing_external_id)
daily_price_snapshots(item_id, source_id, snapshot_date)
price_scrape_runs(source_id, started_at)
parser_errors(source_id, created_at)
```

## 4. Статусы И Enum

Добавить enum или строковые константы для:

### Run Status

```text
planned
running
success
partial_failed
failed
```

### Snapshot Status

```text
ok
no_data
failed
```

### Expected Condition

```text
any
working
not_working
for_parts
new
```

Для первого этапа можно хранить строки, но лучше централизовать значения в `app/models/enums.py` или отдельном pricing enum-файле.

## 5. Маршруты

Реализовать HTML-first маршруты:

```text
GET  /pricing
GET  /pricing/items
GET  /pricing/items/new
POST /pricing/items
GET  /pricing/items/{id}
GET  /pricing/items/{id}/edit
POST /pricing/items/{id}
POST /pricing/items/{id}/archive

GET  /pricing/dashboard
GET  /pricing/items/{id}/history
GET  /pricing/items/{id}/observations
GET  /pricing/runs
GET  /pricing/runs/{id}
GET  /pricing/errors
GET  /pricing/export.csv

POST /pricing/items/{id}/run-now
POST /pricing/runs/run-all
GET  /pricing/health
```

### Редиректы

После POST использовать redirect, как в текущем приложении.

### Права

Первый вариант:

- `center` может смотреть `/pricing`, дашборды и историю;
- `center_admin` может управлять позициями и запускать сбор;
- `region` не имеет доступа к `/pricing`.

Если позже появится роль `valuer`, права вынести в отдельную функцию.

## 6. Сервисы

### PricingService

Операции:

- создать позицию;
- обновить позицию;
- архивировать позицию;
- получить список позиций;
- получить карточку позиции;
- получить фильтры.

### PriceMonitoringService

Операции:

- запустить сбор одной позиции;
- запустить сбор всех активных позиций;
- создать запись запуска;
- обновить статус запуска;
- сохранить наблюдения;
- сохранить ошибки;
- вызвать пересчёт дневного среза.

### PriceSnapshotService

Операции:

- посчитать `min_price`;
- посчитать `max_price`;
- посчитать `avg_price`;
- посчитать `median_price`;
- посчитать `listing_count`;
- создать `no_data`;
- создать `failed`;
- пересчитать день.

Медиану считать на backend. Для PostgreSQL можно использовать SQL-процентили позже, но для MVP допустимо считать по списку цен в Python, так как объёмы небольшие.

## 7. Parser Contract

Базовый контракт:

```python
class PriceParser:
    def fetch_prices(self, search_query: str, region: str | None, limit: int) -> list[PriceListing]:
        ...
```

`PriceListing`:

```text
title
url
external_id
price
currency
location
listing_date
raw_payload
```

### AvitoParser

`AvitoParser` отвечает за:

- построение поискового URL;
- маппинг `search_region` в географический фильтр Avito;
- HTTP-запрос;
- разбор HTML или ответа API;
- нормализацию цены;
- извлечение ссылки;
- извлечение внешнего идентификатора, если доступен;
- обработку пустой выдачи;
- создание технических ошибок.

Если регион не сопоставляется с Avito, парсер должен вернуть ошибку настройки, а не молча искать в другом регионе.

## 8. Безопасность И Ограничения Avito

Перед реализацией базовых компонентов модуля нужно подтвердить допустимый и технически рабочий способ получения данных с Avito. Для этого проводится отдельный M0 discovery.

Разработчику нельзя:

- обходить CAPTCHA;
- обходить авторизацию;
- обходить rate limits;
- использовать прокси как способ обхода запрета;
- скрывать реальный характер автоматического клиента.

Нужно:

- проверить актуальные правила площадки;
- проверить `robots.txt`;
- использовать лимиты;
- делать задержки;
- логировать `403`, `429`, `5xx`;
- выключать источник при массовых блокировках;
- сохранять ошибку в `parser_errors`.

Если допустимость и работоспособность источника не подтверждены, реализацию БД, UI и дашбордов не начинать. Допустима только аналитика и технический spike по Avito.

## 9. UI Требования

Интерфейс должен соответствовать текущему спокойному операционному стилю проекта.

Не делать:

- маркетинговый landing;
- отдельный SPA;
- декоративные dashboard-карточки без пользы;
- крупные hero-блоки;
- перегруженные графики.

Сделать:

- плотный список позиций;
- понятные фильтры;
- компактный график;
- таблицу истории;
- явные статусы `ok`, `no_data`, `failed`;
- ссылки на объявления;
- журнал запусков;
- журнал ошибок.

## 10. Порядок Реализации

Рекомендуемый порядок:

1. M0 discovery Avito API.
2. Если API не покрывает поиск рыночных объявлений - M0 spike HTML-парсинга.
3. Зафиксировать минимальный набор данных, который реально удаётся получить: цена, ссылка, заголовок, регион, дата наблюдения, внешний идентификатор при наличии.
4. Зафиксировать ограничения: лимиты, блокировки, CAPTCHA, маппинг региона, стабильность HTML.
5. Принять gate-решение: реализуем модуль на подтверждённом источнике или не стартуем разработку.
6. Только после успешного gate - миграция и модели.
7. Репозитории.
8. Сервис дневных срезов.
9. CRUD позиций.
10. Реальный адаптер источника.
11. Журнал запусков.
12. Дашборд и история.
13. CSV-экспорт.
14. Scheduler.
15. Приёмочные проверки.

Причина такого порядка: без рабочего источника данных базовые компоненты нечем наполнять, поэтому БД и UI не имеют практического смысла.

## 11. Тесты

Минимальные backend-тесты:

- создание позиции;
- архивирование позиции;
- расчёт дневного среза по набору цен;
- расчёт медианы для нечётного количества цен;
- расчёт медианы для чётного количества цен;
- создание `no_data`;
- создание `failed`;
- ошибка одной позиции не ломает запуск всех позиций;
- CSV-экспорт содержит ожидаемые строки.

Минимальные route/smoke-тесты:

- `/pricing`;
- `/pricing/items`;
- `/pricing/items/new`;
- `/pricing/dashboard`;
- `/pricing/runs`;
- `/pricing/errors`;
- `/pricing/health`.

Минимальные parser-тесты:

- нормализация цены;
- пустая выдача;
- ошибка региона;
- HTTP 403;
- HTTP 429;
- изменение структуры страницы обрабатывается ошибкой, а не падением всего запуска.

## 12. Команды Проверки

После реализации:

```bash
.venv/bin/python -m compileall app scripts
.venv/bin/ruff check app scripts
.venv/bin/alembic upgrade head
.venv/bin/python -c "from scripts.check_mvp_acceptance import main; raise SystemExit(main())"
```

Для модуля оценщика добавить отдельный acceptance script:

```text
scripts/check_price_monitoring_acceptance.py
```

Он должен:

- создать тестовую категорию;
- создать тестовую позицию;
- создать набор тестовых наблюдений;
- пересчитать дневной срез;
- проверить графиковые данные;
- проверить CSV;
- удалить тестовые данные.

## 13. Seed-Данные

Добавить seed только для dev/demo режима.

Рекомендуемые стартовые позиции:

- `Kyocera ECOSYS M2040dn`;
- `HP LaserJet Pro MFP M426`;
- `Lenovo ThinkPad T14`;
- `Dell PowerEdge R740`;
- `Dell P2419H`.

Seed не должен запускать реальный внешний сбор.

Для демонстрации графика можно создать искусственную историю за 30 дней через отдельный demo seed или acceptance script.

## 14. Конфигурация

Добавить параметры:

```text
PRICE_MONITORING_ENABLED=true
PRICE_MONITORING_SCHEDULE=09:00
PRICE_MONITORING_DEFAULT_LIMIT=50
PRICE_MONITORING_REQUEST_DELAY_SECONDS=3
PRICE_MONITORING_SOURCE=avito
```

Для реального источника:

```text
AVITO_REQUEST_TIMEOUT_SECONDS=15
AVITO_USER_AGENT=...
```

Не хранить секреты в коде. Если появится API-ключ, хранить только в `.env`.

## 15. Acceptance Criteria

Разработка считается завершённой, если:

- текущий MVP acceptance script проходит;
- новые таблицы создаются миграцией;
- раздел `/pricing` доступен центру;
- региональный пользователь не имеет доступа к `/pricing`;
- администратор создаёт позицию;
- позицию можно архивировать;
- ручной запуск создаёт run;
- по тестовым наблюдениям создаётся дневной срез;
- день без объявлений записывается как `no_data`;
- ошибка источника записывается как `failed`;
- график показывает `min`, `max`, `median`;
- CSV экспортируется;
- журнал запусков и ошибок доступен;
- код Avito изолирован в parser-модуле;
- нет автоматического изменения цены продажи в карточке оборудования.

## 16. Что Не Делать В Первой Реализации

Не делать:

- ML-рекомендацию цены;
- автоматическую публикацию продажи;
- автоматическое изменение карточки оборудования;
- сравнение регионов;
- несколько источников одновременно;
- несколько поисковых запросов на одну позицию;
- Excel-экспорт;
- Telegram/email-уведомления;
- Celery/Redis;
- ручное исключение объявления из расчёта;
- полноценную роль `valuer`, если её не утвердили отдельно.
