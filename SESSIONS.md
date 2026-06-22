# Сессии

## 2026-06-22

Контекст: ручная проверка резервной цепочки оценщика после настройки `Avito -> Duff89/parser_avito -> Youla`, ветка `dev`.

Что сделано:

- Выполнен один контролируемый ручной запуск: `20260622T040909Z`.
- Итоговый статус запуска: `success`, 3/3 позиции получили успешные снимки.
- Результаты:
  - `kyocera_m2040dn`: `source=avito_duff89`, релевантных 37, медиана 24999;
  - `lenovo_t14`: `source=avito`, релевантных 25, медиана 28000;
  - `dell_r740`: `source=avito_duff89`, релевантных 41, медиана 200000.
- Найден и исправлен дефект Duff89 probe: относительный `job_dir` ломался после `os.chdir` в репозиторий Duff89, из-за чего XLSX был создан, но объявления считались как 0.
- Duff89 probe теперь резолвит `repo` и `job_dir` до смены директории и сериализует похожие на дату/время значения Excel в JSON.
- Запуск восстановлен из уже сохраненных Duff89 XLSX без нового Avito-запроса.
- Запуск импортирован в БД: 103 наблюдения, 3 снимка, 0 ошибок парсера.
- `/pricing` проверен: графики и журнал показывают точки 2026-06-22 с фактическими источниками `avito` / `avito_duff89`.
- Упрощен `scripts/import_price_poc_run.py`: убрана лишняя самоперезапускающаяся `python -c` обертка.
- Разобрана причина различия `avito` blocked и `avito_duff89` success: это не другой источник и не обход, а разные HTTP-клиенты и разные отпечатки запросов к одному Avito через QRATOR.
- В основной обработчик добавлена запись метаданных отпечатка запроса (`impersonate`, `user-agent`) в `response_meta.json` для следующих контролируемых запусков.

Ключевые файлы:

- `docs/52_price_monitoring_fallback_run_2026_06_22.md`
- `docs/53_avito_vs_duff89_blocking_analysis.md`
- `research/avito-monitor-worker-poc/scripts/duff89_probe.py`
- `research/avito-monitor-worker-poc/src/worker.py`
- `research/avito-monitor-worker-poc/tests/test_worker.py`
- `scripts/import_price_poc_run.py`

Решения и ограничения:

- Текущее решение: `keep_fallback_chain_for_mvp_manual`.
- Резервная цепочка полезна для MVP как ручной источник ценовой истории.
- Планировщик, цикл повторов после block, proxy/cookies/обход CAPTCHA остаются запрещены.
- Не повторять боевой запуск в тот же UTC-день без явного контролируемого исключения.

Проверки:

- `research/avito-monitor-worker-poc/.venv/bin/python -m unittest discover -s research/avito-monitor-worker-poc/tests`: 29 tests OK.
- `.venv/bin/python -m compileall scripts/import_price_poc_run.py`: OK.
- `.venv/bin/python scripts/import_price_poc_run.py research/avito-monitor-worker-poc/runs/20260622T040909Z`: импорт OK вне sandbox.
- `/pricing` через локальный HTTP показывает новые строки и точки графиков.

## 2026-06-21

Контекст: продолжение направления "Оценщик"/исследование рыночных источников после Day 4 Avito, ветка `dev`.

Что сделано:

- Проверена Юла как возможный второй экспериментальный источник цен.
- HTML `https://youla.ru/` и поисковый URL вернули `HTTP 200` с текущего сервера, без Avito-подобного `HTTP 403`.
- Из `window.__YOULA_STATE__` получены публичные параметры конечных точек: `apiFederationUri`, `apiClientId`, анонимный `uid`, геолокация.
- В JS-бандлах найден GraphQL-запрос `catalogProductsBoard`.
- Выполнен один контрольный POST на `https://api-gw.youla.ru/graphql` по запросу `Lenovo ThinkPad T14`; результат `HTTP 200`, получены карточки с ценами, URL, городом и cursor.
- Добавлен отдельный ручной POC для Юлы без планировщика и без интеграции в производственный поток оценщика.
- POC-скрипт проверен: `HTTP 200`, `status: ok`, `count: 30`, цены нормализуются из копеек в рубли.
- Реализована резервная цепочка для ручного прогона обработчика: `avito -> avito_duff89 -> youla`.
- Duff89 probe теперь сохраняет XLSX, нормализует объявления в `duff89_normalized_listings.json` и может стать источником снимка, а не только диагностикой.
- Обработчик теперь строит итоговый `daily_snapshot.json` по первому успешному источнику и сохраняет `source: avito`, `source: avito_duff89` или `source: youla`.
- Локальный ignored `research/avito-monitor-worker-poc/config/search_jobs.json` настроен с включёнными Duff89 и резервной Юлой для следующего ручного теста.
- Импорт `scripts/import_price_poc_run.py` через `PricingService` теперь сохраняет фактический источник снимка/объявления.
- `/pricing` показывает источник точки в карточке графика и отдельной колонкой в журнале.
- Подготовлен регламент следующего ручного прогона резервной цепочки.

