# Регламент Запуска Резервной Цепочки

Дата: 2026-06-21

## Область Применения

Ручной запуск резервной цепочки оценщика:

```text
Avito -> Duff89/parser_avito -> Юла
```

Этот регламент предназначен для следующего контролируемого тестового окна. Он не разрешает планировщик или повторные фоновые запуски.

## Предварительная Проверка

Запускать из каталога:

```text
/opt/workspace/projects/equipment-accounting/research/avito-monitor-worker-poc
```

Проверить конфигурацию:

```bash
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
```

Ожидаемый результат:

```text
block_diagnostic_enabled: true
youla_fallback_enabled: true
```

Проверить защиту от повторного запуска в тот же день:

```bash
.venv/bin/python src/worker.py --preflight --config config/search_jobs.json --runs-dir runs
```

Если статус `blocked_by_same_day_guard`, не запускать обработчик без явно утвержденного контролируемого исключения.

## Ручной Запуск

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

После блокировки Avito не повторять запуск в тот же UTC-день.

## После Запуска

Проанализировать последний run:

```bash
.venv/bin/python src/worker.py --analyze-run runs/<RUN_ID>
```

Вывод анализа должен показывать `source` для каждой позиции.

Сформировать markdown-отчет:

```bash
.venv/bin/python src/worker.py --analyze-run runs/<RUN_ID> --write-markdown-report --output runs/<RUN_ID>/offline_report.md
```

Проверить по каждой позиции:

- `job_report.json`
- `daily_snapshot.json`
- `relevant_listings.json`
- `unknown_listings.json`
- `rejected_listings.json`
- `block_diagnostic.json`, если Avito был заблокирован
- `duff89_normalized_listings.json`, если запускался Duff89
- `youla_fallback_report.json`, если запускалась Юла

## Критерии Приемки

По каждой отслеживаемой позиции зафиксировать:

- итоговый `status`;
- итоговый `source`;
- `primary_status`, если использовался резервный источник;
- `primary_http_status`, если использовался резервный источник;
- `relevant_count`;
- `unknown_count`;
- `rejected_count`;
- медианную цену, если она есть.

Полезные исходы:

- `source: avito` означает, что основной обработчик сработал.
- `source: avito_duff89` означает, что Avito не дал результата, но Duff89 вернул пригодные объявления.
- `source: youla` означает, что Avito и Duff89 не дали результата, но Юла вернула пригодные объявления.

Проблемные исходы:

- `blocked` / `captcha`: источник недоступен.
- `parser_error`: ответ источника не удалось разобрать.
- `no_data`: источник вернул данные, но ни одно объявление не прошло фильтр релевантности.

## Импорт В Базу

Импортировать только после ручной проверки каталога run:

```bash
cd /opt/workspace/projects/equipment-accounting
.venv/bin/python scripts/import_price_poc_run.py research/avito-monitor-worker-poc/runs/<RUN_ID>
```

Импортер сохраняет фактический источник снимка и объявлений:

- `avito`
- `avito_duff89`
- `youla`

Заблокированный Avito не импортируется как ценовая точка, если резервный источник дал успешный снимок. Он остается в исходных отчетах run/job как контекст состояния источника.

## Проверка Интерфейса

Открыть:

```text
http://185.168.208.240:8010/pricing
```

Проверить:

- список точек графика показывает код источника;
- в журнале есть отдельная колонка `Источник`;
- резервные ценовые точки не подписаны ошибочно как `avito`.

## Решение После Запуска

Выбрать одно:

- `keep_fallback_chain_for_mvp`: цепочка дает полезные релевантные снимки.
- `adjust_filters_then_retry_next_day`: источник работает, но релевантность шумная.
- `hold_source_unstable`: все источники заблокированы или непригодны.
- `youla_only_manual_experiment`: Avito/Duff89 остаются заблокированными, Юла является единственным полезным резервным источником.
