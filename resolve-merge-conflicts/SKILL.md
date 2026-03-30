---
name: resolve-merge-conflicts
description: >
  Resolves PR merge conflicts via rebase. Use when a PR has conflicts or the user
  says "fix merge conflicts", "my PR has conflicts", or "help me rebase". Fetches
  origin, rebases onto target branch (default: main), resolves all conflicts, and
  force-pushes — no user intervention needed mid-rebase.
---

# Resolve Merge Conflicts

1. Run `git status`; detect any active conflict operation (rebase/merge/cherry-pick).
2. If unrelated local changes exist, stop and ask the user to stash or commit them first.
3. Run `git fetch origin`.
4. If no conflict op is active, run `git rebase ${TARGET_BRANCH:-origin/main}`.
5. Resolve each conflicted file by combining both sides when possible; avoid blind ours/theirs.
6. Stage each resolved file immediately with `git add <file>`.
7. Continue the operation: `git rebase --continue` / `git cherry-pick --continue` / merge commit. If an editor blocks, use `GIT_EDITOR=true`.
8. Repeat until complete, then verify: `rg '^(<<<<<<<|=======|>>>>>>>)'` has no matches and `git status` shows no in-progress op.
9. Run targeted validation for the touched area (relevant build/test/lint).
10. Push with `git push --force-with-lease`, then report what caused each conflict, how it was resolved, and the validation result.
