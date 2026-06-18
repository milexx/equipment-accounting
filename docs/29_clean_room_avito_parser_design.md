# Clean-Room Avito Parser Worker

Дата: 2026-06-17.

Статус: `design_ready_for_poc`.

Цель: описать собственный минимальный parser-worker для фонового мониторинга цен Avito без копирования чужого кода и без платных сервисов.

Связанные документы:

- `docs/19_avito_data_source_discovery_results.md`;
- `docs/27_duff89_parser_avito_audit.md`;
- `docs/28_duff89_parser_avito_poc_results.md`.

## 1. Основание

POC `Duff89/parser_avito` подтвердил рабочий технический подход:

- Avito search page доступна из нашей среды;
- embedded JSON в HTML содержит карточки объявлений;
- можно получить `title`, `price`, `url`, `description`, `published_at`, `location`;
- один one-shot run без cookies/proxy получил 50 объявлений и сохранил 49.

Но готовый parser нельзя использовать как целевой инструмент:

- нет явной лицензии;
- он заточен под новые/изменившиеся объявления;
- `viewed`-фильтр ломает daily full snapshot;
- output Excel, а нам нужен JSON/DB;
- есть лишние компоненты: GUI, Telegram/VK, phone parsing, bypass/cookies/proxy hooks.

Решение:

```text
пишем собственный clean-room parser-worker под нашу задачу
```

## 2. Принципы

Worker должен быть:

- отдельным от MVP;
- минимальным;
- one-shot, а не бесконечным loop внутри процесса;
- запускаемым по cron/systemd timer/APScheduler;
- без телефонов и персональных данных;
- без платных bypass-сервисов;
- без автоматического решения CAPTCHA;
- с сохранением полного дневного snapshot;
- с явным статусом `blocked`, если Avito ограничивает доступ.

## 3. Что Берём Как Идею

Берём только подтверждённые архитектурные идеи:

- использовать сохранённые Avito search URL;
- получать HTML страницы поиска;
- извлекать embedded JSON state из HTML;
- нормализовать объявления в свою схему;
- сохранять raw payload для диагностики;
- считать min/max/median только после фильтрации релевантности.

Не копируем код, классы, структуру файлов или реализации `Duff89/parser_avito`.

## 4. Что Не Берём

Не берём:

- GUI;
- Telegram/VK уведомления;
- Excel как основной формат;
- фильтр `viewed` до snapshot;
- phone parsing;
- cookies API;
- proxy rotation;
- mobile proxy;
- anti-captcha;
- stealth/fingerprint обходы;
- бесконечный loop внутри parser.

## 5. Архитектура

```text
avito-monitor-worker
  config/search_jobs.json
  src/
    cli.py
    http_client.py
    html_state_extractor.py
    listing_normalizer.py
    relevance_filter.py
    snapshot_calculator.py
    storage.py
  runs/
    {run_id}/
      run_report.json
      raw_pages/
      raw_listings.json
      normalized_listings.json
      rejected_listings.json
      daily_snapshot.json
```

Граница с MVP:

```text
worker writes JSON
equipment-accounting imports JSON later
```

На этапе POC worker не пишет в основную БД MVP.

## 6. Input Config

Пример:

```json
{
  "run_mode": "one_shot",
  "default_region": "russia",
  "request_delay_seconds": 5,
  "timeout_seconds": 20,
  "max_pages": 1,
  "jobs": [
    {
      "code": "kyocera_m2040dn",
      "position_name": "Kyocera ECOSYS M2040dn",
      "source": "avito",
      "search_url": "https://www.avito.ru/all/orgtehnika_i_rashodniki?q=Kyocera+ECOSYS+M2040dn",
      "required_terms": ["kyocera", "m2040dn"],
      "positive_terms": ["мфу", "принтер", "ecosys"],
      "negative_terms": ["картридж", "тонер", "печка", "плата", "шлейф", "донор", "запчасти"],
      "price_min": 5000,
      "price_max": 80000
    }
  ]
}
```

## 7. Run Report

Каждый запуск создаёт отчёт:

```json
{
  "run_id": "2026-06-17T12-00-00Z",
  "started_at": "2026-06-17T12:00:00Z",
  "finished_at": "2026-06-17T12:00:10Z",
  "status": "success",
  "jobs_total": 1,
  "jobs_success": 1,
  "jobs_blocked": 0,
  "jobs_failed": 0,
  "notes": []
}
```

Статусы job:

