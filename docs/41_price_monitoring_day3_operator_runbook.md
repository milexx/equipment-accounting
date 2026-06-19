# Runbook Day 3: Оценщик Avito Endurance

Дата подготовки: 2026-06-19
Дата запуска: 2026-06-20 или позже

Цель: выполнить третий official endurance day и проверить, повторяется ли успешность Day 2 без увеличения частоты запросов.

## Правила

- Не больше одного live Avito run в UTC-день.
- Не использовать cookies, proxy, CAPTCHA bypass или retry loop.
- Перед live run обязательно выполнить preflight.
- Если preflight возвращает `blocked_by_same_day_guard`, live run не выполнять.
- Runtime `runs/`, `.venv/` и `config/search_jobs.json` не коммитить.

## Перед Запуском

```bash
cd research/avito-monitor-worker-poc
.venv/bin/python -m unittest discover -s tests
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

Ожидаемый preflight:

```text
status: ready
```

## Live Run

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

Сохранить новый `run_id`.

## После Запуска

```bash
.venv/bin/python src/worker.py --analyze-run runs/{run_id}
.venv/bin/python src/worker.py --write-markdown-report runs/{run_id} --output runs/{run_id}/offline_report.md
.venv/bin/python src/worker.py --write-endurance-doc runs/{run_id} --output ../../docs/44_price_monitoring_endurance_day_3.md --day 3 --date 2026-06-20
.venv/bin/python src/worker.py --write-gate-summary --runs-dir runs --output ../../docs/37_price_monitoring_gate_summary.md
```

## Day 3 Questions

1. `kyocera_m2040dn`: сохраняется ли `HTTP 200 success` после Day 1 `HTTP 403`?
2. `lenovo_t14`: остаётся ли relevant count около 30 и медиана около 28-30 тыс.?
3. `dell_r740`: растёт ли relevant count после смягчения negative terms?
4. Есть ли повторные `HTTP 403`, `HTTP 429`, CAPTCHA или parser errors?

## Решение После Day 3

Варианты:

- `continue_endurance_day_4`: Day 3 полезен, но evidence ещё недостаточно.
- `go_worker_prototype_candidate`: 3 official days, минимум 2 дня с 2+ успешными job, нет доминирования блокировок и фильтры приемлемы.
- `hold_http_unstable`: большинство job снова блокируется или ломается.
- `adjust_filters_offline`: HTTP доступ есть, но качество relevant/unknown/rejected недостаточно.

Даже при `go_worker_prototype_candidate` сначала подготовить итоговый gate decision doc, затем начинать backend-модели.

