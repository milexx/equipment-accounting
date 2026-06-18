# Self-Service Technical Spike По Данным Avito

Дата: 2026-06-17.

Статус: `ready_for_token_check`.

Цель: найти техническое решение получения данных Avito без переговоров с людьми: через self-service API, hosted actor, готовый scraper endpoint или другой программный интерфейс.

Связанные документы:

- `docs/19_avito_data_source_discovery_results.md`;
- `docs/20_intermediary_avito_data_services.md`;
- `docs/21_avito_vendor_spike_requests.md`.

## 1. Изменение Подхода

Сценарий общения с поставщиками не является основным.

Основной подход теперь:

1. Проверить self-service источники, которые можно запустить технически.
2. Получить реальный JSON/CSV по 5 тестовым позициям.
3. Проверить поля, релевантность, стабильность и цену запуска.
4. Только после этого принимать решение, есть ли источник данных для модуля.

## 2. Приоритет Технических Вариантов

| Приоритет | Вариант | Почему |
|---:|---|---|
| 1 | Apify Avito actor | Есть готовые actors, API запуска, dataset output, можно проверить без разработки собственного парсера |
| 2 | Bright Data scraper/API | Технически зрелый provider, но может потребовать аккаунт/платежи/настройку продукта |
| 3 | ShopAPIS | Потенциально прямой product data API, но нужно проверить наличие self-service доступа и документации |
| 4 | MarketParser | Хорош по предметной области, но если нет публичного API/token self-service, уходит в ручной vendor track |
| 5 | Exa | Только discovery/fallback, не источник daily snapshot |
| 6 | Direct parser | Последний вариант из-за 429/CAPTCHA/robots/rate limits |

## 3. Почему Apify Первый

Apify подходит для технического spike, потому что:

- есть marketplace actors под Avito;
- actor можно запускать через API;
- результат обычно складывается в dataset;
- dataset можно забрать JSON API;
- можно быстро проверить 5 запросов;
- не нужно писать собственный обход Avito на первом шаге.

Риск: это всё равно scraping-решение, не официальный API Avito. Actor может ломаться, требовать proxies и иметь ограничения по legal/compliance.

## 4. Технический Сценарий Apify

### 4.1 Что Нужно

- аккаунт Apify;
- API token;
- выбранный actor, например Avito scraper actor из marketplace;
- включённый proxy configuration, если actor требует российские residential proxies;
- тестовый набор запросов.

### 4.2 Тестовые Позиции

```text
Kyocera ECOSYS M2040dn
HP LaserJet Pro MFP M426
Lenovo ThinkPad T14
Dell PowerEdge R740
Dell P2419H
```

Регион: `rossiya` или эквивалент "вся Россия" в параметрах actor.

Лимит: 50 объявлений на запрос.

### 4.3 Минимальный Input Для Actor

Точный schema зависит от выбранного actor, но технически нужен такой смысл:

```json
{
  "keyword": "Kyocera ECOSYS M2040dn",
  "region": "rossiya",
  "maxItems": 50,
  "sort": "date"
}
```

Если actor принимает не `keyword`, а `search`, `query`, `startUrls` или другой формат, адаптер меняется под конкретный actor. Для доменной модели это не важно.

### 4.4 Запуск Через API

Шаблон команды:

```bash
curl -X POST "https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "Kyocera ECOSYS M2040dn",
    "region": "rossiya",
    "maxItems": 50,
    "sort": "date"
  }'
```

Ожидаемый результат: JSON с `id` запуска и ссылками на default dataset.

### 4.5 Получение Dataset

Шаблон:

```bash
curl "https://api.apify.com/v2/datasets/{DATASET_ID}/items?token={APIFY_TOKEN}&format=json&clean=true"
```

Ожидаемый результат: массив объявлений.

### 4.6 Нормализация Результата

Любой output actor приводим к внутренней форме:

```json
{
  "source": "avito",
  "provider": "apify",
  "external_id": "string|null",
  "title": "string",
  "price": 12345,
  "currency": "RUB",
  "url": "https://www.avito.ru/...",
  "region": "string|null",
  "published_at": "datetime|null",
  "updated_at": "datetime|null",
  "fetched_at": "datetime",
  "seller_type": "string|null",
  "status": "active|unknown",
  "raw_payload": {}
}
```

## 5. Критерии Технического Go/No-Go

Apify или другой self-service provider проходит spike, если:

- запуск работает через API без ручных действий в кабинете;
- по каждому из 5 запросов возвращается JSON;
- по массовым позициям возвращается хотя бы 20 релевантных объявлений;
- `price` есть и его можно привести к числу;
- `url` ведёт на конкретное объявление;
- есть город/регион или его можно извлечь;
- можно ограничить выдачу 50-100 объявлениями;
- ошибка actor отдаётся машинно, а не только в UI;
- стоимость одного дневного прогона можно оценить;
- provider не требует, чтобы наш код напрямую обходил CAPTCHA.

No-Go, если:

- actor нестабилен уже на 5 запросах;
- больше половины результатов нерелевантны;
- цена находится только в тексте и плохо парсится;
- нет URL конкретного объявления;
- нет API-запуска;
- требуется ручная работа в UI для каждого запроса;
- provider требует собственные прокси и ручную борьбу с блокировками.

## 6. Стоимость Для Оценки

Расчёт нагрузки:

```text
100 позиций x 50 объявлений x 1 раз в день = 5 000 объявлений/день
200 позиций x 100 объявлений x 1 раз в день = 20 000 объявлений/день
```

В месяц:

```text
150 000 - 600 000 объявлений/месяц
```

Для каждого provider нужно считать не только записи, но и:

- actor compute time;
- proxy usage;
- page loads;
- failed retries;
- хранение dataset;
- стоимость API calls.

## 7. Минимальный Технический Отчёт После Spike

По каждому provider фиксируем:

| Поле | Значение |
|---|---|
| Provider |  |
| Метод доступа | API / actor / scraper endpoint |
| Требуется token | Да/нет |
| Требуются прокси | Да/нет/на стороне provider |
| Тестовые запросы пройдены | 0-5 |
| Среднее число результатов |  |
| Доля результатов с price |  |
| Доля результатов с URL |  |
| Доля результатов с region |  |
| Дата объявления доступна | Да/нет/частично |
| Машинные ошибки доступны | Да/нет |
| Оценка стоимости в месяц |  |
| Главный технический риск |  |
| Решение | go / hold / no-go |

## 8. Архитектурный Вывод

До окончания self-service spike не нужно делать БД, UI и scheduler для будущего модуля.

Единственная архитектура, которую можно считать стабильной заранее:

```text
EquipmentPricePosition
  -> PriceDataProvider
    -> ExternalListing[]
      -> DailyPriceSnapshot
```

Граница интеграции:

```text
Provider-specific API/actor output
  -> provider adapter
  -> normalized ExternalListing
  -> calculation min/max/median
```

Так мы не привязываем будущий модуль к Apify, Bright Data или любому другому источнику.

## 9. Следующий Технический Шаг

Нужен не контакт с людьми, а один из вариантов:

1. Получить/создать Apify API token и выполнить пробный запуск actor по одной позиции.
2. Если Apify не проходит, проверить Bright Data self-service scraper/API.
3. Если оба варианта не проходят, зафиксировать `hold_no_source` или отдельно обсуждать прямой parser research.

Без работающего self-service источника данных начинать разработку модуля преждевременно.

