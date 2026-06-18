# POC Clean-Room Avito Parser Worker

Дата: 2026-06-17.

Статус: `pipeline_works_http_unstable`.

Локация POC:

```text
/tmp/avito-monitor-worker-poc
```

POC не включён в MVP и не добавлен в основной код проекта.

## 1. Что Сделано

Создан минимальный clean-room worker:

```text
/tmp/avito-monitor-worker-poc/src/worker.py
```

Конфиг:

```text
/tmp/avito-monitor-worker-poc/config/search_jobs.json
```

Worker умеет:

- читать список search jobs;
- делать one-shot запрос к Avito;
- сохранять raw HTML;
- извлекать embedded JSON state;
- получать raw listings;
- нормализовать объявления;
- применять простой relevance filter;
- сохранять `relevant_listings.json`;
- сохранять `rejected_listings.json`;
- считать `daily_snapshot.json`;
- писать `run_report.json`.

## 2. Тестовая Позиция

```text
Kyocera ECOSYS M2040dn
```

URL:

```text
https://www.avito.ru/all/orgtehnika_i_rashodniki?q=Kyocera+ECOSYS+M2040dn
```

## 3. Результаты Live HTTP

Первый live run:

```text
HTTP 403
status: blocked
```

После выравнивания HTTP strategy с подтверждённым Duff89 POC:

```text
HTTP 200
HTML сохранён
```

Но первая версия detection ошибочно классифицировала страницу как CAPTCHA, потому что искала строку `captcha` во всём большом HTML. В нормальном HTML Avito такие строки могут встречаться в JS/AB-конфигурациях.

Detection исправлен:

- `403/429` считаются блокировкой;
- `Доступ ограничен` считается блокировкой;
- `проблема с IP` считается блокировкой;
- `подтвердите, что вы не робот` считается CAPTCHA;
- само слово `captcha` внутри большого HTML больше не является достаточным признаком.

После исправления проверка на сохранённом `HTTP 200` HTML:

```text
blocked: false
items extracted: 50
```

Финальный live run снова получил:

```text
HTTP 403
```

Вывод:

```text
pipeline работает, но live HTTP доступ нестабилен.
```

Это совпадает с общим риском Avito scraping: даже рабочий подход может получать периодические блокировки.

## 4. Offline Проверка Pipeline На Сохранённом Live HTML

Чтобы не делать лишние запросы к Avito, сохранённый успешный `HTTP 200` HTML был обработан offline.

Результат:

```text
raw: 50
normalized: 50
relevant: 29
rejected: 21
```

Snapshot:

```json
{
  "job_code": "kyocera_m2040dn",
  "position_name": "Kyocera ECOSYS M2040dn",
  "snapshot_date": "2026-06-17",
  "source": "avito",
  "status": "success",
  "raw_count": 50,
  "normalized_count": 50,
  "relevant_count": 29,
  "rejected_count": 21,
  "min_price": 7500,
  "max_price": 65000,
  "median_price": 23500,
  "currency": "RUB"
}
```

Файлы:

```text
/tmp/avito-monitor-worker-poc/runs/offline_from_20260617T121743Z/kyocera_m2040dn/raw_listings.json
/tmp/avito-monitor-worker-poc/runs/offline_from_20260617T121743Z/kyocera_m2040dn/normalized_listings.json
/tmp/avito-monitor-worker-poc/runs/offline_from_20260617T121743Z/kyocera_m2040dn/relevant_listings.json
/tmp/avito-monitor-worker-poc/runs/offline_from_20260617T121743Z/kyocera_m2040dn/rejected_listings.json
/tmp/avito-monitor-worker-poc/runs/offline_from_20260617T121743Z/kyocera_m2040dn/daily_snapshot.json
```

## 5. Что Подтверждено

Подтверждено:

- clean-room extractor может извлечь 50 карточек из Avito HTML;
- нормализация в нашу схему работает;
- raw snapshot сохраняется до фильтрации;
- relevance filter разделяет объявления на `relevant` и `rejected`;
- daily snapshot считается по relevant объявлениям;
- JSON output соответствует целевой архитектуре.

## 6. Что Не Подтверждено

Не подтверждено:

- стабильный live HTTP доступ без cookies/proxy;
- production-надежность;
- работа по 3-5 позициям;
- работа 3-5 дней подряд;
- качество relevance filter для всех категорий.

