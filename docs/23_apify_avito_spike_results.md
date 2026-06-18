# Результаты Apify Avito Technical Spike

Дата: 2026-06-17.

Статус: `no_go_paid_service`.

Связанные документы:

- `docs/20_intermediary_avito_data_services.md`;
- `docs/22_avito_self_service_technical_spike.md`.

## 1. Что Проверяли

Проверялся self-service вариант получения данных Avito через Apify actor:

```text
server0/avito-scraper
```

Цель проверки:

- запустить actor через API без ручного UI;
- получить JSON dataset;
- проверить наличие полей `title`, `price`, `url`, `region/location`, `postedDate`;
- оценить релевантность выдачи для будущего мониторинга цен оборудования.

## 2. Условия Запуска

Параметры:

```json
{
  "region": "rossiya",
  "maxItems": 10,
  "sort": "date",
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"],
    "apifyProxyCountry": "RU"
  }
}
```

Тестовые запросы:

- `Kyocera ECOSYS M2040dn`;
- `HP LaserJet Pro MFP M426`;
- `Lenovo ThinkPad T14`;
- `Dell PowerEdge R740`;
- `Dell P2419H`.

## 3. Технический Результат

API token работает.

Actor запускается через Apify API.

Результаты сохраняются в dataset и доступны как JSON.

Поля в output:

- `id`;
- `title`;
- `price`;
- `priceString`;
- `currency`;
- `url`;
- `location`;
- `locationId`;
- `lat`;
- `lng`;
- `categoryId`;
- `categorySlug`;
- `categoryName`;
- `postedDate`;
- `postedTimestamp`;
- `imageUrl`;
- `photoCount`;
- `description`;
- `sellerRating`;
- `sellerReviews`;
- `isVerified`;
- `isNew`;
- `isPromoted`;
- `region`;
- `keyword`;
- `scrapedAt`.

Минимально нужные поля для модуля мониторинга есть.

## 4. Результаты По Запросам

| Запрос | HTTP / run status | Записей | Качество |
|---|---|---:|---|
| `Kyocera ECOSYS M2040dn` | `201 / SUCCEEDED`, повторный batch дал 0 записей | 0-5 | Нестабильно, много расходников/запчастей |
| `HP LaserJet Pro MFP M426` | `201 / SUCCEEDED` | 10 | Низкое: в топе много картриджей и запчастей, только 1 явно МФУ |
| `Lenovo ThinkPad T14` | `201 / SUCCEEDED` | 10 | Среднее/хорошее: большинство ноутбуки ThinkPad T14/T14s, есть шум |
| `Dell PowerEdge R740` | `201 / SUCCEEDED` | 10 | Среднее: большинство серверы R740/R740xd, есть память/БП/панель |
| `Dell P2419H` | sync endpoint дал `502`, run `SUCCEEDED`, dataset доступен | 10 | Среднее: часть мониторы, часть аксессуары/платы/нерелевантные Dell |

Важно: `502` на sync endpoint не означает провал actor run. В этом случае dataset можно забрать отдельным запросом по `defaultDatasetId`.

## 5. Примеры Найденных Цен

Примеры релевантных или частично релевантных записей:

| Запрос | Пример title | Цена |
|---|---|---:|
| `HP LaserJet Pro MFP M426` | `Мфу HP LaserJet Pro MFP M426fdn` | 15 999 RUB |
| `Lenovo ThinkPad T14` | `Thinkpad T14 gen 5 Ryzen 7 Pro 8840U 16/512gb` | 69 999 RUB |
| `Dell PowerEdge R740` | `Сервер Dell R740 XD 24SFF PowerEdge 24x 2.5" 2U` | 115 000 RUB |
| `Dell P2419H` | `Монитор Dell p2419h` | 4 000 RUB |

Примеры шума:

- картриджи и тонер для `HP M426`;
- печка, картридж, блок проявки для `Kyocera M2040dn`;
- память, блок питания, передняя панель для `Dell R740`;
- soundbar и плата питания для `Dell P2419H`.

## 6. Стоимость Первого Spike

По последним 6 runs Apify показал суммарный `usageTotalUsd`:

```text
0.4183035883038276 USD
```

Среднее:

```text
~0.07 USD / run
```

Это не финальная экономика production-режима. На стоимость будут влиять:

- actor pricing;
- число результатов;
- browser fallback;
- proxy usage;
- retries;
- объём dataset reads/writes;
- частота запуска.

Ориентировочно для 100-200 позиций ежедневно только overhead runs может стать заметным, поэтому нужен отдельный расчёт на лимите 50-100 объявлений.

## 7. Главный Вывод

Apify actor технически подходит как источник сырых Avito listings:

- API-запуск есть;
- JSON output есть;
- цены числом есть;
- URL объявления есть;
- даты объявления есть;
- регион/локация частично есть;
- direct parser на нашем сервере не нужен для первого технического варианта.

Но actor не решает проблему релевантности.

Если сразу считать `min(price)` и `max(price)` по сырой выдаче, результат будет неправильным: min почти всегда будет приходить от расходников, запчастей, картриджей, кабелей, плат, нерабочих комплектующих или нерелевантных объявлений.

## 8. Архитектурное Следствие

В модуле нужен не только `PriceDataProvider`, но и слой нормализации/фильтрации:

```text
PriceDataProvider
  -> RawExternalListing[]
  -> ListingRelevanceFilter
  -> RelevantListing[]
  -> DailyPriceSnapshot
```

Без `ListingRelevanceFilter` автоматический min/max будет методологически слабым.

Минимальный фильтр должен уметь:

- проверять обязательные токены модели;
- исключать расходники и запчасти;
- исключать "для", "картридж", "тонер", "печка", "плата", "блок питания", "ролик", "шлейф", "панель" и подобные слова для оборудования;
- учитывать категорию Avito;
- применять price floor/ceiling по типу позиции;
- сохранять rejected listings для аудита.

## 9. Решение

Текущий статус:

```text
no_go_paid_service
```

Apify технически подтвердил возможность получения структурированных данных Avito, но не подходит как целевой источник, потому что это платный сервис. Для проекта платный внешний источник данных сейчас исключён.

Дополнительный технический вывод остаётся полезным: даже при наличии источника данных нужен слой фильтрации релевантности, иначе min/max будут загрязнены расходниками и запчастями.

## 10. Следующий Технический Шаг

Так как платный источник не подходит, следующий шаг меняется:

1. Не развивать Apify adapter как основной вариант.
2. Не делать production-расчёты стоимости Apify.
3. Исследовать бесплатные или self-hosted варианты:
   - ручной импорт CSV/Excel как временный источник;
   - полуавтоматический сбор по сохранённым URL, если пользователь сам получает URL из браузера;
   - локальный parser research с явной фиксацией рисков Avito `429/CAPTCHA/robots`;
   - альтернативные открытые источники цен, если они есть для конкретных категорий оборудования.
4. Сохранить требование к `ListingRelevanceFilter` для любого будущего источника.

До появления бесплатного или приемлемого self-hosted источника данных разработку автоматического daily monitoring начинать преждевременно.
