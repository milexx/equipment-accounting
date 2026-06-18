# Проект Схемы БД Модуля Оценщика

Дата: 2026-06-18.

Статус: предварительный проект для этапа C. Это не Alembic-миграция и не разрешение начинать backend-разработку до gate `go_worker_prototype`.

Связанные документы:

- `docs/14_price_monitoring_module.md`;
- `docs/17_price_monitoring_developer_handoff.md`;
- `docs/32_price_monitoring_implementation_plan.md`;
- `docs/33_price_monitoring_endurance_day_1.md`;
- `docs/34_price_monitoring_endurance_day_2_plan.md`.

## 1. Правило Gate

Схема ниже нужна, чтобы заранее снять архитектурные вопросы, но таблицы не создавать до решения:

```text
go_worker_prototype
```

Если endurance test приводит к `hold_http_unstable`, этот документ остаётся research-материалом и не переносится в основное приложение.

## 2. Принципы

- Модуль живёт отдельно от текущих таблиц MVP.
- Карточки `equipment` не меняются в первом релизе.
- Источник данных хранится отдельной сущностью.
- Сырые объявления и дневные агрегаты хранятся отдельно.
- Графики строятся по `daily_price_snapshots`, а не по сырым объявлениям.
- `unknown` объявления не участвуют в min/max/median, но сохраняются для ручной проверки.
- `rejected` объявления сохраняются для аудита фильтра и настройки правил.
- Повторный пересчёт одного дня должен обновлять один snapshot, а не создавать дубль.
- Ошибки источника и ошибки позиции фиксируются явно.

## 3. Статусы

На первом этапе рекомендуется использовать `TEXT + CHECK`, а не PostgreSQL enum, чтобы не усложнять изменения во время pilot.

### `price_scrape_run.status`

```text
running
success
partial_failed
failed
cancelled
```

### `daily_price_snapshot.status`

```text
success
no_data
source_blocked
parser_error
failed
```

### `price_observations.relevance_status`

```text
relevant
unknown
rejected
```

### `parser_errors.error_type`

```text
http_403
http_429
captcha
access_restricted
page_not_found
parser_error
timeout
network_error
invalid_config
unknown
```

## 4. Таблицы

### `price_categories`

Назначение: группировка отслеживаемых позиций.

