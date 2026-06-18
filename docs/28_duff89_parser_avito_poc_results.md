# POC Duff89/parser_avito На Реальном Avito

Дата: 2026-06-17.

Статус: `works_as_reference_not_as_target_tool`.

Репозиторий:

```text
https://github.com/Duff89/parser_avito
```

Локальная копия:

```text
/tmp/duff89-parser-avito
```

POC выполнялся изолированно от MVP:

- отдельный venv: `/tmp/duff89-parser-avito-venv`;
- отдельный config в `/tmp`;
- без proxy;
- без cookies;
- без телефонов;
- без уведомлений;
- `one_time_start=true`;
- один URL;
- одна страница.

## 1. Зачем Проверяли

Нужно было подтвердить, что найденный open-source parser действительно работает в нашей среде. Иначе проектировать собственный parser по его идеям рискованно.

## 2. Тестовый URL

```text
https://www.avito.ru/all/orgtehnika_i_rashodniki?q=Kyocera+ECOSYS+M2040dn
```

Категория: оргтехника и расходники.

Поиск: `Kyocera ECOSYS M2040dn`.

## 3. Результат Первого Запуска

Первый one-shot запуск:

```text
Хорошие запросы: 1
Плохие запросы: 0
Объявлений перед чисткой: 50
После фильтрации viewed: 50
После остальных фильтров: 49
Сохранено: 49
```

Создан файл:

```text
/tmp/duff89-parser-avito/result/avito.xlsx
```

SQLite:

```text
viewed records: 49
```

Вывод:

```text
Duff89/parser_avito реально получил данные Avito без cookies/proxy в нашей среде.
```

## 4. Качество Полученных Данных

Excel содержит 50 строк: 1 header + 49 объявлений.

Поля:

- `Название`;
- `Цена`;
- `URL`;
- `Описание`;
- `Дата публикации`;
- `Продавец`;
- `Адрес`;
- `Адрес пользователя`;
- `Координаты`;
- `Изображения`;
- `Поднято`;
- `Просмотры`;
- `Телефон`.

Примеры:

| Название | Цена | Дата публикации |
|---|---:|---|
| `Kyocera ecosys m2040dn` | 18 000 | 2026-06-09 |
| `Мфу kyocera ecosys m2040dn` | 13 000 | 2026-06-07 |
| `Мфу лазерное Kyocera ecosys M2040dn` | 25 000 | 2026-05-31 |
| `Мфу Kyocera Ecosys M2040dn/печатает отлично` | 25 000 | 2026-06-02 |
| `Мфу kyocera ecosys m2040dn` | 10 000 | 2026-06-17 |

Данные структурированы и пригодны для нормализации:

```text
title, price, url, description, published_at, seller, location
```

## 5. Качество Релевантности

Результат лучше, чем у Apify по тому же запросу:

- много полноценных МФУ;
- меньше расходников в первых строках;
- есть проблемные объявления "на запчасти", "донор", "без блока";
- есть близкая, но не та же модель `MA4000x (замена M2040dn)`.

Вывод:

```text
Даже при рабочем parser нужен ListingRelevanceFilter.
```

Примеры стоп-сигналов:

- `донор`;
- `на запчасти`;
- `без внутреннего блока`;
- `замена M2040dn`;
- `требуется замена печки`;
- слишком низкая цена для категории.

## 6. Результат Повторного Запуска

Второй one-shot запуск сразу после первого:

```text
Хорошие запросы: 1
Плохие запросы: 0
Объявлений перед чисткой: 50
После фильтрации viewed: 3
После остальных фильтров: 2
Сохранено: 2
```

Вывод:

```text
Parser оптимизирован под новые/изменившиеся объявления, а не под полный дневной срез.
```

Для нашего daily min/max это критично: повторно видимые объявления должны участвовать в дневном срезе каждый день.

## 7. Главный Технический Вывод

Duff89/parser_avito работает как proof that approach is viable:

- Avito HTML/embedded JSON доступен из нашей среды;
- `curl_cffi` browser impersonation сработал;
- 50 карточек извлечены;
- цена, URL, описание и дата публикации получены;
- Excel и SQLite output работают.

Но он не подходит как целевой инструмент "из коробки":

- нет лицензии;
- output заточен под notifications/new ads;
- viewed-фильтр ломает daily full snapshot;
- Excel не лучший формат для внутреннего pipeline;
- есть лишние компоненты: GUI, Telegram, VK, phone parsing;
- cookies/proxy/bypass механики нужно явно исключить или изолировать.

## 8. Что Это Значит Для Нашего Parser

Теперь можно проектировать собственный clean-room parser с гораздо большей уверенностью.

Нужна не копия Duff89, а целевой worker:

```text
avito-monitor-worker
  -> one-shot run
  -> full raw snapshot
  -> normalized JSON
  -> relevance filter
  -> daily min/max/median
```

Ключевые требования к нашему parser:

- не фильтровать viewed до сохранения raw snapshot;
- каждый запуск сохраняет полный список объявлений;
- `external_id + fetched_at` фиксируют факт наблюдения;
- блокировки фиксируются как `blocked`, без скрытого обхода;
- никаких телефонов;
- никаких уведомлений;
- output JSON/DB, не Excel как основной формат;
- фильтрация релевантности отдельным слоем.

## 9. Go/No-Go

Решение:

```text
go_clean_room_parser_design
```

Основание:

- рабочий source approach подтверждён;
- данные реально получены;
- структура данных достаточна;
- известны ограничения готового parser;
- можно писать свой минимальный целевой worker.

Ограничение:

```text
production stability не доказана одним запуском.
```

Перед production всё равно нужен endurance test:

- 3-5 URL;
- 3-5 дней;
- 1-2 запуска в день;
- без proxy/cookies;
- учёт 403/429/CAPTCHA.

## 10. Следующий Шаг

Описать проект собственного parser:

```text
docs/29_clean_room_avito_parser_design.md
```

В документе нужно зафиксировать:

- input config;
- HTTP strategy;
- embedded JSON extraction;
- pagination;
- normalized output schema;
- block/error handling;
- daily snapshot model;
- relevance filter;
- POC plan;
- границу с MVP.

