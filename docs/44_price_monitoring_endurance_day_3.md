# Endurance Test Оценщика: День 3

Дата: 2026-06-20.

Статус: `partial_success`.

## Live Run

```text
run_id: 20260620T081446Z
started_at: 2026-06-20T08:14:46.108386Z
finished_at: 2026-06-20T08:15:00.634895Z
status: partial_success
jobs_total: 3
```

## Результаты По Позициям

| Позиция | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median | Findings |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `dell_r740` | 403 | `blocked` | 0 | 0 | 0 | 0 | 0 | - | - | - | access_restricted_ip |
| `kyocera_m2040dn` | 200 | `success` | 50 | 50 | 33 | 7 | 10 | 7500 | 78000 | 25000 | - |
| `lenovo_t14` | 200 | `success` | 50 | 50 | 31 | 0 | 19 | 16990 | 51999 | 27990 | - |

## Наблюдения

- `dell_r740`: `blocked`, block_reason: `http_403`; findings: `access_restricted_ip`.
- `kyocera_m2040dn`: `success`, top rejected reason: `price_below_min` (4).
- `lenovo_t14`: `success`, top rejected reason: `negative_term:экран` (8).

## Решение После Запуска

```text
continue_endurance_day_4
```

## Следующий Шаг

Не делать повторный live run 2026-06-20; следующий запуск 2026-06-21 или позже, затем обновить gate decision.
