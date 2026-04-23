---
name: ultra-pr-shepherd
description: Drive a PR to merge-ready with aggressive parallel intelligence — classify and triage review comments (separating real signal from AI slop), auto-fix CI failures, resolve threads, and iterate until human-ready. Use when asked to "shepherd", "babysit", "watch", "monitor", or "see through" a PR, or when invoked as /ultra-pr-shepherd [pr-number]. Spawns parallel Explore agents to investigate comment clusters and CI failures concurrently. Handles comment triage (AI slop, false positives, trivial fixes, substantive fixes, design questions, out-of-scope), build/lint/type/test errors, and post-push iteration.
---

# Ultra PR Shepherd

Drive a PR to merge-ready state with aggressive parallelism. Classify every comment, discard AI slop, fix what's trivially fixable, escalate what isn't — and **never declare done without re-checking for new comments after every push**.

## Design principles

- **Parallel by default.** Fan out to Explore subagents in one message for independent investigations (one per comment cluster, one per CI failure category). The orchestrator stays clean; agents carry raw tool output.
- **AI slop gets its own bucket.** CodeRabbit / Cursor Bugbot / Copilot / Gemini / Claude-review comments often duplicate each other or flag non-issues. Classify aggressively; don't treat every bot comment as sacred, but never dismiss one that identifies a concrete bug.
- **Reply → push → resolve.** Never resolve without replying. Never push without local validation. Never declare DONE without re-checking after the last push.
- **Options, not questions.** When human input is needed, present 2–4 options with pros/cons and a recommendation. Never ask "what should I do?"

## Announce at start

"Starting Ultra PR Shepherd on PR #[N]. I'll classify comments in parallel, fix what I'm confident about, and flag the rest. Expect several fan-out rounds."

## Phase 1 — Initialize

```bash
PR_NUMBER=${1:-$(gh pr view --json number -q .number 2>/dev/null)}
OWNER=$(gh repo view --json owner -q .owner.login)
REPO=$(gh repo view --json name -q .name)
[ -z "$PR_NUMBER" ] && { echo "No PR found. Pass a PR number."; exit 1; }
```

Detect toolchain once (cache the answer):

- `package.json` `packageManager` field, else presence of `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` / `bun.lockb`
- Map install/lint/typecheck/test commands accordingly
- `.nvmrc` / `.tool-versions` → suggested runtime

## Phase 2 — Gather all signal in parallel

Single message, multiple Bash calls running in parallel:

1. `gh pr view $PR_NUMBER --json title,body,headRefName,baseRefName,mergeable,mergeStateStatus,isDraft`
2. `gh pr checks $PR_NUMBER --json name,status,conclusion,detailsUrl`
3. `gh pr diff $PR_NUMBER --name-only` (for scope)
4. GraphQL for review threads (appendix A)
5. `gh pr view $PR_NUMBER --json reviews --jq '.reviews[] | {author: .author.login, state, body}'`

Persist raw JSON into `/tmp/ups-$PR_NUMBER-*.json` so downstream agents can read it without re-fetching.

## Phase 3 — Classify comments (the core step)

For every unresolved thread, pick **one of six buckets**:

| Bucket                        | Meaning                                                                                             | Action                                                                                   |
| ----------------------------- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **A. AI slop**                | Bot comment: nitpicky, duplicative, pattern-matches a non-issue, or contradicts project conventions | Reply explaining why it doesn't apply → resolve                                          |
| **B. False positive**         | Issue doesn't exist in current code (fixed in later commit, reviewer misread)                       | Reply citing code/commit → resolve                                                       |
| **C. Trivial fix (≥80%)**     | Mechanical, uncontroversial: typo, null check, import, off-by-one, rename, dead code, lint-style    | Fix → push → reply → resolve                                                             |
| **D. Substantive fix (≥80%)** | Real behavior/logic/test change, but the correct move is clear and bounded                          | TDD fix → push → reply → resolve                                                         |
| **E. Design / <80%**          | Architecture, trade-off, opinion, broad refactor, ambiguous scope                                   | Do NOT resolve. Add to human-input summary                                               |
| **F. Out-of-scope**           | About code outside this PR's diff                                                                   | If <30 min & <3 files: treat as C/D. Else: open linked issue → reply with link → resolve |

### AI-slop heuristics

Mark as **A. AI slop** when author matches `coderabbitai|cursor|bugbot|copilot|gemini|claude(\[bot\])?|sonar|sweep-ai` **AND** any of:

- Flags a pattern the codebase uses everywhere
- Asks for a defensive check for a case that can't happen at this callsite
- Suggests a rename/docstring/TODO with no correctness impact
- Contradicts an established project convention visible in nearby files
- Duplicates an earlier human comment in the same thread
- Generic "LGTM, but consider..." with no concrete claim

