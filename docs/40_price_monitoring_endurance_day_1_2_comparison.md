# Endurance Test Оценщика: Day 1 / Day 2 Comparison

Дата: 2026-06-19

Статус: offline analysis после второго live run.

## Official Runs

Официальными endurance-днями считаются только live runs, которые реально дошли до Avito:

| Day | Run | Date | Status |
|---:|---|---|---|
| 1 | `20260618T075423Z` | 2026-06-18 | `partial_success_http_unstable` |
| 2 | `20260619T082828Z` | 2026-06-19 | `success` |

Технический run `20260618T075301Z` не считается official endurance day:

```text
reason: DNS could not resolve www.avito.ru inside sandbox
classification: infrastructure_attempt
```

Его можно учитывать как проверку обработки `parser_error`, но не как evidence реакции Avito.

## Job Comparison

| Job | Day 1 | Day 2 | Interpretation |
|---|---|---|---|
| `kyocera_m2040dn` | `HTTP 403 blocked` | `HTTP 200 success`, relevant 41, median 25000 | Блокировка не повторилась; HTTP access нестабилен, но не полностью закрыт |
| `lenovo_t14` | `HTTP 200 success`, relevant 30, median 29450 | `HTTP 200 success`, relevant 30, median 27995 | Самая стабильная позиция; медиана близка между днями |
| `dell_r740` | `HTTP 200 no_data`, offline finding `page_not_found` | `HTTP 200 success`, relevant 11, median 139500 | Day 1 был config/search URL issue; широкий URL на Day 2 дал данные |

## Metrics

| Metric | Day 1 | Day 2 |
|---|---:|---:|
| Jobs total | 3 | 3 |
| Jobs success | 1 | 3 |
| Jobs blocked | 1 | 0 |
| Jobs parser/config issue | 1 | 0 |
| Jobs with usable median | 1 | 3 |

## Findings

- Day 2 materially improves confidence: all three jobs returned `HTTP 200` and produced usable relevant listings.
- Day 1 `kyocera_m2040dn` block remains a real risk because the same job returned `HTTP 403` one day earlier.
- Day 1 `dell_r740` should not be interpreted as real market `no_data`; it was a bad search/category URL and is now mitigated by the broader query.
- `lenovo_t14` is the best stability signal so far: relevant count stayed at 30 on both official days, and median moved from 29450 to 27995.
- `dell_r740` needs filter review before production: Day 2 had 11 relevant, 9 unknown, 30 rejected, with many rejected parts/accessories.

## Gate Interpretation

Current decision:

```text
continue_endurance_day_3
```

Do not choose `go_worker_prototype` yet:

- only 2 official endurance days exist;
- one official day had a real block;
- one successful day is not enough to prove production reliability;
- filter quality for server listings still needs review.

Do not choose `hold_http_unstable` yet:

- Day 2 had 3/3 successful jobs;
- Kyocera recovered from the Day 1 block;
- Dell issue was explained and mitigated.

## Next Day Criteria

Day 3 should answer:

1. Does `kyocera_m2040dn` stay successful or return to `HTTP 403`?
2. Does `lenovo_t14` remain stable around 30 relevant listings?
3. Does `dell_r740` keep producing server listings without `page_not_found`?
4. Does any job trigger CAPTCHA, `HTTP 429`, repeated `HTTP 403`, or parser error?

## Operational Rule

No more live Avito runs on 2026-06-19.

Next live run:

```text
2026-06-20 or later, one run per UTC day
```

