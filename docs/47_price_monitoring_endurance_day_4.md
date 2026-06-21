# Endurance Test Оценщика: День 4

Дата: 2026-06-21.

Статус: `partial_success`.

## Live Run

```text
run_id: 20260621T131205Z
started_at: 2026-06-21T13:12:05.305277Z
finished_at: 2026-06-21T13:12:16.123032Z
status: partial_success
jobs_total: 3
```

## Результаты По Позициям

| Позиция | HTTP | Статус | Raw | Normalized | Relevant | Unknown | Rejected | Min | Max | Median | Findings |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `dell_r740` | 403 | `blocked` | 0 | 0 | 0 | 0 | 0 | - | - | - | access_restricted_ip |
| `kyocera_m2040dn` | 403 | `blocked` | 0 | 0 | 0 | 0 | 0 | - | - | - | access_restricted_ip |
| `lenovo_t14` | 403 | `blocked` | 0 | 0 | 0 | 0 | 0 | - | - | - | access_restricted_ip |

## Наблюдения

- `dell_r740`: `blocked`, block_reason: `http_403`; findings: `access_restricted_ip`.
- `kyocera_m2040dn`: `blocked`, block_reason: `http_403`; findings: `access_restricted_ip`.
- `lenovo_t14`: `blocked`, block_reason: `http_403`; findings: `access_restricted_ip`.

## Решение После Запуска

```text
hold_http_unstable_candidate
```

## Следующий Шаг

Продолжить по gate checklist.