- `success`;
- `no_results`;
- `blocked`;
- `captcha`;
- `http_error`;
- `parser_error`;
- `partial_success`.

## 8. Normalized Listing

Целевая схема:

```json
{
  "source": "avito",
  "job_code": "kyocera_m2040dn",
  "external_id": "8020987851",
  "title": "Kyocera ecosys m2040dn",
  "description": "string|null",
  "price": 18000,
  "currency": "RUB",
  "url": "https://www.avito.ru/...",
  "location": "Новосибирск",
  "published_at": "2026-06-09T19:02:18",
  "fetched_at": "2026-06-17T12:00:00Z",
  "raw_payload": {}
}
```

Обязательные поля:

- `source`;
- `job_code`;
- `external_id`;
- `title`;
- `price`;
- `url`;
- `fetched_at`.

## 9. Relevance Filter

Фильтрация не должна уничтожать raw snapshot.

Порядок:

```text
raw_listings
  -> normalized_listings
  -> relevance_filter
  -> relevant_listings + rejected_listings
  -> daily_snapshot
```

Причина отклонения должна сохраняться:

```json
{
  "external_id": "8201691570",
  "title": "Мфу kyocera ecosys m2040dn",
  "price": 10000,
  "relevance_status": "rejected",
  "reject_reasons": ["spare_part_or_repair", "negative_term:запчасти"]
}
```

Минимальные правила:

- required terms должны быть в title/description;
- negative terms отклоняют объявление;
- price ниже/выше диапазона отклоняется;
- объявления "донор", "на запчасти", "нерабочий" отклоняются;
- похожие модели помечаются `unknown`, не `relevant`.

## 10. Daily Snapshot

Snapshot считается только по `relevant_listings`.

Пример:

```json
{
  "job_code": "kyocera_m2040dn",
  "snapshot_date": "2026-06-17",
  "source": "avito",
  "status": "success",
  "raw_count": 50,
  "normalized_count": 50,
  "relevant_count": 34,
  "rejected_count": 16,
  "min_price": 13000,
  "max_price": 35990,
  "median_price": 22000,
  "currency": "RUB",
  "fetched_at": "2026-06-17T12:00:00Z"
}
```

Если данных нет:

```json
{
  "status": "no_data",
  "raw_count": 0,
  "relevant_count": 0,
  "min_price": null,
  "max_price": null,
  "median_price": null
}
```

## 11. HTTP Strategy

Для POC:

- low frequency;
- one page per job;
- timeout 20 seconds;
- no cookies;
- no proxy;
- no phone pages;
- no item detail pages;
- only search page;
- save HTTP status and response headers;
- stop on `403`, `429`, CAPTCHA/access restricted.

Если получен block:

```text
status = blocked
do not retry aggressively
do not bypass
record evidence
exit cleanly
```

## 12. Pagination

POC:

```text
max_pages = 1
```

Следующий этап:

```text
max_pages = 2-3
```

Полный сбор тысяч объявлений не нужен. Для оценки достаточно 50-100 объявлений на позицию.

## 13. POC Plan

Этап 1:

- отдельная папка вне MVP;
- один config;
- один URL `Kyocera ECOSYS M2040dn`;
- один запуск;
- сохранить `raw.html`, `raw_listings.json`, `normalized_listings.json`, `daily_snapshot.json`.

Этап 2:

- добавить `HP LaserJet Pro MFP M426`;
- добавить `Lenovo ThinkPad T14`;
- добавить `Dell PowerEdge R740`;
- проверить шум и relevance filter.

Этап 3:

- endurance test 3-5 дней;
- 1-2 запуска в день;
- без cookies/proxy;
- фиксировать `success/blocked/captcha`.

## 14. Go/No-Go

Go:

- POC получает данные по 3 позициям;
- `price/title/url` заполнены минимум у 90%;
- relevant_count достаточно для расчёта;
- нет постоянных `403/429`;
- repeated runs сохраняют полный snapshot, а не только новые объявления;
- worker можно запускать по расписанию.

No-Go:

- Avito стабильно блокирует;
- embedded JSON недоступен;
- нужна платная proxy/cookies инфраструктура;
- relevance filter не оставляет достаточно объявлений;
- поддержка parser становится слишком дорогой.

## 15. Решение

Текущее решение:

```text
go_clean_room_parser_poc
```

Следующий шаг после этого документа:

```text
реализовать минимальный POC worker вне MVP
```

