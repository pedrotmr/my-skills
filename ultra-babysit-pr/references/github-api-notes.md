# GitHub API Notes

The watcher uses `gh` and assumes the current user can read the repo, PR, checks, reviews, Actions runs, jobs, and logs.

## Watcher Commands

```bash
python3 scripts/ultra_pr_watch.py --pr auto --once
python3 scripts/ultra_pr_watch.py --pr auto --watch
python3 scripts/ultra_pr_watch.py --pr auto --retry-failed-now
python3 scripts/ultra_pr_watch.py --pr auto --mark-handled '<item-id>'
```

Use `--pr <number-or-url>` for an explicit target.

## Important Payload Fields

- `pending_review_items[].id`: stable watcher item id to pass to `--mark-handled`.
- `pending_review_items[].kind`: `issue_comment`, `review`, or `review_thread`.
- `pending_review_items[].thread_id`: GraphQL review thread id for resolving inline threads.
- `pending_review_items[].comment_id`: REST database id for replying to review comments when present.
- `failed_jobs[].logs_endpoint`: direct Actions job log endpoint.
- `actions`: `process_review_items`, `diagnose_ci_failure`, `retry_failed_checks`, `ready_to_merge`, `idle`, `stop_pr_closed`, or `stop_exhausted_retries`.

## Reply And Resolve

Reply to a review comment:

```bash
gh api repos/<owner>/<repo>/pulls/<pr>/comments/<comment-id>/replies -f body='<reply>'
```

Resolve a review thread:

```bash
gh api graphql -f query='mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{isResolved} } }' -f id='<thread-id>'
```

Rerun failed jobs for failed workflow runs:

```bash
gh run rerun <run-id> --failed
```

The watcher wraps reruns through `--retry-failed-now` so retry counts stay tied to the current head SHA.
