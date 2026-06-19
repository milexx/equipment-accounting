# Post-Gate Integration Backlog: Оценщик

Дата: 2026-06-19

Статус: backlog только после решения `go_worker_prototype`.

До `go_worker_prototype` не начинать:

- backend-модели;
- Alembic migrations;
- UI `/pricing`;
- scheduler в основном приложении.

## Phase 1: Data Model

Файлы:

```text
app/models/pricing.py
alembic/versions/{revision}_add_pricing_tables.py
```

Таблицы:

- `price_categories`;
- `monitored_items`;
- `market_sources`;
- `price_scrape_runs`;
- `price_observations`;
- `daily_price_snapshots`;
- `parser_errors`.

Критерии:

- `alembic upgrade head` создаёт таблицы;
- один monitored item может иметь много observations;
- daily snapshot уникален по item/source/date;
- `no_data`, `blocked`, `parser_error` сохраняются явно.

## Phase 2: Service Layer

Файлы:

```text
app/services/pricing/
```

Минимальные сервисы:

- create/update/archive monitored item;
- save scrape run;
- save observations;
- calculate daily snapshot from relevant observations;
- record parser errors.

Критерии:

- повторный пересчёт snapshot за день обновляет одну запись;
- unknown/rejected observations не участвуют в median;
- rejected/unknown reasons доступны для аудита.

## Phase 3: Parser Adapter

Файлы:

```text
app/services/pricing_parsers/base.py
app/services/pricing_parsers/registry.py
app/services/pricing_parsers/avito.py
```

Требования:

- переносить только clean-room код из POC;
- Avito logic изолировать внутри adapter;
- stop-on-block для `403`, `429`, CAPTCHA, access restricted;
- без proxy rotation, cookies и CAPTCHA bypass;
- raw HTML писать только в runtime path вне git.

## Phase 4: Admin UI `/pricing`

Routes:

- `GET /pricing`;
- `GET /pricing/items/new`;
- `POST /pricing/items`;
- `GET /pricing/items/{id}`;
- `GET /pricing/items/{id}/edit`;
- `POST /pricing/items/{id}`;
- `POST /pricing/items/{id}/archive`;
- `POST /pricing/items/{id}/run`;
- `GET /pricing/runs`;
- `GET /pricing/runs/{id}`;
- `GET /pricing/items/{id}/export.csv`.

Roles:

- `center_admin`: manage items and run parser manually;
- `center`: view dashboard and export;
- `region`: no access in first release.

## Phase 5: Reporting

Минимум:

- table of daily min/max/median;
- listing count by status;
- parser error log;
- CSV export for daily snapshots;
- CSV export for observations.

График можно добавить после таблицы, не блокировать первый prototype.

## Phase 6: Scheduler

Для demo/dev:

- manual run first;
- optional systemd timer or internal command.

Для production:

- separate worker or systemd timer;
- lock against parallel runs;
- one scheduled window per day;
- stop-on-block, no retry loop.

## Acceptance Before Pilot

- Создано 10-20 monitored items.
- Ручной run одной позиции работает.
- Ручной run всех активных позиций работает.
- Видны статусы `success`, `no_data`, `blocked`, `parser_error`.
- Median считается только по relevant observations.
- Unknown/rejected доступны для проверки.
- CSV открывается в LibreOffice/Excel.
- Права `center_admin` и `center` работают.

