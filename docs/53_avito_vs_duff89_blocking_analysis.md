# Avito Primary vs Duff89 Blocking Analysis

Date: 2026-06-22

## Question

Why can the primary `avito` worker get `HTTP 403`, while the immediate `avito_duff89` fallback succeeds against the same Avito search URL?

## Observed Facts

Run: `20260622T040909Z`

- `kyocera_m2040dn`: primary Avito returned `HTTP 403` / `access_restricted_ip`.
- `kyocera_m2040dn`: Duff89/parser_avito immediately fetched and saved 50 listings.
- `dell_r740`: primary Avito returned `HTTP 403` / `access_restricted_ip`.
- `dell_r740`: Duff89/parser_avito output existed and was recovered from XLSX.
- `lenovo_t14`: primary Avito returned `HTTP 200` and saved a normal snapshot.

This means the IP was not globally blocked for all Avito traffic during the run.

Response metadata:

- blocked primary responses came from `server: QRATOR`;
- blocked primary responses set only limited anti-bot/service cookies;
- successful Avito response set fuller session-like cookies and included normal SSR markers.

## Duff89 Configuration In This Run

Duff89 was used without:

- proxy;
- own cookies;
- webdriver;
- bypass API;
- phone parsing.

So `avito_duff89` success was not caused by proxy rotation, cookie reuse, CAPTCHA bypass, or browser automation.

## Most Likely Explanation

`avito` and `avito_duff89` are two different HTTP clients hitting the same Avito domain.

Avito/QRATOR appears to make a per-request risk decision based on a combination of:

- IP reputation at that moment;
- TLS/browser impersonation fingerprint;
- user-agent/header combination;
- URL/category/search pattern;
- recent request sequence;
- cookies issued or not issued on the current request.

The primary worker and Duff89 both use `curl_cffi`, but each request chooses its own browser impersonation/session. A request can therefore be blocked while the next nearby request is accepted. The Day 5 result is best interpreted as request-level blocking, not as a stable source-level status.

## Practical Implication

Do not record primary Avito `blocked` as the valuation result if Duff89 returns usable listings.

Correct semantics:

- primary Avito `blocked` is source-health evidence;
- Duff89 success is the final price source for that job;
- the persisted snapshot source must be `avito_duff89`.

## Added Diagnostic

The primary worker now writes request fingerprint metadata into `response_meta.json` for future runs:

```json
{
  "request": {
    "impersonate": "chrome|edge|firefox|safari",
    "headers": {
      "user-agent": "..."
    }
  }
}
```

This lets the next run compare blocked vs successful primary requests without repeating the run just for diagnostics.

## Next Check

On the next controlled run, compare for each job:

- primary `response_meta.request.impersonate`;
- primary `response_meta.request.headers.user-agent`;
- primary HTTP status and QRATOR cookies;
- Duff89 `good_request_count` / `bad_request_count`;
- final source and median.

If blocks correlate with specific `impersonate` values or UA/fingerprint mismatch, the primary worker can be made less random and closer to the known-good client profile.