## 7. Проблема Relevance Filter

`min_price = 7500` для Kyocera M2040dn выглядит подозрительно. Это может быть:

- неполный комплект;
- неисправное устройство;
- донор;
- запчасть, не отловленная стоп-словами;
- реальное дешёвое объявление.

Вывод:

```text
первый relevance filter недостаточен для production min/max.
```

Нужно усилить фильтр:

- добавить отдельные причины `repair_or_defect`;
- учитывать слова `трещит`, `требуется`, `без блока`, `не хватает`, `пробег`, `донор`;
- ввести `unknown` вместо автоматического `relevant` для спорных объявлений;
- считать min/max только по `relevant`, а `unknown` показывать отдельно.

## 8. Решение

Текущий статус:

```text
go_clean_room_parser_poc_phase_2
```

Но с оговоркой:

```text
нужно решить live HTTP stability до разработки production-модуля
```

## 9. Следующий Шаг

Следующий экономный шаг:

1. Не делать больше частых live-запросов сегодня.
2. Доработать POC worker на сохранённых HTML:
   - улучшить relevance filter;
   - добавить `unknown`;
   - улучшить отчётность по reject reasons.
3. Потом сделать один осторожный live run через несколько часов или на следующий день.
4. Если live run снова периодически проходит, запускать endurance test:
   - 3 позиции;
   - 1 запуск в день;
   - 3-5 дней.

## 10. Phase 2: Улучшение Relevance Filter Offline

Без новых запросов к Avito worker был доработан на сохранённом HTML.

Добавлено:

- статус `unknown`;
- отдельные причины `repair_or_incomplete`;
- отдельные причины `accessory_or_consumable`;
- сохранение `unknown_listings.json`;
- расчёт min/max/median только по `relevant`;
- более осторожная обработка аксессуаров: аксессуары отклоняются по заголовку, а не по любому упоминанию в описании.

Причина: нормальное объявление МФУ может содержать в описании "картридж в комплекте", и такое объявление нельзя автоматически отклонять.

Первый пересчёт после добавления `unknown`:

```text
raw: 50
normalized: 50
relevant: 25
unknown: 3
rejected: 22
min_price: 7500
max_price: 65000
median_price: 23990
```

Проблема: в relevant попал товар `Блок проявки Kyocera DV-1150`, цена `7500`. Это не МФУ, а запчасть.

После добавления стоп-сигналов:

- `блок проявки`;
- `фотовал`;
- `ракель`;
- `прижимная планка`;
- accessory detection по title.

Результат:

```text
raw: 50
normalized: 50
relevant: 37
unknown: 3
rejected: 10
min_price: 15000
max_price: 65000
median_price: 23995
```

Примеры дешёвых relevant:

| Цена | Название |
|---:|---|
| 15 000 | `Мфу Kyocera ecosys m2040dn` |
| 15 000 | `Принтер Kyocera ecosys M2040dn` |
| 16 000 | `Мфу kyocera ecosys m2040dn` |
| 18 000 | `Kyocera ecosys m2040dn` |

Примеры rejected:

| Цена | Название | Причина |
|---:|---|---|
| 1 050 | `Kyocera DK-1150 - фотовал, ракель` | accessory |
| 5 300 | `Картридж Kyocera TK-1170 для M2040dn/M2540dn/M2640` | accessory |
| 7 500 | `Блок проявки Kyocera DV-1150` | accessory |
| 9 999 | `Печка в Kyocera Ecosys M2040dn` | accessory |
| 10 000 | `Мфу kyocera ecosys m2040dn` | donor/repair/spare parts |

Примеры unknown:

| Цена | Название | Причина |
|---:|---|---|
| 13 000 | `Мфу kyocera ecosys m2040dn` | отсутствует лоток |
| 13 000 | `Мфу kyocera ecosys m2040dn` | не хватает крышки |
| 33 000 | `Мфу Kyocera ecosys m2040dn лазерное` | упоминание термоплёнки |

Вывод:

```text
relevance filter стал пригоден для POC, но требует настройки по каждой категории оборудования.
```

Важная методика:

- `relevant` участвует в min/max/median;
- `unknown` не участвует в min/max/median, но показывается оценщику;
- `rejected` хранится для аудита, но не влияет на расчёт.

