# CI Heuristics

Use logs, changed files, and the current head SHA to classify failures. Do not guess from check names alone.

## Branch-Caused

Treat as branch-caused when logs clearly point to the PR branch:

- Compile, typecheck, lint, format, or static analysis failures in touched files.
- Deterministic unit or integration test failures in touched modules.
- Snapshot diffs caused by UI/text changes in the branch.
- Build script, lockfile, package, schema, migration, or config changes from this PR causing deterministic failure.
- Missing generated artifacts or fixtures that the PR should have updated.

Action: fix locally, validate, commit, push, and resume watching.

## Likely Flaky Or Unrelated

Treat as flaky/unrelated when evidence points outside the branch:

- DNS, network, package registry, dependency download, or cache timeout.
- Runner image provisioning or GitHub Actions infrastructure failure.
- Cloud/API/service outage, rate limit, or transient auth provider failure.
- Non-deterministic failures in unrelated integration tests with known flaky patterns.
- Cancelled or stale jobs caused by superseded commits.

Action: do not edit code. If the watcher recommends `retry_failed_checks`, run `--retry-failed-now`. Otherwise wait or stop for user help.

## Ambiguous

When uncertain:

1. Fetch failed job logs once.
2. Compare failing paths/tests to the PR diff.
3. Prefer waiting or asking over patching unrelated tests or CI infrastructure.

Stop for user help when retries for the same SHA are exhausted, credentials/permissions fail, the branch cannot be pushed, or the failure needs product/team ownership.
