# Endurance Test Оценщика: День 1

Дата: 2026-06-18.

Статус: `partial_success_http_unstable`.

Связанные документы:

- `docs/32_price_monitoring_implementation_plan.md`;
- `research/avito-monitor-worker-poc/README.md`;
- `research/avito-monitor-worker-poc/config/search_jobs.example.json`.

## Условия Запуска

Цель: первый live run clean-room Avito worker на 3 позициях.

Параметры:

- позиции: `kyocera_m2040dn`, `lenovo_t14`, `dell_r740`;
- режим: `one_shot`;
- страниц на позицию: 1;
- timeout: 20 секунд;
- задержка между позициями: 5 секунд;
- cookies: нет;
- proxy: нет;
- CAPTCHA bypass: нет;
- retry при блокировке: нет.

## Инфраструктурная Попытка

Первый запуск внутри sandbox не дошёл до Avito:

```text
run_id: 20260618T075301Z
result: parser_error
reason: DNS could not resolve www.avito.ru
```

Эта попытка не считается проверкой реакции Avito, потому что сеть была заблокирована на уровне окружения.

## Реальный Live Run

```text
run_id: 20260618T075423Z
started_at: 2026-06-18T07:54:23Z
finished_at: 2026-06-18T07:54:36Z
status: partial_success
jobs_total: 3
jobs_success: 1
jobs_blocked: 1
jobs_failed: 0
```

## Результаты По Позициям

| Позиция | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `kyocera_m2040dn` | 403 | `blocked` | 0 | 0 | 0 | 0 | 0 | - | - | - |
| `lenovo_t14` | 200 | `success` | 50 | 50 | 30 | 0 | 20 | 16 990 | 99 000 | 29 450 |
| `dell_r740` | 200 | `no_data` | 0 | 0 | 0 | 0 | 0 | - | - | - |

## Наблюдения

- Worker подтвердил, что может получить и обработать live HTML минимум по одной позиции из трёх.
- `lenovo_t14` дал пригодный дневной snapshot: 50 raw listings, 30 relevant, median 29 450 RUB.
- `kyocera_m2040dn` получил `HTTP 403`, что подтверждает риск нестабильного доступа.
- `dell_r740` получил `HTTP 200`, но extractor не нашёл объявлений в embedded state. Это может означать реальный пустой результат, неподходящий search URL или отличие структуры страницы для категории.
- Пауза между позициями применена.
- При сетевых исключениях worker теперь пишет `parser_error`, а не роняет весь run.

## Решение После Дня 1

Текущее решение:

```text
continue_endurance_with_caution
```

Причина:

- источник не полностью заблокирован;
- один успешный snapshot есть;
- но 1 из 3 позиций уже получила `HTTP 403`, поэтому риск `hold_http_unstable` остаётся высоким.

## Следующий День

Правило:

```text
Не делать повторный live run 2026-06-18.
```

Следующий запуск:

```text
2026-06-19 или позже, один запуск в день.
```

Перед следующим запуском:

1. Не менять частоту запросов.
2. Не добавлять proxy/cookies/CAPTCHA bypass.
3. Проверить search URL для `dell_r740`, но не делать дополнительный live run в тот же день.
4. После day 2 сравнить:
   - повторится ли `HTTP 403` по Kyocera;
   - появятся ли данные по Dell;
   - сохранится ли успешность Lenovo.