When uncertain, **read the referenced code first**. Never dismiss a bot comment that identifies a concrete bug, security issue, or type/logic error — those are the whole point of having bots.

### Fan-out classification

If there are **>5 unresolved threads**, spawn one Explore agent per cluster of 3–5 related threads (group by file or feature). Each returns: `{thread_id, bucket, justification, proposed_diff?}`. You make the final call — agents advise, they don't decide.

## Phase 4 — State machine

```
MONITORING ─(CI fail)──→ FIXING ──────────→ MONITORING
           ─(comments)─→ HANDLING_REVIEWS ─→ MONITORING
           ─(ambig)────→ WAITING_FOR_USER ─→ FIXING
           ─(all clear)→ VERIFY ───────────→ DONE
```

Between states, poll `gh pr checks` + review threads every ~60s.

## Phase 5 — Fix CI failures in parallel

Group failures by category. Spawn one Explore agent per category to gather evidence (failing logs, relevant file snapshots) before you touch code:

- **Lint / format** — autofix with project linter; revert unrelated noise
- **Type errors** — fix locally, re-run typecheck
- **Unit tests** — only update expectations if the change is clearly intentional; otherwise fix the code
- **E2E / snapshot** — if UI changes in this PR justify it, regenerate or apply the project's snapshot-update label; else flag as regression
- **Flaky / infra** — never "fix" by retrying; flag to human

Rules:

- Kill stale watchers before testing: `pkill -f 'vitest|jest' 2>/dev/null || true`
- Validate locally before every push: `<prettier> && <typecheck> && <test>`
- Stage specific files — never `git add -A`
- Never force-push or `--no-verify` without explicit user approval

## Phase 6 — Reply → push → resolve

Order matters:

1. **Push fixes first** — reply can cite a commit SHA
2. **Reply to the thread** — reference the commit and what changed
3. **Resolve the thread** (appendix A)

Never resolve without replying. Never resolve E (design) threads.

## Phase 7 — Iteration (the #1 failure mode)

After every push that addresses reviews:

1. Wait ~60s for bots to re-scan
2. Re-fetch review threads + checks
3. If any new unresolved threads or failing checks → back to Phase 3
4. Only exit to DONE when a full poll shows: all checks green, zero unresolved threads, no new comments since the last push

**Do not shortcut this.** Automated reviewers often post within 1–2 minutes of a push; skipping this step is how shepherds declare victory prematurely.

## Phase 8 — Human input (when needed)

```
[One-line situation]

Options:
1. [Name] (Recommended)
   - What: …
   - Pros: …
   - Cons: …
2. [Name]
   - …
3. [Name]
   - …

Which would you like? (Or propose your own.)
```

## Phase 9 — Exit

### DONE checklist

- [ ] All CI checks green
- [ ] Zero unresolved threads
- [ ] Every top-level comment has a reply
- [ ] Post-push iteration ran clean (no new comments since last push)
- [ ] Summary posted

### Summary format

```
## PR #<N> — Ready for human merge

### Fixed by shepherd
- <sha>: <one-liner>

### Resolved with explanation
- thread <id>: <bucket> — <why>

### Dismissed as AI slop
- thread <id> (<bot>): <why it doesn't apply>

### Needs your input
- thread <id>: <why judgment required>

### CI
- <check>: <status>
```

Omit empty sections.

## Soft timeout — 4 hours

Checkpoint with the user using the Phase 8 template. Offer: keep monitoring / exit with handoff / shorten cadence.

## Appendix A — GraphQL snippets

**Fetch unresolved threads with metadata:**

```bash
gh api graphql -f query='
  query($owner:String!,$repo:String!,$number:Int!){
    repository(owner:$owner,name:$repo){
      pullRequest(number:$number){
        reviewThreads(first:100){
          nodes{
            id isResolved isOutdated
            comments(first:50){
              nodes{ databaseId body path line author{login} createdAt }
            }
          }
        }
      }
    }
  }' -f owner=$OWNER -f repo=$REPO -F number=$PR_NUMBER
```

**Resolve a thread:**

```bash
gh api graphql -f query='
  mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{isResolved} } }
' -f id="$THREAD_ID"
```

**Reply to a review comment:**

```bash
gh api repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments/$COMMENT_ID/replies -f body="$REPLY"
```

## Non-negotiable rules

1. Read actual code before classifying a comment as false positive or slop
2. Validate locally before every push
3. Never resolve without replying
4. After every push, re-check for new comments before declaring DONE
5. Present options, not open questions, when blocked
6. Stage specific files; never `git add -A`
7. Never force-push or bypass hooks without explicit user approval
