# Оценщик: Risk Register и Decision Matrix

Дата: 2026-06-18

Статус: offline decision support перед day 2 endurance.

## Текущая Позиция

Модуль оценки рыночной цены остаётся research-направлением. Основное приложение, миграции, backend-модели и UI `/pricing` не начинаются до решения `go_worker_prototype`.

Day 1 endurance показал частичную работоспособность и нестабильность HTTP-доступа:

```text
kyocera_m2040dn: HTTP 403 blocked
lenovo_t14: HTTP 200 success, raw 50, relevant 30, median 29450
dell_r740: HTTP 200 page_not_found, fixed URL prepared for day 2
```

Текущее решение:

```text
continue_endurance_with_caution
```

## Risk Register

| Risk | Probability | Impact | Signal | Mitigation |
| --- | --- | --- | --- | --- |
| Avito blocks direct HTTP access | High | High | `HTTP 403`, `HTTP 429`, CAPTCHA, empty restricted page | One live run per UTC day, no retries after block, no bypass, classify as `access_restricted_ip` |
| Avito returns semantic error with `HTTP 200` | Medium | Medium | `page_not_found`, region/category mismatch, no listing cards | Detect parser error from HTML content, avoid treating as real `no_data` |
| Layout changes break extraction | Medium | High | raw HTML exists, but normalized count drops to zero | Keep raw snapshots, add parser-error classification, review HTML before productizing |
| Search URL too narrow or wrong | Medium | Medium | valid HTTP response but irrelevant or no cards | Prefer broad query URLs during endurance, validate each job manually in day docs |
| Median price is distorted by irrelevant listings | Medium | High | high `unknown`/`rejected`, suspicious min/max spread | Count only `relevant`, keep rejected reasons, require category-specific filters before production |
| Daily snapshots are not reproducible | Medium | High | different counts with same job over short time | Use one scheduled snapshot per day, store raw snapshot and normalized output |
| Legal or ToS constraints are unclear | Medium | High | need for production scraping decision | Keep research isolated, avoid bypass techniques, require explicit owner decision before production |
| Third-party parser code cannot be reused | Confirmed | Medium | missing or unclear LICENSE in checked parser | Continue clean-room implementation only |
| Paid data providers are excluded | Confirmed | Medium | Apify/Bright Data/etc. not acceptable as production path | Keep them as research evidence only, not implementation dependency |
| Product work starts too early | Medium | High | migrations/UI before data source is proven | Gate backend/UI work on `go_worker_prototype` only |

## Decision Matrix

| Decision | Use When | Allowed Next Work | Blocked Work |
| --- | --- | --- | --- |
| `continue_endurance_with_caution` | At least one job succeeds with valid relevant listings, and failures are classified clearly | Continue 1 live run per UTC day, improve offline reports, refine filters conservatively | Production integration, migrations, `/pricing` UI |
| `hold_http_unstable` | Most jobs are blocked, CAPTCHA/403 dominates, or results cannot support a daily snapshot | Stop live Avito runs, summarize findings, decide whether to pause module | More HTTP scraping attempts, production integration |
| `browser_profile_research` | HTTP worker is too unstable, but business value still justifies research | Open separate research track for operator-controlled browser profile mode | Automated bypass, hidden proxy/cookie work, production integration |
| `go_worker_prototype` | 3-5 daily runs meet gate criteria: stable enough access, explainable failures, useful medians, acceptable risk | Start backend prototype plan: models, retention, API, worker schedule, admin UI design | Direct production rollout without review |
| `no_go_price_monitoring` | Source risk is unacceptable or data quality is not useful | Archive research, keep docs for future reference | Further Avito integration work |

## Gate Before `go_worker_prototype`

Required evidence:

- 3-5 calendar days of endurance data.
- Three tracked jobs attempted each day.
- No more than one live run per UTC day.
- Every failure classified as blocked, parser error, no data, or config issue.
- At least one category has repeated useful `relevant` listings and plausible median.
- Raw snapshots and offline reports are retained outside git.
- Legal/ToS and operational risk accepted by project owner.

Until all required evidence exists, the only valid decisions are:

```text
continue_endurance_with_caution
hold_http_unstable
browser_profile_research
no_go_price_monitoring
```

## Immediate Next Step

For day 2, follow:

```text
docs/38_price_monitoring_day2_operator_runbook.md
```

Expected output after day 2:

```text
docs/34_price_monitoring_endurance_day_2.md
docs/37_price_monitoring_gate_summary.md
runs/{run_id}/offline_report.md
```
