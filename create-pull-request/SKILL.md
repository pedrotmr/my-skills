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
   - Type: `feat`, `fix`, `refactor`, etc.
   - Scope: _(optional)_
   - Description: clear, present tense, ≤72 chars
   - Format: `<type>[scope]: <description>`

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

**PR summary must be concise but also super easy to read and understand the context in one go - should take less than 2 minutes to read. Avoid fluff.**

8. **Report results:**
   - Print successful PR URL, branch, and commit summary.

Example result:

```
✅ PR created!
   Branch: <branch>
   PR: <url>
   Commit: <type>[scope]: <description>
```
