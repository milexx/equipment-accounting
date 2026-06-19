# Endurance Test Оценщика: День 2

Дата: 2026-06-19.

Статус: `success`.

## Live Run

```text
run_id: 20260619T082828Z
started_at: 2026-06-19T08:28:28.230032Z
finished_at: 2026-06-19T08:28:44.906710Z
status: success
jobs_total: 3
```

## Результаты По Позициям

| Позиция | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median | Findings |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `dell_r740` | 200 | `success` | 50 | 50 | 11 | 9 | 30 | 100000 | 235000 | 139500 | - |
| `kyocera_m2040dn` | 200 | `success` | 50 | 50 | 41 | 2 | 7 | 15000 | 78000 | 25000 | - |
| `lenovo_t14` | 200 | `success` | 50 | 50 | 30 | 0 | 20 | 16990 | 51999 | 27995 | - |

## Наблюдения

- `dell_r740`: `success`, top rejected reason: `negative_term:процессор` (19).
- `kyocera_m2040dn`: `success`, top rejected reason: `price_below_min` (3).
- `lenovo_t14`: `success`, top rejected reason: `negative_term:экран` (11).

## Решение После Запуска

```text
continue_endurance_day_3
```

## Следующий Шаг

Продолжить по gate checklist.
