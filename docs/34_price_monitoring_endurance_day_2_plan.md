# Endurance Test Оценщика: План Дня 2

Дата запуска: 2026-06-19 или позже.

Статус: `planned`.

Важно:

```text
Не запускать live Avito run 2026-06-18 повторно.
```

## Цель

Проверить, повторяются ли результаты day 1 при одном осторожном live-запуске в следующий день.

Особое внимание:

- повторится ли `HTTP 403` по `kyocera_m2040dn`;
- сохранится ли успешный сбор по `lenovo_t14`;
- даст ли `dell_r740` данные после замены URL на более широкий `/all?q=Dell+PowerEdge+R740`.

## Изменения Перед Day 2

Без live-проверки подготовлено:

- `dell_r740.search_url` изменён с `/all/servernoe_oborudovanie?q=...` на `/all?q=...`;
- причина: day 1 HTML содержал страницу `Такой страницы не существует`, то есть category URL был неподходящим;
- worker доработан: future `page_not_found` будет классифицироваться как `parser_error`, а не как `no_data`;
- добавлен offline-анализатор run:

```bash
.venv/bin/python src/worker.py --analyze-run runs/{run_id}
```

## Команда Запуска

Из `research/avito-monitor-worker-poc/`:

Сначала офлайн-проверки без сети:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

Затем один live run:

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

Worker остановит повторный live run в тот же UTC-день со статусом `blocked_by_same_day_guard`.

После live run сформировать offline-анализ и markdown-таблицу:

```bash
.venv/bin/python src/worker.py --analyze-run runs/{run_id}
.venv/bin/python src/worker.py --write-markdown-report runs/{run_id} --output runs/{run_id}/offline_report.md
.venv/bin/python src/worker.py --write-endurance-doc runs/{run_id} --output ../../local/docs/34_price_monitoring_endurance_day_2.md --day 2 --date 2026-06-19
.venv/bin/python src/worker.py --write-gate-summary --runs-dir runs --output ../../local/docs/37_price_monitoring_gate_summary.md
```

Если перед запуском локальный ignored config устарел:

```bash
cp config/search_jobs.example.json config/search_jobs.json
```

## Правила

- один live run в день;
- не делать retry при `blocked`, `captcha`, `403`, `429` или `page_not_found`;
- не использовать `--allow-same-day-live`, кроме инфраструктурного сбоя до обращения к Avito;
- не использовать cookies;
- не использовать proxy;
- не обходить CAPTCHA;
- сохранить raw runtime только в ignored `runs/`;
- в git добавить только отчёт day 2.

## Шаблон Результатов

```text
run_id:
started_at:
finished_at:
status:
jobs_total:
jobs_success:
jobs_blocked:
jobs_failed:
```

| Позиция | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median | Findings |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `kyocera_m2040dn` | | | | | | | | | | | |
| `lenovo_t14` | | | | | | | | | | | |
| `dell_r740` | | | | | | | | | | | |

## Решение После Day 2

Варианты:

- `continue_endurance_day_3` - если минимум 2 позиции дают пригодные данные и блокировки не доминируют;
- `hold_http_unstable` - если блокировки повторяются или валидные данные остаются только по одной позиции;
- `adjust_queries_offline` - если проблема только в URL/категориях, а не в блокировке.