```sql
CREATE TABLE price_categories (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `market_sources`

Назначение: настройка источников данных.

```sql
CREATE TABLE market_sources (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    daily_limit INTEGER,
    request_delay_seconds INTEGER NOT NULL DEFAULT 5,
    timeout_seconds INTEGER NOT NULL DEFAULT 20,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Первый seed:

```text
code: avito
name: Avito
request_delay_seconds: 5
timeout_seconds: 20
```

### `monitored_items`

Назначение: рыночная позиция, по которой собираются цены.

```sql
CREATE TABLE monitored_items (
    id BIGSERIAL PRIMARY KEY,
    category_id BIGINT REFERENCES price_categories(id),
    name TEXT NOT NULL,
    brand TEXT,
    model TEXT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_query TEXT NOT NULL,
    search_region TEXT NOT NULL DEFAULT 'Россия',
    source_limit INTEGER NOT NULL DEFAULT 50,
    required_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    positive_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    negative_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    price_min NUMERIC(14, 2),
    price_max NUMERIC(14, 2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at TIMESTAMPTZ,
    created_by_user_id BIGINT REFERENCES users(id),
    updated_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_monitored_items_source_limit_positive CHECK (source_limit > 0),
    CONSTRAINT chk_monitored_items_price_bounds CHECK (
        price_min IS NULL
        OR price_max IS NULL
        OR price_min < price_max
    )
);
```

В первом релизе `required_terms`, `positive_terms`, `negative_terms`, `price_min`, `price_max` повторяют проверенную модель POC.

### `price_scrape_runs`

Назначение: один запуск сбора по источнику.

```sql
CREATE TABLE price_scrape_runs (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES market_sources(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    items_total INTEGER NOT NULL DEFAULT 0,
    items_success INTEGER NOT NULL DEFAULT 0,
    items_no_data INTEGER NOT NULL DEFAULT 0,
    items_blocked INTEGER NOT NULL DEFAULT 0,
    items_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    runtime_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by_user_id BIGINT REFERENCES users(id),
    CONSTRAINT chk_price_scrape_runs_status CHECK (
        status IN ('running', 'success', 'partial_failed', 'failed', 'cancelled')
    )
);
```

### `price_observations`

Назначение: сохранённые объявления.

```sql
CREATE TABLE price_observations (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL REFERENCES monitored_items(id),
    source_id BIGINT NOT NULL REFERENCES market_sources(id),
    run_id BIGINT NOT NULL REFERENCES price_scrape_runs(id),
    observed_at TIMESTAMPTZ NOT NULL,
    listing_external_id TEXT,
    listing_url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price NUMERIC(14, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'RUB',
    location TEXT,
    published_at TIMESTAMPTZ,
    relevance_status TEXT NOT NULL,
    relevance_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_price_observations_price_positive CHECK (price >= 0),
    CONSTRAINT chk_price_observations_relevance_status CHECK (
        relevance_status IN ('relevant', 'unknown', 'rejected')
    )
);
```

Дедупликация:

```sql
CREATE UNIQUE INDEX uq_price_observations_source_external_run
ON price_observations(source_id, listing_external_id, run_id)
WHERE listing_external_id IS NOT NULL;

CREATE UNIQUE INDEX uq_price_observations_source_url_run
ON price_observations(source_id, listing_url, run_id);
```

Причина уникальности по `run_id`: одно и то же объявление может попадать в разные дни, и это важно для истории.

### `daily_price_snapshots`

Назначение: дневной агрегат для графиков и отчётов.

```sql
CREATE TABLE daily_price_snapshots (
    id BIGSERIAL PRIMARY KEY,
    item_id BIGINT NOT NULL REFERENCES monitored_items(id),
    source_id BIGINT NOT NULL REFERENCES market_sources(id),
    run_id BIGINT REFERENCES price_scrape_runs(id),
    snapshot_date DATE NOT NULL,
    status TEXT NOT NULL,
    raw_count INTEGER NOT NULL DEFAULT 0,
    normalized_count INTEGER NOT NULL DEFAULT 0,
    relevant_count INTEGER NOT NULL DEFAULT 0,
    unknown_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    min_price NUMERIC(14, 2),
    max_price NUMERIC(14, 2),
    avg_price NUMERIC(14, 2),
    median_price NUMERIC(14, 2),
    currency TEXT NOT NULL DEFAULT 'RUB',
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    error_type TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_daily_price_snapshots_status CHECK (
        status IN ('success', 'no_data', 'source_blocked', 'parser_error', 'failed')
    ),
    CONSTRAINT uq_daily_price_snapshots_item_source_date
        UNIQUE (item_id, source_id, snapshot_date)
);
```

Правило расчёта:

- `min_price`, `max_price`, `avg_price`, `median_price` считаются только по `price_observations.relevance_status = 'relevant'`;
- если relevant нет, но source отработал, статус `no_data`;
- если источник заблокирован, статус `source_blocked`;
- если HTML/парсер сломался, статус `parser_error`.

### `parser_errors`

Назначение: журнал ошибок источника и конкретных позиций.

```sql
CREATE TABLE parser_errors (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT REFERENCES market_sources(id),
    item_id BIGINT REFERENCES monitored_items(id),
    run_id BIGINT REFERENCES price_scrape_runs(id),
    error_type TEXT NOT NULL,
    http_status INTEGER,
    message TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_parser_errors_error_type CHECK (
        error_type IN (
            'http_403',
            'http_429',
            'captcha',
            'access_restricted',
            'page_not_found',
            'parser_error',
            'timeout',
            'network_error',
            'invalid_config',
            'unknown'
        )
    )
);
```

## 5. Индексы

```sql
CREATE INDEX idx_monitored_items_active_category
ON monitored_items(is_active, category_id);

CREATE INDEX idx_monitored_items_brand_model
ON monitored_items(brand, model);

CREATE INDEX idx_monitored_items_search_region
ON monitored_items(search_region);

CREATE INDEX idx_price_scrape_runs_source_started
ON price_scrape_runs(source_id, started_at DESC);

CREATE INDEX idx_price_observations_item_observed
ON price_observations(item_id, observed_at DESC);

CREATE INDEX idx_price_observations_source_external
ON price_observations(source_id, listing_external_id)
WHERE listing_external_id IS NOT NULL;

CREATE INDEX idx_price_observations_relevance
ON price_observations(item_id, source_id, relevance_status, observed_at DESC);

CREATE INDEX idx_daily_price_snapshots_item_date
ON daily_price_snapshots(item_id, snapshot_date DESC);

CREATE INDEX idx_daily_price_snapshots_source_date
ON daily_price_snapshots(source_id, snapshot_date DESC);

CREATE INDEX idx_parser_errors_run
ON parser_errors(run_id, created_at DESC);

CREATE INDEX idx_parser_errors_item
ON parser_errors(item_id, created_at DESC);

CREATE INDEX idx_parser_errors_type
ON parser_errors(error_type, created_at DESC);
```

## 6. Snapshot Upsert

Дневной snapshot должен записываться через upsert по:

```text
item_id + source_id + snapshot_date
```

Правило:

- новый run за тот же день обновляет существующий snapshot;
- `run_id` меняется на последний run, который дал текущие значения;
- старые `price_observations` не удаляются автоматически;
- при необходимости очистки дублей это отдельная maintenance-задача после pilot.

## 7. Хранение Raw HTML

Raw HTML не хранится в БД.

Рекомендуемый runtime path:

```text
var/pricing/raw/{run_id}/{item_code}/page_1.html
```

В БД можно хранить только `parser_errors.raw_path`, если ошибка требует последующей диагностики.

Raw HTML не должен попадать в git.

## 8. Будущая Связь С Equipment

В первом релизе не добавлять связь с `equipment`.

После pilot возможна отдельная таблица:

```sql
CREATE TABLE equipment_pricing_links (
    id BIGSERIAL PRIMARY KEY,
    equipment_id BIGINT NOT NULL REFERENCES equipment(id),
    monitored_item_id BIGINT NOT NULL REFERENCES monitored_items(id),
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (equipment_id, monitored_item_id)
);
```

Но её не включать в первый релиз, чтобы не менять текущие сценарии MVP.

## 9. Открытые Вопросы Перед Миграцией

1. Нужна ли отдельная роль `valuer` или достаточно `center` / `center_admin`.
2. Хранить ли `raw_payload` целиком или ограничить whitelist полей.
3. Какой retention для `price_observations`: бессрочно, 1 год, 2 года.
4. Нужен ли отдельный manual CSV source в первом релизе как fallback.
5. Где хранить raw HTML в production: локальный диск, object storage или не хранить после успешного parsing.
