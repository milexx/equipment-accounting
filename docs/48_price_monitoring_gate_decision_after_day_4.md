# Gate Decision После Day 4: Оценщик

Дата: 2026-06-21

Статус: updated decision record после дополнительного endurance day.

## Inputs

Official endurance days:

| Day | Run | Status | Success | Blocked | Key Notes |
|---:|---|---|---:|---:|---|
| 1 | `20260618T075423Z` | `partial_success` | 1 | 1 | Kyocera `HTTP 403`; Dell bad URL / `page_not_found`; Lenovo success |
| 2 | `20260619T082828Z` | `success` | 3 | 0 | 3/3 success |
| 3 | `20260620T081446Z` | `partial_success` | 2 | 1 | Dell `HTTP 403`; Kyocera and Lenovo success |
| 4 | `20260621T131205Z` | `partial_success` | 0 | 3 | All jobs `HTTP 403`, finding `access_restricted_ip` |

Generated gate summary after Day 4:

```text
recommendation: continue_endurance
runs_seen_total: 5
runs_total: 4
runs_excluded: 1
runs_with_two_successes: 2
runs_with_majority_blocked_or_failed: 1
```

## Interpretation

Day 4 is a negative signal for unattended Avito usage.

The source remains useful for an experimental, manual, stop-on-block prototype because previous days produced valid data and the system now preserves blocked outcomes as history. It is not acceptable to increase automation confidence after a day where all three monitored jobs returned `HTTP 403`.

## Decision

```text
decision: continue_endurance_with_automation_hold
```

This supersedes the Day 3 confidence level for automation decisions.

Allowed:

- keep the read-only `/pricing` UI;
- keep imported historical snapshots, including blocked points;
- keep manual import and manual analysis tooling;
- continue endurance with at most one live run per UTC day;
- improve reporting around source health and blocked rate.

Not allowed yet:

- scheduler;
- unattended daily production runs;
- retry loop after `HTTP 403`, `HTTP 429`, CAPTCHA, or access restricted;
- proxy rotation;
- cookies/session profile;
- CAPTCHA bypass;
- presenting Avito as a stable valuation source.

## Operational Rule

Do not run another live Avito request on 2026-06-21 UTC.

Next live endurance run, if needed:

```text
2026-06-22 or later, one run per UTC day
```

## Product Impact

The correct MVP behavior is to show price history with explicit source statuses. A blocked day is data about source health, not a failed application state.

For user-facing language, prefer:

```text
Источник временно недоступен / блокировка доступа. Последняя успешная оценка сохранена в истории.
```
