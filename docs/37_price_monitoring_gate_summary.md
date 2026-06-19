# Gate Summary: Price Monitoring Endurance

Recommendation: `continue_endurance`.

```text
runs_total: 3
runs_with_two_successes: 1
runs_with_majority_blocked_or_failed: 1
```

## Runs

| Run | Started | Status | Success | Blocked/Captcha | Parser Errors |
|---|---|---|---:|---:|---:|
| `20260618T075301Z` | 2026-06-18T07:53:01.726097Z | `partial_success` | 0 | 0 | 3 |
| `20260618T075423Z` | 2026-06-18T07:54:23.104180Z | `partial_success` | 1 | 1 | 0 |
| `20260619T082828Z` | 2026-06-19T08:28:28.230032Z | `success` | 3 | 0 | 0 |

## Job Totals

- `dell_r740`: `parser_error`: 1, `no_data`: 1, `success`: 1
- `kyocera_m2040dn`: `parser_error`: 1, `blocked`: 1, `success`: 1
- `lenovo_t14`: `success`: 2, `parser_error`: 1

## Gate Rules

- `go_worker_prototype_candidate`: at least 3 runs, at least 2 runs with 2+ successful jobs, and no run where blocked/parser errors dominate.
- `hold_http_unstable_candidate`: at least 2 runs where blocked/parser errors dominate.
- `continue_endurance`: not enough evidence yet.
