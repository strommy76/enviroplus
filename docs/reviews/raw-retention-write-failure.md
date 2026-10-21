# Raw retention: a failed write raises

> Moved from `~/projects/shared/docs/retention-write-failure-review.md` with the module (operator, 2026-10-20 23:23, "Yes, move it"). Where this record names `shared` branch revisions (`1cdf41b`, `1c37dc5`), they are where the work was reviewed. The code now lives in enviroplus `raw_retention.py`.

## Direction

The finding was raised by the enviroplus `feat/scd41-co2` review of a522210 (F5). It went to Bryan, 2026-10-20, under AGENTS D.

Bryan's words:
- 22:36 EDT: "Why does a failed write record success? Shouldn't success be determined after all writes are attempted? And shouldn't partial writes log success vs failure accurately? What is the optimal anti-fragile logic? What is generally accepted best practice?"
- 22:38 EDT, on pi-claude's recommendation: "no, fold it in"

Executor: pi-claude, by operator assignment (AGENTS B). The fold joins the enviroplus plan. Under AGENTS f this repository gets its own branch and review artifact, which is this file. The enviroplus side is recorded in enviroplus `docs/reviews/scd41-co2.md`.

## The defect

`_append()` caught `OSError`, logged it and returned `False`. `retain()` ignored that result and returned the arrival outcome. Callers then:
- wrote derived rows from a record the canonical tier did not hold, which breaks AGENTS j: derived state must be rebuildable;
- reported the failure only in a log line, which breaks n: a failure must not read as success.

The 2026-08-06 rationale was "losing an observation in both tiers to protect one is worse than losing it in one". But a derived row whose source is lost is not a protected observation. Nothing can rebuild it or check it.

## Practice adopted (AGENTS C)

| Practice | Here |
|---|---|
| Write-ahead: commit the source, then derive | Callers derive only after `retain()` returns |
| Success means durably stored | Return only after write, flush and fsync |
| Report failure, never success | `RetentionWriteError` (an `OSError`) |
| Leave the log readable | Unbuffered `os.write`, then `ftruncate` on failure |
| Retry only what was not stored | Dedup digest advances only on success |
| Surface failure where it is watched | Consumers exit; systemd restarts flat with no stop limit, `OnFailure` alerts each failure |

**Not adopted: an in-memory retry buffer.**
- No retention write failure has been observed on this host. It had 206 GB free on 2026-10-20 and NVMe storage.
- A buffer would die with the process anyway.
- Stopping on a failed log write is current write-ahead-log practice. PostgreSQL panics on fsync failure, since the 2018 fsync data-loss reports.
- systemd's flat restart, with no stop limit, is the retry, so collection resumes once the fault clears.

## Change

- `RetentionWriteError(OSError)` is new.
- `_append()` writes through an unbuffered descriptor: `os.open` with `O_APPEND`, an `os.write` loop over short writes, then `os.fsync`.
  - On any `OSError` it `ftruncate`s back to the length before the attempt, then raises.
  - A buffered text file could not do this. Its truncate first flushes the failed buffer, so the torn line survived (review S1).
- An unsafe provider key still raises `ValueError` before any I/O.
- `retain()` advances the dedup digest only after a successful append.
- A failure creating or reading the day file for dedup is also `RetentionWriteError`, so every failure to store raises the same error.
- `retain()` and `record_outcome()` document the raise.
- New `days(provider)` lists the retained day files. enviroplus replay uses it to find where retention begins, instead of reaching into private paths (h).

## Consumers (all in enviroplus, same plan)

| Consumer | Change |
|---|---|
| `ambient_wx.py`, `nws_wx.py`, `provider_collector.py` | `retain()` no longer wrapped in a log-only catch; the loop re-raises `RetentionWriteError` |
| `enviro_dash3.py` | Its Tier 1 write raises, ending the process before deriving |
| `ambient_wx`, `nws_wx`, `airnow_wx` units | Gain `OnFailure`; flat restart, no stop limit |
| `enviro_dash` unit | Its 120 s/2 start limit removed; flat restart |
| `scripts/capture_ambient_history.py` | Unaffected: it uses `scrub_body` only |

`rg raw_retention` across `~/projects` on 2026-10-20 finds no consumer outside enviroplus.

## C / H declaration

**Lifetime:** permanent runtime library code. k fires: a silent wrong result would be an unsourced derived row or a misread failure.

**Where failure surfaces:**
- `RetentionWriteError` reaches the consumer.
- The consumer process exits. systemd triggers `OnFailure` on every failed exit (systemd 257) and restarts it flat every 10 s (collectors) or 30 s (dashboard), with no stop limit (operator, 23:29).
- A double fault, where `ftruncate` also fails after a failed write, can still leave a torn tail. That would make `read_day` raise for the day, which surfaces at replay. This is residual.

**Revert:** the module now lives in enviroplus with its consumers (operator, 23:23), so a revert is one enviroplus revert followed by restarting the consumers. No `shared` change is involved.

**Irreversible effects:** none.

## Test power (AGENTS r)

The shared suite gives 141 passed. Each violation below was made in the real implementation and the suite was run:

| Violation | Result |
|---|---|
| Old log-only behaviour restored | 3 failed |
| No truncation of the partial line | 2 failed |
| Dedup advanced despite the failure | 2 failed |

The enviroplus suite, run against this branch (251 passed), observes:

| Violation | Result |
|---|---|
| Ambient swallows the failure at `retain()` | 1 failed |
| NWS swallows the failure at `retain()` | 1 failed |
| Provider loop swallows `RetentionWriteError` | 1 failed |
| Dashboard swallows its Tier 1 failure | 1 failed |

The ambient and NWS loop-level re-raises have no test. Their `run()` loops need a live environment. The `retain()`-level tests cover the path that matters, and the loop re-raise mirrors the tested provider loop.

## Review: 1cdf41b (architecture-reviewer, Anthropic), dispositions

| # | Finding | Disposition |
|---|---|---|
| S1 | Torn line survived a buffered failure | Closed: unbuffered write and `ftruncate` |
| S2 | Partial-line tests could not fail | Closed: short-write test |
| S3 | Dedup read raised a plain `OSError` | Closed: translated |
| E3 | Start limit stopped collection | Closed: no stop limit (backoff later dropped, operator 23:29) |
| E4 | 100 s derivation wrong | Closed: the limit is removed |
| E5 | Ambient/NWS loop re-raise untested | Disclosed; unchanged |

Power for the fixes, with the shared suite at 144 passed:

| Violation | Result |
|---|---|
| No `ftruncate` | 3 failed |
| Dedup read error untranslated | 1 failed |
| Short write not completed | 1 failed |

## Review

Reviewed in Anthropic rounds 4–6. See `docs/reviews/scd41-co2.md`, including its note on provider families (k).
