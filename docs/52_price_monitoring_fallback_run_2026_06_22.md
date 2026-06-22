# Price Monitoring Fallback Run 2026-06-22

Date: 2026-06-22
Run ID: `20260622T040909Z`

## Scope

Controlled manual run of the pricing fallback chain:

```text
Avito -> Duff89/parser_avito -> Youla
```

No scheduler was enabled. The run was executed once for the UTC day.

## Result

Final run status: `success`

| Job | Final source | Status | Relevant | Unknown | Rejected | Median |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `kyocera_m2040dn` | `avito_duff89` | `success` | 37 | 5 | 8 | 24 999 |
| `lenovo_t14` | `avito` | `success` | 25 | 0 | 25 | 28 000 |
| `dell_r740` | `avito_duff89` | `success` | 41 | 0 | 9 | 200 000 |

## Source Behavior

- `lenovo_t14`: primary Avito worker succeeded.
- `kyocera_m2040dn`: primary Avito returned `HTTP 403` / `access_restricted_ip`; Duff89 returned usable listings.
- `dell_r740`: fallback data was recovered from Duff89 XLSX output and imported as `avito_duff89`.
- Youla was not needed for the final successful snapshots.

## Technical Fix

During the run, Duff89 reported saved XLSX files but the probe initially counted zero listings. Root cause: `duff89_probe.py` accepted a relative `job_dir`, then changed working directory to the Duff89 repository, so output was checked under the wrong directory.

Fix:

- resolve `repo` and `job_dir` before `os.chdir`;
- serialize Excel datetime-like values with `isoformat`;
- add regression tests for relative `job_dir` handling.

The run was repaired offline from the already saved Duff89 XLSX files. No additional live Avito request was made for the repair.

## Database Import

The run was imported into backend pricing tables:

```text
run_id=20260622T040909Z
status=success
observations_created=103
snapshots_saved=3
parser_errors_created=0
```

The `/pricing` page now shows the 2026-06-22 points in historical charts and journal rows with actual sources:

- `avito` for Lenovo;
- `avito_duff89` for Kyocera and Dell.

## Decision

Decision: `keep_fallback_chain_for_mvp_manual`

Rationale:

- The fallback chain produced usable daily snapshots for all three monitored items.
- Blocked Avito attempts did not pollute valuation history as final blocked price points.
- Actual source attribution is visible in the UI and persisted in the database.

Constraints remain:

- manual runs only;
- no scheduler;
- no retry loop after block;
- no proxy, cookies, or CAPTCHA bypass;
- one controlled live run per UTC day unless explicitly overridden.