Ключевые файлы:

- `docs/49_youla_source_discovery.md`
- `docs/50_price_monitoring_fallback_chain.md`
- `docs/51_price_monitoring_fallback_runbook.md`
- `research/youla-source-poc/README.md`
- `research/youla-source-poc/fetch_youla_catalog.py`
- `research/avito-monitor-worker-poc/src/worker.py`
- `research/avito-monitor-worker-poc/scripts/duff89_probe.py`
- `app/services/pricing_service.py`
- `app/api/pricing.py`
- `app/templates/pricing/index.html`

Решения и ограничения:

- Рекомендован следующий статус: `youla_manual_source_poc`.
- Юлу можно проверять только как ручной экспериментальный источник, с сохранением каждого запуска как снимка.
- Не подключать планировщик и не делать фоновые повторные запросы.
- Avito после Day 4 остаётся `manual_experimental` / `blocked_recently`; не повторять заблокированный Avito в тот же день.
- Резервная цепочка не отменяет ограничение: только ручной режим, без планировщика и без цикла повторов.

Что осталось:

- Один раз прогнать всю резервную цепочку по текущим отслеживаемым позициям с консервативными паузами.
- Сравнить релевантность и медианы резервного источника с последними успешными снимками Avito.
- Если полезно, добавить `source=youla` в исторические снимки без изменения контракта `/pricing`.

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

## 2026-06-20, backend skeleton

Контекст: выполнение всех шагов дневного плана по backend skeleton для "Оценщика" после решения `go_worker_prototype_candidate_with_constraints`.

Что сделано:

- Добавлены pricing enum values: `PriceRunStatus`, `PriceJobStatus`, `PriceObservationStatus`.
- Добавлены backend-модели:
  - `PriceCategory`;
  - `MonitoredItem`;
  - `MarketSource`;
  - `PriceScrapeRun`;
  - `PriceObservation`;
  - `DailyPriceSnapshot`;
  - `ParserError`.
- Добавлена Alembic migration `20260620_0005_add_pricing_tables`.
- Обновлён Alembic env: подключён `app.models.pricing`, online migrations используют `create_engine(settings.database_url, poolclass=NullPool)`.
- Добавлен `PricingService` с созданием source/category/item/run, сохранением observations/snapshots/parser errors и идемпотентным импортом сохранённого POC-run.
- Добавлен ручной import script `scripts/import_price_poc_run.py`.
- Добавлены focused tests `tests/test_pricing_service.py`.
- В dev DB применена миграция до `20260620_0005`.
- В новые таблицы импортирован сохранённый Day 3 run `20260620T081446Z`.

Результат импорта Day 3:

```text
price_scrape_runs: 1
price_observations: 64
daily_price_snapshots: 3
parser_errors: 1
```

Ключевые файлы:

- `app/models/enums.py`
- `app/models/pricing.py`
- `app/models/__init__.py`
- `app/services/pricing_service.py`
- `scripts/import_price_poc_run.py`
- `scripts/__init__.py`
- `tests/test_pricing_service.py`
- `alembic/env.py`
- `alembic/versions/20260620_0005_add_pricing_tables.py`
- `docs/46_price_monitoring_backend_skeleton_checklist.md`
- `docs/continuation.md`

Проверки:

- `.venv/bin/python -m unittest discover -s tests`: 3 tests OK.
- `research/avito-monitor-worker-poc/.venv/bin/python -m unittest discover -s research/avito-monitor-worker-poc/tests`: 21 tests OK.
- `.venv/bin/python -c "from scripts.check_mvp_acceptance import main; raise SystemExit(main())"`: passed.
- `.venv/bin/ruff check app scripts tests alembic/versions/20260620_0005_add_pricing_tables.py`: passed.
- `git diff --check`: passed.
- Alembic current via Python API: `20260620_0005 (head)`.

Ограничения и наблюдения:

- Live Avito не запускался.
- UI `/pricing`, scheduler, automatic daily runs и live parser integration не реализованы.
- Прямой запуск `python scripts/import_price_poc_run.py ...` в текущем sandbox окружении ловил `psycopg.OperationalError: connection is bad` до первого SQL; проверенный import-mode command зафиксирован в `docs/continuation.md`.
- Следующий backend-шаг: parser contract + disabled Avito adapter boundary либо read-only service/query layer для будущего UI.

## 2026-06-20, historical pricing fix

Контекст: уточнено требование - каждый запуск оценщика должен фиксироваться отдельно, а исторические графики должны строиться по сохранённым точкам, без перезаписи same-day run.

Что сделано:

