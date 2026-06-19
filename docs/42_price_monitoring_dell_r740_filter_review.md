# Dell R740 Filter Review

Дата: 2026-06-19

Источник: Day 2 official run `20260619T082828Z`.

## Summary

`dell_r740` впервые дал usable snapshot после замены search URL:

```text
status: success
http_status: 200
raw: 50
normalized: 50
relevant: 11
unknown: 9
rejected: 30
median: 139500
```

Snapshot полезен, но фильтр слишком агрессивно режет полноценные серверы.

## Relevant Examples

Примеры relevant объявлений:

```text
167000 Сервер Dell R740xd 24SFF 2x6148 64GB H730p 2x750W PowerEdge 2U
100000 Сервер Dell R740 8SFF
115000 Сервер Dell PowerEdge R740 R740xd
139500 Сервер dell r740xd
120000 Сервер Dell R740 XD 12LFF PowerEdge 12x 3.5" 2U
235000 Сервер Dell PowerEdge R740XD для видеонаблюдения
```

Диапазон relevant выглядит правдоподобно для б/у серверов:

```text
min: 100000
max: 235000
median: 139500
```

## Unknown Examples

Unknown в основном ниже `price_min`:

```text
9000 Райзеры для dell EMC poweredge R740
16000 Intel Xeon Silver 4215R
7000 Сетевая карта Dell 068M95 / Intel X710 4*10Gb SFP+
2500 Вентилятор Dell R740 R7425 high performance 04VXP3
4800 Радиатор dell R740 0trjt7
100 Бу Сервер dell PowerEdge R740
```

Большинство unknown выглядят как запчасти или подозрительно дешёвые карточки. Оставлять их вне медианы правильно.

## False Rejection Risk

Часть rejected выглядит как полноценные серверы:

```text
242000 Сервер dell R740xd 28SFF 2x6240 128GB, H730
174000 Сервер dell R740xd 28SFF 2x6138 64GB, H730
166000 Сервер dell R740 8LFF 2x6146 128GB, H730
240000 Сервер dell R740 8LFF 2x6240 192GB, H730
218000 Сервер dell R740xd 28SFF 2x6146 128GB, H730
```

Причина: слишком широкие negative terms:

```text
процессор
память
диск
raid
контроллер
```

Для серверов эти слова часто являются характеристиками комплектации, а не признаком запчасти.

## Filter Change For Day 3

В `search_jobs.example.json` и локальном `search_jobs.json` broad negative terms для `dell_r740` заменены на более точные признаки запчастей:

```text
процессор для
память для
жесткий диск для
диск для
raid контроллер
контроллер для
райзер
радиатор
вентилятор
сетевая карта
серверная плата
материнская плата
```

Сохраняются общие reject terms:

```text
блок питания
салазки
корзина
лицензия
донор
запчасти
запчасть
ремонт
нерабоч
```

## Expected Day 3 Signal

После смягчения фильтра для Dell ожидается:

- relevant count выше 11;
- rejected count ниже 30;
- median может подняться, если ранее дорогие полноценные серверы ошибочно отбрасывались;
- unknown должны остаться в основном низкоценовыми запчастями.

Если relevant count резко вырастет, перед `go_worker_prototype` нужно дополнительно проверить, не попали ли в median комплектующие.

## Decision

Текущее решение:

```text
adjust_filters_offline_then_continue_day_3
```

