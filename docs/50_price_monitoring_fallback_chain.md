# Price Monitoring Fallback Chain

Date: 2026-06-21

## Decision

Use a strict manual fallback chain for each monitored item:

```text
1. Avito primary worker
2. Duff89/parser_avito fallback
3. Youla GraphQL fallback
```

The first source that returns relevant listings becomes the source of the daily snapshot.

## Behavior

For each job:

1. Run the current Avito worker.
2. If Avito returns `success`, save the Avito snapshot and stop.
3. If Avito returns `blocked`, `captcha`, `parser_error`, or `no_data`, run Duff89/parser_avito.
4. If Duff89 returns listings, normalize them, run the same relevance filter, save the snapshot with `source: avito_duff89`, and stop.
5. If Duff89 does not return listings, run Youla.
6. If Youla returns listings, normalize them, run the same relevance filter, save the snapshot with `source: youla`, and stop.
7. If all sources fail, keep the original Avito failure as the job result and preserve source-health evidence.

## Important Rule

A blocked Avito attempt is not the final valuation result if a fallback source returns usable listings.

It remains recorded as source-health context:

- `fallback_from: avito`
- `primary_status`
- `primary_http_status`
- Duff89 diagnostic report, if present

## Implementation Notes

Changed worker behavior:

- `duff89_probe.py` now writes `duff89_normalized_listings.json` when it can extract listings from Duff89 XLSX output.
- `worker.py` can build a normal `daily_snapshot.json` from `avito_duff89` listings.
- `worker.py` can query Youla GraphQL as the final fallback.
- `calculate_snapshot` now records the actual source used for the snapshot.
- `search_jobs.example.json` documents `youla_fallback`, disabled by default.
- local ignored `search_jobs.json` has Duff89 and Youla fallback enabled for manual testing.

## Source Status Semantics

Snapshot `source` values:

- `avito`: primary worker succeeded.
- `avito_duff89`: primary Avito failed, Duff89 produced usable listings.
- `youla`: Avito and Duff89 failed, Youla produced usable listings.

Job `status` values remain:

- `success`: at least one relevant listing after filtering.
- `no_data`: listings were fetched but none survived relevance filtering.
- `blocked` / `captcha`: primary/final source was blocked.
- `parser_error`: source response could not be parsed or source call failed.

## Constraints

- Manual runs only.
- No scheduler.
- No retry loop after block.
- No proxy rotation.
- No CAPTCHA bypass.
- Keep one Avito live run per UTC day unless explicitly overriding for a controlled test.

## Next Test

Run the chain once against the three monitored jobs:

```text
kyocera_m2040dn
lenovo_t14
dell_r740
```

Expected useful outcome:

- At least one job should produce `source: avito`, `source: avito_duff89`, or `source: youla`.
- If fallback source is `youla`, review rejected/unknown reasons carefully because Youla search is broader.
