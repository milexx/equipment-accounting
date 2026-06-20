# Backend Skeleton Checklist: Оценщик

Дата: 2026-06-20

Статус: implementation checklist после `go_worker_prototype_candidate_with_constraints`.

Этот документ не запускает реализацию сам по себе. Он фиксирует порядок работ, если принято explicit approval на backend prototype.

## Preconditions

Перед началом кода подтвердить:

- gate decision прочитан: `docs/45_price_monitoring_gate_decision_after_day_3.md`;
- Avito остаётся unstable experimental source;
- первый prototype начинается с backend/data model, не с UI;
- scheduler не включается в первом backend-шаге;
- manual run only;
- raw HTML не попадает в git.

## Step 1: Models

Создать:

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

## Step 2: Migration

Создать Alembic revision:

```text
alembic/versions/{revision}_add_pricing_tables.py
```

Acceptance:

- `alembic upgrade head` проходит;
- `alembic downgrade -1` проходит, если проект поддерживает downgrade;
- unique constraint prevents duplicate daily snapshot for same item/source/date;
- indexes exist for item/date/source and run status.

## Step 3: Services

Создать service package:

```text
app/services/pricing/
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

## Step 5: Manual Command

Добавить backend command or script for manual run:

```text
run one monitored item
run all active monitored items
```

Acceptance:

- one failed job does not stop all jobs;
- command writes `PriceScrapeRun`;
- command writes observations/snapshot or parser error;
- command prints concise run summary.

## Step 6: Tests

Minimum tests:

- snapshot median uses only relevant observations;
- repeated daily snapshot update is idempotent;
- blocked parser result persists as run/job error;
- parser adapter stop-on-block behavior;
- permissions/ownership for monitored item service.

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

