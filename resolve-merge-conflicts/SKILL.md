---
name: resolve-merge-conflicts
description: >
  Resolves PR merge conflicts via rebase. Use when a PR has conflicts or the user
  says "fix merge conflicts", "my PR has conflicts", or "help me rebase". Fetches
  origin, rebases onto target branch (default: main), resolves all conflicts, and
  force-pushes with a safety-first conflict strategy that asks the user when
  intent is ambiguous.
---

# Merge Conflict Resolution Guide

**When to run:**
Use when a PR has merge conflicts or the user requests help with rebase/conflict resolution.

---

## Workflow

**1. Check in-progress operations**

- Run `git status`.
- Detect if a rebase, merge, or cherry-pick is already happening.

**2. Handle unrelated local changes**

- If unrelated local modifications are present:
  - Pause and ask the user: "Do you want to (a) stash, (b) commit, or (c) abort?"

**3. Sync remote changes**

- Run `git fetch origin`.

**4. Determine rebase base and start rebase**

- If `TARGET_BRANCH` is set:
  - Run `git rebase origin/${TARGET_BRANCH}`
- Otherwise:
  - Run `git rebase origin/main`
- If a rebase is already in progress, **continue** the existing one (don’t restart).

**5. Resolve each conflicted file (deliberate, file-by-file):**

- **Keep "ours"** (current branch) if conflict is from new feature logic in the branch.
- **Keep "theirs"** (target branch) for upstream refactors, renames, or formatting-only changes.
- **Combine both** sides if changes are non-overlapping and should coexist.
- **Never** apply blanket `--ours`/`--theirs` for all files.
- If unsure, **pause and ask the user for guidance**.

**6. Handling ambiguity**

- If the correct action for a file is **unclear after two attempts**, stop and ask the user rather than guess.

**7. Stage and verify after each file**

- After resolving a conflict, run:
  - `git add <file>`
  - `git status` (verify the number of unresolved conflicts is decreasing).

**8. Continue the rebase process**

- Run `git rebase --continue` (or the equivalent command for the current operation).
- If prompted with an editor, suppress with `GIT_EDITOR=true`.

**9. Repeat steps 5–8** until:

- No conflict markers remain:
  - Confirm: `rg '^(<<<<<<<|=======|>>>>>>>)'` returns **no matches**.
  - `git status` shows no active rebase/merge/cherry-pick.

**10. Validate the resolved branch**

- Run tests, lints, or builds as appropriate for modified code.

**11. Prepare for push**

- **Ensure** you’re _not_ on `main` or `master` unless the user explicitly asks for it.

**12. Push changes**

- Run `git push --force-with-lease`.

**13. Handle rebase failures**

- If the rebase cannot be completed safely, pause and ask whether to run `git rebase --abort`.

**14. Report summary**

- Clearly inform the user:
  - Which files had conflicts.
  - The resolution path chosen for each file (ours/theirs/combined and _why_).
  - Tests/validation performed.
  - Uncertainties or points requiring user input.

---
