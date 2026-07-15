# Backend Skeleton Checklist: Оценщик

Дата: 2026-06-20

Статус: backend skeleton implemented после `go_worker_prototype_candidate_with_constraints`.

Этот документ фиксировал порядок работ. На 2026-06-20 первый backend skeleton выполнен в ограниченном scope: модели, миграция, сервис импорта сохранённых POC-run, focused tests. UI, scheduler и live parser integration не включались.

## Preconditions

Перед началом кода подтвердить:

- gate decision прочитан: `local/docs/45_price_monitoring_gate_decision_after_day_3.md`;
- Avito остаётся unstable experimental source;
- первый prototype начинается с backend/data model, не с UI;
- scheduler не включается в первом backend-шаге;
- manual run only;
- raw HTML не попадает в git.

## Step 1: Models

Создано:

```text
app/models/pricing.py
```

Минимальные модели:

- `PriceCategory`;
- `MonitoredItem`;
- `MarketSource`;
- `PriceScrapeRun`;
- `PriceObservation`;
- `DailyPriceSnapshot`;
- `ParserError`.

Обязательные поля:

- tenant/center ownership where applicable;
- status fields for `success`, `no_data`, `blocked`, `captcha`, `parser_error`;
- timestamps for started/finished/fetched;
- source code, job code, external id;
- relevance status and reject reasons;
- min/max/median daily snapshot.

Implementation status: done.

## Step 2: Migration

Создана Alembic revision:

```text
alembic/versions/20260620_0005_add_pricing_tables.py
```

Acceptance:

- `alembic upgrade head` проходит;
- `alembic downgrade -1` проходит, если проект поддерживает downgrade;
- unique constraint prevents duplicate daily snapshot for same item/source/date;
- indexes exist for item/date/source and run status.

Implementation status: partially done.

- `alembic upgrade head` applied on dev DB.
- Current DB revision: `20260620_0005`.
- Unique constraints added for daily snapshots and imported observations.
- Explicit secondary indexes are deferred until query patterns are known.

## Step 3: Services

Создан service module:

```text
app/services/pricing_service.py
```

Минимальные функции:

- create monitored item;
- update monitored item;
- archive monitored item;
- create scrape run;
- save observations;
- classify observation status;
- calculate daily snapshot;
- record parser error.

Acceptance:

- daily snapshot calculated only from `relevant`;
- `unknown` and `rejected` retained for audit;
- repeated recalculation updates same daily snapshot;
- blocked/no_data/parser_error runs are visible and persisted.

Implementation status: done for first backend skeleton.

- `PricingService.import_poc_run(...)` imports saved POC run artifacts.
- `PriceScrapeRun`, `PriceObservation`, `DailyPriceSnapshot`, `ParserError` are persisted.
- Re-import of the same `external_run_id` is idempotent for run children.
- Blocked job persists as `ParserError` and blocked daily snapshot.
- Every run keeps its own snapshots; multiple runs for the same item/source/date are preserved by `scrape_run_id`.

## Step 4: Parser Contract

Создать:

```text
app/services/pricing_parsers/base.py
app/services/pricing_parsers/registry.py
app/services/pricing_parsers/avito.py
```

Contract:

```text
fetch(job) -> ParserResult
```

`ParserResult` должен поддерживать:

- observations;
- raw status;
- blocked/captcha/parser_error/no_data;
- error reason;
- source metadata;
- runtime artifact path for raw HTML.

Acceptance:

- Avito adapter can be disabled without breaking pricing module;
- block status stops the current job;
- no retry loop on block;
- no cookies/proxy/CAPTCHA bypass.

Implementation status: deferred.

Parser contract files are not created yet. The first backend skeleton intentionally imports saved POC artifacts only and does not call Avito.

## Step 5: Manual Command

Добавлен backend import script for saved POC run:

```text
scripts/import_price_poc_run.py
```

Acceptance:

- one failed job does not stop all jobs;
- command writes `PriceScrapeRun`;
- command writes observations/snapshot or parser error;
- command prints concise run summary.

Проверенная operator-команда в текущем окружении:

```bash
.venv/bin/python -c "import os, sys; os.chdir('/opt/workspace/projects/equipment-accounting'); from scripts.import_price_poc_run import main; sys.argv=['import_price_poc_run.py','research/avito-monitor-worker-poc/runs/20260620T081446Z']; raise SystemExit(main())"
```

Прямой запуск `python scripts/import_price_poc_run.py ...` в текущем sandbox окружении ловил `psycopg.OperationalError: connection is bad` до первого SQL. Сервисный import path выше проверен и использован.

Implementation status: done for saved POC artifacts, deferred for live/manual parser run.

## Step 6: Tests

Minimum tests:

- snapshot median uses only relevant observations;
- repeated daily snapshot update is idempotent;
- blocked parser result persists as run/job error;
- parser adapter stop-on-block behavior;
- permissions/ownership for monitored item service.

Implementation status: partially done.

- Added `tests/test_pricing_service.py`.
- Covered import success+blocked, idempotent re-import, snapshot min/max/median.
- Covered multiple same-day runs for the same item without overwriting historical snapshots.
- Parser adapter and permissions tests are deferred because parser contract/UI are out of current scope.

## Explicitly Out Of Scope For First Backend Skeleton

- `/pricing` UI;
- charts;
- CSV export;
- scheduler;
- automatic daily runs;
- region access;
- browser-profile source;
- paid providers.

## Exit Criteria

Backend skeleton is complete when:

- migrations apply;
- services can create item and save one synthetic run;
- one manual command can execute a fake/parser fixture source;
- tests cover snapshot calculation and blocked/error persistence;
- no live Avito call is required for backend tests.

Current exit status:

- migrations apply: done;
- services can create item and save one imported run: done;
- manual command for saved POC run: done via verified import-mode command;
- tests cover snapshot calculation and blocked/error persistence: done;
- no live Avito call required: done.
