# Runbook Day 2: Оценщик Avito Endurance

Дата подготовки: 2026-06-18
Дата запуска: 2026-06-19 или позже

Цель: выполнить второй live run endurance-проверки без лишней нагрузки на Avito и без обхода ограничений доступа.

## Правила

- Делать не больше одного live run в UTC-день.
- Не использовать cookies, proxy, CAPTCHA bypass или агрессивные повторы.
- Если `kyocera_m2040dn` снова получает `HTTP 403`, считать это подтверждением нестабильности HTTP-доступа, а не ошибкой оператора.
- Если preflight блокирует запуск из-за same-day guard, live run не выполнять.
- Не коммитить `runs/`, `.venv/`, `config/search_jobs.json` и runtime HTML/JSON snapshots.

## Подготовка

Перейти в POC:

```bash
cd research/avito-monitor-worker-poc
```

Если локального runtime config нет, создать его из примера:

```bash
cp config/search_jobs.example.json config/search_jobs.json
```

Проверить, что в `config/search_jobs.json` есть три job:

```text
kyocera_m2040dn
lenovo_t14
dell_r740
```

Для `dell_r740` должен использоваться широкий URL:

```text
https://www.avito.ru/all?q=Dell+PowerEdge+R740
```

## Offline-Проверки

Перед live run выполнить:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

Ожидаемый preflight перед day 2:

```text
status: ready
```

Если preflight возвращает `blocked_by_same_day_guard`, остановиться и перенести запуск на следующий UTC-день.

## Live Run

Запускать только после успешного preflight:

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

Сохранить `run_id` из вывода команды.

## Разбор Результата

Для нового `run_id` выполнить:

```bash
.venv/bin/python src/worker.py --analyze-run runs/{run_id}
.venv/bin/python src/worker.py --write-markdown-report runs/{run_id} --output runs/{run_id}/offline_report.md
.venv/bin/python src/worker.py --write-endurance-doc runs/{run_id} --output ../../local/docs/34_price_monitoring_endurance_day_2.md --day 2 --date 2026-06-19
.venv/bin/python src/worker.py --write-gate-summary --runs-dir runs --output ../../local/docs/37_price_monitoring_gate_summary.md
```

Проверить:

```text
local/docs/34_price_monitoring_endurance_day_2.md
local/docs/37_price_monitoring_gate_summary.md
runs/{run_id}/offline_report.md
```

## Оценка Day 2

Day 2 можно считать полезным, если:

- хотя бы одна позиция получила `HTTP 200` и валидные `relevant` объявления;
- `dell_r740` больше не классифицируется как `no_data` из-за `page_not_found`;
- блокировки и parser errors явно отражены в generated docs;
- gate summary показывает, можно ли продолжать endurance или нужно остановиться.

## Решение После Day 2

Варианты:

- `continue_endurance_with_caution`: есть хотя бы один стабильный успешный источник и нет новых критичных проблем.
- `hold_http_unstable`: большинство job блокируются или дают parser errors.
- `browser_profile_research`: HTTP worker недостаточно стабилен, нужен отдельный research browser-профиля.
- `go_worker_prototype`: выбирать только после 3-5 дней, если gate criteria выполнены.

