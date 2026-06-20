# Gate Summary: Price Monitoring Endurance

Recommendation: `go_worker_prototype_candidate`.

```text
runs_seen_total: 4
runs_total: 3
runs_excluded: 1
runs_with_two_successes: 2
runs_with_majority_blocked_or_failed: 0
```

## Runs

| Run | Started | Status | Success | Blocked/Captcha | Parser Errors |
|---|---|---|---:|---:|---:|
| `20260618T075423Z` | 2026-06-18T07:54:23.104180Z | `partial_success` | 1 | 1 | 0 |
| `20260619T082828Z` | 2026-06-19T08:28:28.230032Z | `success` | 3 | 0 | 0 |
| `20260620T081446Z` | 2026-06-20T08:14:46.108386Z | `partial_success` | 2 | 1 | 0 |

## Excluded Runs

| Run | Started | Status | Reason |
|---|---|---|---|
| `20260618T075301Z` | 2026-06-18T07:53:01.726097Z | `partial_success` | `infrastructure_attempt` |

## Job Totals

- `dell_r740`: `no_data`: 1, `success`: 1, `blocked`: 1
- `kyocera_m2040dn`: `success`: 2, `blocked`: 1
- `lenovo_t14`: `success`: 3

## Gate Rules

- `go_worker_prototype_candidate`: at least 3 runs, at least 2 runs with 2+ successful jobs, and no run where blocked/parser errors dominate.
- `hold_http_unstable_candidate`: at least 2 runs where blocked/parser errors dominate.
- `continue_endurance`: not enough evidence yet.
