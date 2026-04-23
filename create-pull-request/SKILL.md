---
name: create-pull-request
description: Commit, push, and open a PR—all in one flow with a clear, quick PR summary.
---

# Concise PR Flow

1. **Check prerequisites:**
   - `gh --version` and `gh auth status` (stop if missing or unauthenticated)

2. **Scan current state:**
   - Get changes: `git status --porcelain`, `git diff`, current branch, recent commits

3. **Stage changes:**
   - `git add -A`
   - _Never add secrets (.env, credentials, etc.)—warn & skip if found_

4. **Craft commit message:**
   - Types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`
   - No trailing period
   - Scope: _(optional)_
   - Description: clear, imperative and present tense, ≤50 chars
   - Format: `<type>[scope]: <description>`
   - Body (only if needed): Skip entirely when subject is self-explanatory

   #### Examples

   **Diff:** Add new endpoint for user profile (with explanation)
   - ❌ Incorrect:
     ```
     feat: add a new endpoint to get user profile information from the database
     ```
   - ✅ Correct:

     ```
     feat(api): add GET /users/:id/profile

     Mobile client needs profile data without the full user payload
     to reduce LTE bandwidth on cold-launch screens.

     Closes #128
     ```

   **Diff:** Breaking API change
   - ✅ Correct:

     ```
     feat(api)!: rename /v1/orders to /v1/checkout

     BREAKING CHANGE: clients on /v1/orders must migrate to /v1/checkout
     before 2026-06-01. Old route returns 410 after that date.
     ```

5. **Commit (run pre-commit hooks):**
   - `git commit -m "<type>[scope]: <description>"`
   - If hooks fail: read error, fix, restage, re-commit. If still fails, stop and report.

6. **Push to remote:**
   - `git push -u origin $(git branch --show-current)`
   - If rejected, `git pull --rebase ...` and retry once.

7. **Open PR:**
   - Get diffs: `git diff main...HEAD`, commit summaries
   - Generate a clear, scan-friendly PR:

```bash
gh pr create --title "<type>[scope]: <short summary>" --body "$(cat <<'EOF'

## What Changed
<!-- Describe the change clearly and keep scope tight. -->

## Why
<!-- Explain the problem being solved and why this approach is the right one. -->

EOF
)"
```

**Write the PR summary to be brief, clear, and immediately understandable. Anyone should grasp what changed and why, in under 2 minutes. Focus on context, impact, and intent, not process or implementation details. Avoid jargon, unnecessary detail, or filler—use plain language that's easy for any teammate to read. Prioritize clarity and relevance over technical precision.**

8. **Report results:**
   - Print successful PR URL, branch, and commit summary.

Example result:

```
✅ PR created!
   Branch: <branch>
   PR: <url>
   Commit: <type>[scope]: <description>
```
