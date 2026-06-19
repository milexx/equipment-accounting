# Sessions

## 2026-06-18

Контекст: продолжение работы по проекту `equipment-accounting`, ветка `dev`, направление "Оценщик"/Avito price monitoring research.

Что сделано:

- Выполнен Day 1 endurance live run POC Avito worker.
- Зафиксирован результат Day 1: `kyocera_m2040dn` получил `HTTP 403`, `lenovo_t14` успешно собрал объявления, `dell_r740` уточнён как `page_not_found` при `HTTP 200`.
- Добавлен offline-анализ сохранённых run snapshots.
- Добавлена генерация markdown offline report, endurance day doc и gate summary.
- Добавлен guard от повторного live run в тот же UTC-день.
- Подготовлены gate checklist, предварительный database design без миграций, Day 2 operator runbook и risk/decision matrix.

Ключевые файлы:

- `docs/33_price_monitoring_endurance_day_1.md`
- `docs/34_price_monitoring_endurance_day_2_plan.md`
- `docs/35_price_monitoring_database_design.md`
- `docs/36_price_monitoring_gate_acceptance.md`
- `docs/38_price_monitoring_day2_operator_runbook.md`
- `docs/39_price_monitoring_risk_and_decision_matrix.md`
- `docs/continuation.md`
- `research/avito-monitor-worker-poc/src/worker.py`
- `research/avito-monitor-worker-poc/tests/`

Решения и ограничения:

- Повторный live Avito run 2026-06-18 не выполнять.
- Следующий live run разрешён 2026-06-19 или позже, не больше одного запуска в UTC-день.
- Не использовать cookies, proxy, CAPTCHA bypass или агрессивные повторы.
- Backend-модели, Alembic и UI `/pricing` не начинать до решения `go_worker_prototype`.
- Текущее решение после Day 1: `continue_endurance_with_caution`.

Проверки:

- Unit tests POC проходили после изменений worker/preflight.
- `git diff --check` проходил для последних документационных изменений.
- Последние коммиты запушены в `origin/dev`.

Что осталось:

- На 2026-06-19 или позже выполнить Day 2 по `docs/38_price_monitoring_day2_operator_runbook.md`.
- После Day 2 сгенерировать `docs/34_price_monitoring_endurance_day_2.md` и обновить `docs/37_price_monitoring_gate_summary.md`.
- По результатам Day 2 выбрать продолжение: `continue_endurance_with_caution`, `hold_http_unstable`, `browser_profile_research` или позже `go_worker_prototype`.

## 2026-06-19

Контекст: продолжение research-направления "Оценщик"/Avito price monitoring в `equipment-accounting`, ветка `dev`.

Что сделано:

- Выполнен Day 2 endurance live run POC Avito worker: `run_id: 20260619T082828Z`.
- Все три job получили `HTTP 200` и usable snapshots:
  - `kyocera_m2040dn`: relevant 41, median 25000;
  - `lenovo_t14`: relevant 30, median 27995;
  - `dell_r740`: relevant 11, median 139500.
- Сгенерированы Day 2 endurance doc и gate summary.
- Проверен same-day guard после запуска: повторный live run 2026-06-19 блокируется.
- Подготовлено offline-сравнение Day 1 / Day 2 и отделён technical sandbox run от official endurance days.

Ключевые файлы:

- `docs/34_price_monitoring_endurance_day_2.md`
- `docs/37_price_monitoring_gate_summary.md`
- `docs/40_price_monitoring_endurance_day_1_2_comparison.md`
- `docs/continuation.md`

Решения и ограничения:

- Текущая рекомендация gate: `continue_endurance`.
- Текущее практическое решение: `continue_endurance_day_3`.
- `20260618T075301Z` не считать official endurance day, потому что он не дошёл до Avito из-за DNS/network sandbox.
- Повторный live Avito run 2026-06-19 не выполнять.
- Следующий live run разрешён 2026-06-20 или позже, не больше одного запуска в UTC-день.
- Backend-модели, Alembic и UI `/pricing` всё ещё не начинать до решения `go_worker_prototype`.

Проверки:

- `.venv/bin/python -m unittest discover -s tests`: 20 tests OK.
- `--dry-run-config`: config valid, 3 jobs.
- Preflight до live run: `ready`.
- Preflight после live run: `blocked_by_same_day_guard` на `20260619T082828Z`.
- `git diff --check` проходил для документационных изменений.
- Последние коммиты запушены в `origin/dev`.

Что осталось:

- На 2026-06-20 или позже выполнить Day 3 по тем же правилам: один live run в UTC-день, без cookies/proxy/CAPTCHA bypass.
- После Day 3 сравнить устойчивость `kyocera_m2040dn`, стабильность `lenovo_t14` и качество `dell_r740`.
- Не выбирать `go_worker_prototype` до 3-5 official endurance days и явного прохождения gate criteria.
