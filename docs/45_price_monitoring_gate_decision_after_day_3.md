# Gate Decision После Day 3: Оценщик

Дата: 2026-06-20

Статус: decision record после трёх official endurance days.

## Inputs

Official endurance days:

| Day | Run | Status | Success | Blocked | Key Notes |
|---:|---|---|---:|---:|---|
| 1 | `20260618T075423Z` | `partial_success` | 1 | 1 | Kyocera `HTTP 403`; Dell bad URL / `page_not_found`; Lenovo success |
| 2 | `20260619T082828Z` | `success` | 3 | 0 | 3/3 success |
| 3 | `20260620T081446Z` | `partial_success` | 2 | 1 | Dell `HTTP 403`; Kyocera and Lenovo success |

Excluded infrastructure attempt:

```text
20260618T075301Z: infrastructure_attempt, DNS/network sandbox, not an official endurance day
```

Current generated gate summary:

```text
recommendation: go_worker_prototype_candidate
runs_seen_total: 4
runs_total: 3
runs_excluded: 1
runs_with_two_successes: 2
runs_with_majority_blocked_or_failed: 0
```

## Interpretation

The source is usable for an experimental worker prototype, but not reliable enough for an unattended production promise.

Evidence supporting prototype:

- 3 official endurance days completed.
- 2 of 3 official days had at least 2 successful jobs.
- No official day had blocked/parser errors dominating the run.
- `lenovo_t14` succeeded 3/3 days with stable median around 28-30k.
- `kyocera_m2040dn` recovered after Day 1 `HTTP 403` and succeeded on Days 2 and 3.
- `dell_r740` produced useful data on Day 2 after search URL correction.

Evidence against immediate production confidence:

- `HTTP 403` occurred on Day 1 and Day 3.
- `dell_r740` is unstable: bad URL/no data on Day 1, success on Day 2, blocked on Day 3.
- Dell filter quality still needs validation after Day 3 was blocked and could not test the adjusted negative terms.
- Avito access must remain stop-on-block; no retry loop, proxy rotation, cookies, or CAPTCHA bypass.

## Decision

```text
decision: go_worker_prototype_candidate_with_constraints
```

This means:

- it is acceptable to start the backend prototype planning/design step;
- it is not yet acceptable to market the source as production-stable;
- implementation must preserve strict operational limits;
- the first integrated version must be explicitly experimental.

## Allowed Next Work

Allowed now:

- prepare backend implementation task breakdown;
- create a migration/API/UI implementation plan;
- start a small backend skeleton only if explicitly approved after this decision;
- keep Avito adapter behind a source abstraction;
- design stop-on-block handling and parser error persistence.

Allowed after explicit approval:

- add `pricing` database models;
- add Alembic migration;
- add pricing service layer;
- port clean-room parser into an adapter;
- add manual run only, before scheduler.

## Still Blocked

Blocked until explicit implementation approval:

- UI `/pricing`;
- scheduler;
- automatic daily production runs;
- any retry loop after `HTTP 403`, `HTTP 429`, CAPTCHA, or access restricted;
- proxy rotation;
- cookies/session profile;
- CAPTCHA bypass;
- paid data providers.

## Required Constraints For Prototype

The prototype must:

- treat Avito as an unstable source;
- save `blocked`, `captcha`, `parser_error`, and `no_data` as first-class outcomes;
- stop the current source/job on block;
- never retry aggressively in the same run;
- keep raw HTML out of git;
- calculate daily median only from `relevant` observations;
- keep `unknown` and `rejected` available for audit;
- expose source health in admin views.

## Recommended Next Step

Do not start coding UI first.

Next engineering step:

```text
draft backend skeleton implementation checklist
```

That checklist should map directly to:

```text
docs/43_price_monitoring_post_gate_integration_backlog.md
```

Optional research step:

```text
continue_endurance_day_4 on 2026-06-21 or later
```

Day 4 is useful but not required before drafting the backend skeleton. It is required before increasing automation confidence.

