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

