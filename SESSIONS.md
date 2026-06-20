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

## 2026-06-19, второй блок

Контекст: офлайн-доработки после Day 2, без новых live Avito-запросов.

Что сделано:

- Доработан gate summary: infrastructure attempts больше не смешиваются с official endurance days.
- `20260618T075301Z` теперь выводится как excluded run с причиной `infrastructure_attempt`.
- Gate summary теперь считает:
  - `runs_seen_total: 3`;
  - `runs_total: 2`;
  - `runs_excluded: 1`;
  - `runs_with_majority_blocked_or_failed: 0`.
- Подготовлен Day 3 operator runbook.
- Выполнен filter review для `dell_r740`: найден false rejection risk из-за слишком широких negative terms.
- Смягчён tracked example config для `dell_r740`; локальный ignored `config/search_jobs.json` тоже обновлён для Day 3.
- Подготовлен post-gate integration backlog, который разрешено использовать только после `go_worker_prototype`.

Ключевые файлы:

- `research/avito-monitor-worker-poc/src/worker.py`
- `research/avito-monitor-worker-poc/tests/test_worker.py`
- `research/avito-monitor-worker-poc/config/search_jobs.example.json`
- `docs/37_price_monitoring_gate_summary.md`
- `docs/41_price_monitoring_day3_operator_runbook.md`
- `docs/42_price_monitoring_dell_r740_filter_review.md`
- `docs/43_price_monitoring_post_gate_integration_backlog.md`
- `docs/36_price_monitoring_gate_acceptance.md`
- `docs/continuation.md`

Решения и ограничения:

- Повторный live Avito run 2026-06-19 не выполнять.
- Day 3 запускать 2026-06-20 или позже, один раз в UTC-день.
- `go_worker_prototype` всё ещё преждевременен: есть только 2 official endurance days.
- Backend-модели, Alembic и UI `/pricing` не начинать до итогового gate decision.

Проверки:

- `.venv/bin/python -m unittest discover -s tests`: 21 tests OK.
- `.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json`: OK.
- `git diff --check`: OK.
- Коммиты `49832aa` и `5a3ab96` запушены в `origin/dev`.

Что осталось:

- На 2026-06-20 или позже выполнить Day 3 по `docs/41_price_monitoring_day3_operator_runbook.md`.
- После Day 3 проверить, улучшился ли `dell_r740` после смягчения фильтра.
- После Day 3 обновить gate summary и принять одно из решений: `continue_endurance_day_4`, `go_worker_prototype_candidate`, `hold_http_unstable`, `adjust_filters_offline`.

## 2026-06-20

Контекст: закрытие Day 3 endurance по research-направлению "Оценщик"/Avito price monitoring в `equipment-accounting`, ветка `dev`.

Что сделано:

- Выполнен Day 3 endurance live run POC Avito worker: `run_id: 20260620T081446Z`.
- Результат запуска: `partial_success`, 2 успешные job и 1 блокировка:
  - `kyocera_m2040dn`: `HTTP 200`, relevant 33, median 25000;
  - `lenovo_t14`: `HTTP 200`, relevant 31, median 27990;
  - `dell_r740`: `HTTP 403`, `blocked`, block reason `http_403`.
- Сгенерирован Day 3 endurance doc и обновлён gate summary.
- После Day 3 принято решение `go_worker_prototype_candidate_with_constraints`.
- Подготовлен backend skeleton checklist для следующего этапа, без запуска реализации backend-моделей в этот день.
- Обновлена точка продолжения в `docs/continuation.md`.

Ключевые файлы:

- `docs/44_price_monitoring_endurance_day_3.md`
- `docs/45_price_monitoring_gate_decision_after_day_3.md`
- `docs/46_price_monitoring_backend_skeleton_checklist.md`
- `docs/37_price_monitoring_gate_summary.md`
- `docs/continuation.md`

Решения и ограничения:

- Источник Avito можно использовать только как экспериментальный worker prototype candidate, не как production-stable источник.
- Backend-прототип разрешён только с ограничениями: abstraction boundary, manual run, stop-on-block, без scheduler и без UI `/pricing`.
- Запрещены retry loop, proxy/cookies/CAPTCHA bypass и повторные live-запросы в тот же UTC-день.
- Повторный live Avito run 2026-06-20 не выполнять.
- Следующий live run разрешён 2026-06-21 или позже, если решено продолжать endurance day 4.

Проверки:

- `.venv/bin/python -m unittest discover -s tests`: 21 tests OK.
- `.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json`: OK.
- Preflight до live run: `ready`.
- Preflight после live run: `blocked_by_same_day_guard` на `20260620T081446Z`.
- Коммиты `f4fd7c9` и `0c8a9ec` запушены в `origin/dev`.

Что осталось:

- При следующем продолжении начинать с `docs/46_price_monitoring_backend_skeleton_checklist.md`.
- Если нужен Day 4 endurance, запускать его не раньше 2026-06-21 и только один раз в UTC-день.
- Перед backend-кодом явно подтвердить объём: модели/миграция/ручной сервис без scheduler и UI.
