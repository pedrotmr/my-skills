---
name: ultra-babysit-pr
description: Reliably shepherd GitHub pull requests until merged, closed, or genuinely blocked. Use when Codex is asked to babysit, shepherd, monitor, watch, see through, or handle a PR after creation; triage review comments and bot feedback; diagnose CI failures; retry likely flaky failures with a budget; fix branch-caused failures; resolve review threads; or keep polling after pushes so late comments and checks are not missed.
---

# Ultra Babysit PR

Babysit a GitHub PR with a deterministic watcher plus disciplined agent judgment. Use the watcher for state, persistence, retry accounting, unresolved thread detection, and polling; use Codex for code reading, triage, fixes, replies, validation, commits, pushes, and final judgment.

## Start

Prefer continuous monitoring unless the user explicitly asks for a one-shot check:

```bash
python3 scripts/ultra_pr_watch.py --pr auto --watch
```

For diagnostics or after returning from a fix:

```bash
python3 scripts/ultra_pr_watch.py --pr auto --once
```

Accept explicit PR numbers or URLs with `--pr <number-or-url>`. The watcher emits JSON with:

- `actions`: next recommended actions.
- `pending_review_items`: persisted review items that need a decision.
- `failed_jobs`: failed jobs with direct `logs_endpoint` when available.
- `retry_state`: retry count for the current head SHA.
- `state_file`: watcher state file in `/tmp`.

## Operating Loop

1. Start `--watch` or run `--once`.
2. Process `pending_review_items` before CI reruns. A review fix commit will retrigger CI, so do not rerun old failed jobs first.
3. For each review item, read the referenced code before classifying it. Use `references/review-triage.md`.
4. If the item is actionable and safe, patch locally, validate, commit, push, reply if appropriate, resolve the thread if it is a review thread, then mark it handled.
5. If CI fails, inspect failed job logs before deciding whether it is branch-caused or flaky/unrelated. Use `references/ci-heuristics.md`.
6. If CI is likely flaky/unrelated and the watcher recommends `retry_failed_checks`, run `--retry-failed-now`.
7. After every push or retry, immediately resume polling. A push is progress, not completion.
8. Stop only when the PR is merged/closed or user input is required. A green, mergeable, review-clean PR is a milestone; keep watching while it remains open unless the user tells you to stop.

## Review Handling

Use the A-F triage buckets from `references/review-triage.md`:

- A: bot noise or AI slop
- B: false positive
- C: trivial fix
- D: substantive bounded fix
- E: design or under-80-percent confidence
- F: out of scope

Rules:

- Never dismiss a bot comment without reading the relevant code.
- Never resolve a human-authored review thread without either fixing it or getting user approval for the exact response.
- Do not post replies to human-authored GitHub comments automatically. Present the suggested reply to the user first; if approved, prefix it with `[codex]`.
- Bot comments may be answered and resolved when the reason is concrete and code-backed.
- Design or ambiguous items stay unresolved and are surfaced to the user with 2-4 options and a recommendation.

After handling an item, remove it from the pending queue:

```bash
python3 scripts/ultra_pr_watch.py --pr auto --mark-handled '<item-id>'
```

For multiple handled items:

```bash
python3 scripts/ultra_pr_watch.py --pr auto --mark-handled '<item-id-1>' '<item-id-2>'
```

## CI Handling

When `diagnose_ci_failure` appears:

1. Inspect failed jobs from the watcher payload.
2. Fetch direct job logs if `logs_endpoint` is present:

```bash
gh api '<logs_endpoint>' > /tmp/codex-gh-job-logs.zip
```

3. Classify using `references/ci-heuristics.md`.
4. Fix only branch-caused failures. Do not patch unrelated flaky tests, infrastructure, dependency outages, runner issues, or CI config unless logs clearly connect them to this branch.
5. Retry likely flakes only when `retry_failed_checks` appears:

```bash
python3 scripts/ultra_pr_watch.py --pr auto --retry-failed-now
```

## Git Safety

- Work only on the PR head branch.
- Check for unrelated uncommitted changes before editing.
- Stage specific files; do not use `git add -A`.
- Validate locally before every push with the repo's relevant format, lint, typecheck, and test commands.
- Do not force-push, bypass hooks, switch branches, or run destructive git commands unless the user explicitly approves.
- If the local worktree is dirty with unrelated changes, stop and ask.

## Resolving Threads

For review threads, the watcher includes `thread_id` and `comment_id` when GitHub exposes them.

Reply to an inline review comment:

```bash
gh api repos/<owner>/<repo>/pulls/<pr>/comments/<comment-id>/replies -f body='<reply>'
```

Resolve a thread:

```bash
gh api graphql -f query='mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{isResolved} } }' -f id='<thread-id>'
```

Only resolve after the fix or explanation is on GitHub. Never resolve an unresolved human design question.

## Human Input

When blocked, present options instead of a vague question:

```text
<one-line situation>

Options:
1. <recommended option> (Recommended)
   - What: ...
   - Pros: ...
   - Cons: ...
2. <alternative>
   - What: ...
   - Pros: ...
   - Cons: ...

Which would you like? (Or propose your own.)
```

## Done Criteria

Only call the task done when all are true:

- PR is merged/closed, or the user asked you to stop.
- No watcher process is still running.
- Latest snapshot has been inspected after the last push or retry.
- Remaining blockers, if any, are explicitly named.

If reporting a ready milestone, include final SHA, CI summary, mergeability, review state, fixes pushed, retries used, and any unresolved items.
