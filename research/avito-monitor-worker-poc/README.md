# Avito Monitor Worker POC

Статус: research-only.

Это изолированный POC собственного clean-room parser-worker для Avito. Он не подключён к MVP и не пишет в основную БД приложения.

## Что Проверяет

- one-shot сбор страницы поиска Avito;
- сохранение raw HTML;
- извлечение embedded JSON;
- нормализация объявлений;
- разделение на `relevant`, `unknown`, `rejected`;
- расчёт daily snapshot по `relevant`.

## Ограничения

- Это не production-код.
- Live HTTP доступ к Avito нестабилен: в POC были и `HTTP 200`, и `HTTP 403`.
- Нет обхода CAPTCHA, proxy rotation, phone parsing или paid bypass.
- Частые live-запуски запрещены для POC. Стартовое правило: не чаще 1 запуска в день.

## Установка Для POC

Из корня research-пакета:

```bash
python3 -m venv .venv
.venv/bin/pip install beautifulsoup4 curl_cffi
cp config/search_jobs.example.json config/search_jobs.json
```

## Запуск

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs
```

Live-запуск защищён от случайного повтора в тот же UTC-день. Если в `runs/` уже есть live `run_report.json` за текущую дату, worker остановится до сетевых запросов со статусом `blocked_by_same_day_guard`.

Принудительный повтор возможен только явным флагом:

```bash
.venv/bin/python src/worker.py --config config/search_jobs.json --runs-dir runs --allow-same-day-live
```

Использовать этот флаг только для инфраструктурных сбоев до обращения к Avito, например DNS/sandbox, и фиксировать причину в отчёте.

Результаты появятся в:

```text
runs/{run_id}/{job_code}/
```

Основные файлы:

- `raw_pages/page_1.html`;
- `raw_listings.json`;
- `normalized_listings.json`;
- `relevant_listings.json`;
- `unknown_listings.json`;
- `rejected_listings.json`;
- `daily_snapshot.json`;
- `job_report.json`;
- `run_report.json`.

## Offline-Анализ Run

Повторный live-запуск для анализа не нужен. Уже сохранённый run можно разобрать так:

```bash
.venv/bin/python src/worker.py --analyze-run runs/20260618T075423Z
```

Анализатор показывает:

- HTTP/status по каждой позиции;
- `raw`, `normalized`, `relevant`, `unknown`, `rejected`;
- `min`, `max`, `median`;
- признаки HTML-проблем: `access_restricted_ip`, `page_not_found`, `captcha`;
- сводку причин `rejected` и `unknown`.

Markdown-отчёт из сохранённого run:

```bash
.venv/bin/python src/worker.py --write-markdown-report runs/20260618T075423Z --output runs/20260618T075423Z/offline_report.md
```

Документ endurance day report для `docs/`:

```bash
.venv/bin/python src/worker.py --write-endurance-doc runs/{run_id} --output ../../docs/34_price_monitoring_endurance_day_2.md --day 2 --date 2026-06-19
```

Пересчёт сохранённого HTML без сетевого запроса:

```bash
.venv/bin/python src/worker.py --from-html runs/20260618T075423Z/lenovo_t14/raw_pages/page_1.html --job-code lenovo_t14 --config config/search_jobs.json --runs-dir runs
```

Проверка конфига без сетевого запроса:

```bash
.venv/bin/python src/worker.py --dry-run-config --config config/search_jobs.json
```

## Offline-Тесты

Тесты не делают сетевых запросов и проверяют классификацию, snapshot-расчёт, диагностику HTML-проблем и анализатор run:

```bash
.venv/bin/python -m unittest discover -s tests
```

## Методика

`relevant` участвует в `min_price`, `max_price`, `median_price`.

`unknown` не участвует в расчёте, но должен показываться оценщику.

`rejected` хранится для аудита и настройки фильтров.

## Следующий Этап

Endurance test:

- 3 позиции;
- 1 запуск в день;
- 3-5 дней;
- без proxy/cookies;
- фиксировать `success`, `blocked`, `captcha`, `parser_error`.

## Журнал Endurance Test

Правило: не больше одного live-запуска в день. При `blocked`, `captcha`, `403` или `429` не делать повторный запуск в этот же день.

| День | Дата | Позиции | Результат | Документ |
|---|---|---|---|---|
| 1 | 2026-06-18 | `kyocera_m2040dn`, `lenovo_t14`, `dell_r740` | `partial_success_http_unstable` | `docs/33_price_monitoring_endurance_day_1.md` |
| 2 | 2026-06-19 или позже | `kyocera_m2040dn`, `lenovo_t14`, `dell_r740` | planned | `docs/34_price_monitoring_endurance_day_2_plan.md` |

В git коммитятся только конфиги, код и отчёты. Runtime-данные `runs/`, raw HTML и локальный `config/search_jobs.json` не коммитятся.
