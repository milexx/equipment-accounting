# План Прогона Оценщика 2026-06-24

Дата планируемого запуска: 2026-06-24
Режим: ручной контролируемый запуск

## Цель

Проверить устойчивость цепочки:

```text
Avito -> Duff89/parser_avito -> Юла
```

Нужный результат дня: один корректно зафиксированный run, импортированный в базу только после проверки, без повторных попыток при блокировке источника.

## Перед Запуском

Рабочий каталог:

```bash
cd /opt/workspace/projects/equipment-accounting/research/avito-monitor-worker-poc
```

Проверить конфигурацию:

```bash
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
```

Ожидаемые признаки:

- `jobs_total: 3`;
- `kyocera_m2040dn`, `lenovo_t14`, `dell_r740` есть в списке;
- `block_diagnostic_enabled: true`;
- `youla_fallback_enabled: true`.

Проверить дневной guard:

```bash
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

Если preflight вернул `blocked_by_same_day_guard`, боевой запуск не делать без отдельного явного решения.

## Боевой Запуск

Выполнить один раз:

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

Сохранить `run_id` из вывода:

```text
RUN_ID=<заполнить после запуска>
```

## Анализ После Запуска

Проанализировать run:

```bash
.venv/bin/python src/worker.py --analyze-run runs/<RUN_ID>
```

Сформировать markdown-отчет:

```bash
.venv/bin/python src/worker.py --write-markdown-report runs/<RUN_ID> --output runs/<RUN_ID>/offline_report.md
```

Проверить, что по каждой позиции видны:

- итоговый `source`;
- итоговый `status`;
- `http_status`;
- `relevant_count`;
- `unknown_count`;
- `rejected_count`;
- `median_price`, если статус успешный.

## Проверка Источников

Если итоговый источник `avito`:

- основной Avito сработал;
- fallback не должен запускаться как итоговый источник;
- можно импортировать после проверки релевантности.

Если итоговый источник `avito_duff89`:

- основной Avito не дал пригодный результат;
- проверить `primary_status` и `primary_http_status`;
- убедиться, что в историю цены попадет `avito_duff89`, а не `blocked`.

Если итоговый источник `youla`:

- Avito и Duff89 не дали пригодный результат;
- проверить качество релевантности отдельно;
- импортировать только если объявления похожи на реальные аналоги.

Если статус `blocked`, `captcha`, `parser_error` или `failed`:

- не повторять боевой запуск в этот же UTC-день;
- не импортировать как ценовую точку;
- зафиксировать состояние источника в документе дня.

## Импорт В Базу

Импортировать только после ручной проверки:

```bash
cd /opt/workspace/projects/equipment-accounting
.venv/bin/python scripts/import_price_poc_run.py research/avito-monitor-worker-poc/runs/<RUN_ID>
```

Ожидаемый полезный результат:

```text
status=success
snapshots_saved=3
parser_errors_created=0
```

Если есть `parser_errors_created`, перед выводом проверить, не попали ли ошибки в график как результат оценки.

## Проверка Интерфейса

Открыть:

```text
http://185.168.208.240:8010/pricing
```

Проверить:

- в карточках появилась последняя оценка за 2026-06-24;
- в графиках добавилась новая точка;
- в журнале указан фактический источник;
- blocked-исходы не отображаются как цена.

## Документ Дня

После проверки создать документ:

```text
docs/58_price_monitoring_fallback_run_2026_06_24.md
```

В документе зафиксировать:

- `run_id`;
- preflight-статус;
- таблицу по трем позициям;
- поведение источников;
- результат импорта;
- решение после запуска.

## Решение После Запуска

Выбрать одно:

- `keep_fallback_chain_for_mvp_manual` - цепочка снова дала полезные снимки;
- `keep_but_watch_avito_volatility` - данные есть, но Avito нестабилен по источникам;
- `adjust_filters_then_retry_next_day` - источник работает, но много шума;
- `hold_source_unstable` - источники заблокированы или непригодны;
- `youla_only_manual_experiment` - полезным остался только источник Юла.

## Что Не Делать

- Не запускать повторно после блокировки в тот же UTC-день.
- Не включать планировщик.
- Не добавлять прокси, cookies и обход CAPTCHA.
- Не импортировать `blocked` как ценовой снимок.
- Не менять фильтры во время самого дневного запуска.
