# Fallback Chain Runbook

Date: 2026-06-21

## Scope

Manual run for the pricing fallback chain:

```text
Avito -> Duff89/parser_avito -> Youla
```

This runbook is for the next controlled test window. It does not authorize scheduler or repeated background runs.

## Preflight

Run from:

```text
/opt/workspace/projects/equipment-accounting/research/avito-monitor-worker-poc
```

Check config:

```bash
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
```

Expected:

```text
block_diagnostic_enabled: true
youla_fallback_enabled: true
```

Check same-day guard:

```bash
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

If status is `blocked_by_same_day_guard`, do not run unless this is an explicitly approved controlled override.

## Manual Run

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

Do not repeat the run on the same UTC day after an Avito block.

## After Run

Analyze latest run:

```bash
.venv/bin/python src/worker.py --analyze-run runs/<RUN_ID>
```

Generate markdown report:

```bash
.venv/bin/python src/worker.py --analyze-run runs/<RUN_ID> --write-markdown-report --output runs/<RUN_ID>/offline_report.md
```

Check per job:

- `job_report.json`
- `daily_snapshot.json`
- `relevant_listings.json`
- `unknown_listings.json`
- `rejected_listings.json`
- `block_diagnostic.json`, if Avito was blocked
- `duff89_normalized_listings.json`, if Duff89 ran
- `youla_fallback_report.json`, if Youla ran

## Acceptance Criteria

For each monitored item, record:

- final `status`;
- final `source`;
- `primary_status`, if fallback was used;
- `primary_http_status`, if fallback was used;
- `relevant_count`;
- `unknown_count`;
- `rejected_count`;
- median price, if available.

Useful outcomes:

- `source: avito` means primary worker succeeded.
- `source: avito_duff89` means Avito failed but Duff89 returned usable listings.
- `source: youla` means Avito and Duff89 failed but Youla returned usable listings.

Problem outcomes:

- `blocked` / `captcha`: source unavailable.
- `parser_error`: source response could not be parsed.
- `no_data`: source returned data, but no relevant listings survived filters.

## Import To Database

Import only after reviewing the run directory:

```bash
cd /opt/workspace/projects/equipment-accounting
.venv/bin/python scripts/import_price_poc_run.py research/avito-monitor-worker-poc/runs/<RUN_ID>
```

The importer now preserves actual snapshot/listing source:

- `avito`
- `avito_duff89`
- `youla`

Blocked Avito is not imported as a price point if fallback produced a successful snapshot. It remains preserved in run/job raw reports.

## UI Check

Open:

```text
http://185.168.208.240:8010/pricing
```

Verify:

- chart point list shows source code;
- journal has a separate `Источник` column;
- fallback price points are not mislabeled as `avito`.

## Decision After Run

Choose one:

- `keep_fallback_chain_for_mvp`: chain gives useful relevant snapshots.
- `adjust_filters_then_retry_next_day`: source works, but relevance is noisy.
- `hold_source_unstable`: all sources blocked or unusable.
- `youla_only_manual_experiment`: Avito/Duff89 remain blocked, Youla is the only useful fallback.
