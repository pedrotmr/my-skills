---
name: address-pr-comments
description: Helps address review and issue comments on the open GitHub PR for the current branch using gh CLI. Use when the user asks to triage PR comments, organize unresolved feedback, group related review threads, validate whether comments are actionable, and apply fixes with commit/thread follow-up.
---

# GitHub PR Comment Handler

Find the open PR for the current branch, triage all comment threads, and help the user resolve only what needs action.

Run all `gh` commands with elevated network permissions.

## Workflow

### 1) Authentication gate

- Run `gh auth status` first.
- If not authenticated (or missing scopes), ask user to run `gh auth login`.
- If sandbox/network blocks auth checks, rerun with elevated permissions.
- Do not proceed until auth is healthy.

### 2) Identify the current PR and fetch all feedback

- Determine PR tied to current branch:
  - `gh pr view --json number,url,headRefName,baseRefName`
- Collect flat PR review comments:
  - `gh api repos/{owner}/{repo}/pulls/{pr_number}/comments`
- Collect thread metadata (resolved/outdated state plus comments):
  - `gh api graphql -f query='query($owner:String!,$repo:String!,$number:Int!){ repository(owner:$owner,name:$repo){ pullRequest(number:$number){ reviewThreads(first:100){ nodes{ id isResolved isOutdated comments(first:20){ nodes{ id author{ login } body path url createdAt } } } } } } }' -F owner={owner} -F repo={repo} -F number={pr_number}`

If API calls fail due to auth/rate limits, pause and ask user to re-authenticate, then retry.

### 3) Analyze and group comments

Build grouped issue buckets by shared root concern (same defect/request), even when spread across multiple comments/threads.

For each group include:

- Group number
- Issue title (short)
- Why comments belong together
- Affected files/paths
- Linked thread/comment refs
- Status rollup (`unresolved`, `resolved`, `outdated`, `mixed`)
- Actionability verdict (`needs action` / `no action needed`)
- Assistant take (agree/challenge with reason)
- Proposed fix outline (if actionable)
- Severity rating (`Blocker`, `High`, `Medium`, `Low`):
  - `Blocker` blocker: correctness/security/data loss; fix first
  - `High` high: likely regression/maintainability risk; fix early
  - `Medium` medium: improvement requested; fix when capacity allows
  - `Low` low: polish/nit; batch last or leave with rationale

### 4) Present results in required order

Use this response structure:

1. **Actionable unresolved groups (first, highlighted)**
   - Only groups that still need work.
   - Number them for selection.

2. **All thread/comment groups (complete inventory)**
   - Include unresolved, resolved, outdated, and mixed groups.
   - Mark clearly:
     - `outdated - no action needed`
     - `resolved - no action needed`
   - If unresolved but non-actionable, explain why.

3. **Decision prompt**
   - Ask user exactly which group numbers to address.
   - If user says "fix all issues", skip selection and enter automation loop.

### 5) Implement selected groups only

When user selects groups:

- Apply fixes for selected groups.
- Stop and ask user to run/confirm local tests.
- Do not commit until user approves.

### 5b) Automation loop for large PRs ("fix all issues")

When user requests to fix everything, run this loop automatically:

1. Build execution queue: actionable unresolved groups sorted by severity (`Blocker` -> `Low`) and dependency.
2. Process in batches:
   - Default batch size: 2 groups
   - Use size 1 for risky/cross-cutting groups (`Blocker/High` touching shared files)
   - Allow size 3 only for clearly isolated `Medium/Low` groups
3. For each batch: implement -> run tests -> commit per group -> push -> update/resolve threads.
4. Continue until queue is empty, then publish final status (addressed, skipped-with-rationale, still-blocked).

### 5c) Optional manager/worker sub-agent mode

Use only when issue count is high (for example 8+ actionable groups) and groups are mostly independent.

- Manager agent responsibilities:
  - No code changes
  - Own queue/status board and batch assignment
  - Enforce ordering/dependency and prevent overlap
- Worker agent responsibilities:
  - Implement assigned group(s), test, and report status
- Guardrails:
  - Never run workers in parallel on overlapping files
  - Keep one commit per issue group
  - Manager verifies clean merge and CI before final thread resolution

### 6) Commit and PR thread updates (after approval)

For each addressed group:

1. Create one commit per group with focused message.
2. Push branch.
3. Post thread update:
   - `Addressed: <commit message> (<commit link>)`
4. Resolve corresponding thread(s) when appropriate.

If force-push happens later, refresh any commit links shared in thread replies.

## Boundaries

- Do not silently dismiss unresolved feedback; justify every non-action decision.
- Do not batch unrelated issues into one group just because they touch same file.
- Do not create commits before user confirmation.