- Импортирован Day 2 run `20260619T082828Z`, где `dell_r740` был успешным.
- Добавлена миграция `20260620_0006_make_price_snapshots_run_scoped`.
- Unique constraint для `daily_price_snapshots` изменён:
  - было: `monitored_item_id + source_id + snapshot_date`;
  - стало: `scrape_run_id + monitored_item_id + source_id + snapshot_date`.
- `PricingService.save_snapshot(...)` теперь ищет snapshot с учётом `scrape_run_id`.
- Добавлен тест, что два разных запуска в один день для одной позиции сохраняют две исторические точки.

Текущее состояние dev DB:

```text
current revision: 20260620_0006
price_scrape_runs: 2
price_observations: 146
daily_price_snapshots: 6
parser_errors: 1
```

История Dell:

```text
2026-06-19: success, relevant 11, median 139500
2026-06-20: blocked, HTTP 403
```

Проверки:

- `.venv/bin/python -m unittest discover -s tests`: 4 tests OK.
- `.venv/bin/ruff check app scripts tests alembic/versions/20260620_0006_make_price_snapshots_run_scoped.py`: passed.
- `git diff --check`: passed.
- Alembic current: `20260620_0006 (head)`.

## 2026-06-20, pricing read-only UI prototype

Контекст: нужен первый экран оценщика, чтобы смотреть сохранённую историю запусков и будущие исторические графики без повторного live Avito run.

Что сделано:

- Добавлен маршрут `/pricing` для центра.
- Добавлен read-only Jinja UI с SVG-графиками по `daily_price_snapshots`.
- Для каждой позиции показываются линии `min`, `median`, `max`, статусы blocked/no data и таблица всех snapshots.
- Главная страница получила ссылку `Оценщик`.
- MVP acceptance smoke дополнен проверками:
  - центр открывает `/pricing`;
  - региональная роль получает `403`.

Проверки:

- `/pricing`: HTTP 200 для центра.
- `/pricing` с `demo_user=region24`: HTTP 403.
- `.venv/bin/python -m unittest discover -s tests`: 4 tests OK.
- `research/avito-monitor-worker-poc/.venv/bin/python -m unittest discover -s research/avito-monitor-worker-poc/tests`: 21 tests OK.
- `.venv/bin/ruff check app scripts tests alembic/versions/20260620_0006_make_price_snapshots_run_scoped.py`: passed.
- `.venv/bin/python -c "from scripts.check_mvp_acceptance import main; raise SystemExit(main())"`: passed.
- `git diff --check`: passed.

Ограничения:

- Live Avito не запускался.
- Scheduler не подключался.
- UI использует уже импортированные snapshots из dev DB.

## 2026-06-21, Avito endurance Day 4

Контекст: выполнен дополнительный live endurance run после Day 3, чтобы проверить устойчивость источника перед любым повышением автоматизации.

Что сделано:

- Preflight вернул `ready`; same-day live run отсутствовал.
- Выполнен один live run: `20260621T131205Z`.
- Результат: все 3 job получили `HTTP 403`:
  - `dell_r740`: `blocked`, `access_restricted_ip`;
  - `kyocera_m2040dn`: `blocked`, `access_restricted_ip`;
  - `lenovo_t14`: `blocked`, `access_restricted_ip`.
- Сгенерирован `docs/47_price_monitoring_endurance_day_4.md`.
- Обновлён `docs/37_price_monitoring_gate_summary.md`.
- Добавлен `docs/48_price_monitoring_gate_decision_after_day_4.md`.
- Run импортирован в основную БД оценщика.

Состояние dev DB после импорта:

```text
price_scrape_runs: 3
price_observations: 146
daily_price_snapshots: 9
parser_errors: 4
```

Решение после Day 4:

```text
continue_endurance_with_automation_hold
```

Ограничения:

- Повторный live Avito run 2026-06-21 UTC не выполнять.
- Scheduler и unattended production runs не включать.
- Avito остаётся experimental/manual source с явным отображением blocked-состояний.

## 2026-06-21, Duff89 block diagnostic hook

Контекст: нужно при каждой блокировке проверять, как в той же среде отрабатывает git-модуль `Duff89/parser_avito`.

Что сделано:

- В POC worker добавлен `block_diagnostic` hook.
- При статусе `blocked` или `captcha` worker запускает настроенную диагностическую команду.
- Результат сохраняется в:
  - `runs/{run_id}/{job_code}/block_diagnostic.json`;
  - `runs/{run_id}/{job_code}/duff89_probe_report.json` для Duff89 probe.
- Analysis и markdown/endurance reports теперь показывают колонку `Diagnostic`.
- Добавлен `research/avito-monitor-worker-poc/scripts/duff89_probe.py`.
- В `config/search_jobs.example.json` hook описан, но выключен.
- В локальном ignored `config/search_jobs.json` hook включён для следующего разрешённого live run.

Ограничения:

- Это диагностический probe, не источник цены.
- Это не отменяет правило: не делать повторный live Avito run 2026-06-21 UTC.
- Следующий live run можно делать 2026-06-22 UTC или позже.
