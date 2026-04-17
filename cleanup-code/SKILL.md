---
name: cleanup-code
description: Use when cleaning up bloated, AI-generated, or recently modified code that works but has duplication, dead code, needless abstraction, boundary leaks, or weak tests. Preserves behavior via regression-tests-first, one-smell-at-a-time passes. Not for architectural rewrites, behavior changes, or broad refactors.
---

# Simplify

## Mission

Reduce noise and complexity while preserving exact behavior. Raise signal per line without introducing new abstractions.

The goal is not fewer lines — it's code that is easier to read, understand, modify, and debug. Every simplification must pass a simple test: "Would a new team member understand this faster than the original?"

Required outcomes:

- Behavior is identical before and after.
- Every removal is evidence-backed, not speculative.
- Diff is minimal, bounded to the resolved scope.
- No new abstractions, helpers, or dependencies unless explicitly requested.
- Refactor commits stay separate from feature and bugfix commits.

## When to Use

- Code path works but feels bloated, noisy, or over-abstracted.
- Cleaning up AI-generated output (duplicated branches, wrapper layers, debug leftovers, stale flags).
- Recently modified code needs a clarity and consistency polish.
- Review flagged readability, nesting, naming, or duplication issues.
- User says: "simplify", "cleanup", "deslop", "refactor this", "tighten this up".

## When NOT to Use

- Behavior is broken — fix correctness first.
- Behavior intentionally needs to change — that is a feature or refactor task, not simplify.
- Code is already clean — do not simplify for its own sake.
- You do not yet understand what the code does — comprehend first, simplify after.
- Broad architectural rework, module redesign, or public API rename — out of scope.
- Pure style/formatting concerns — use the linter.

## Core Principles

1. **Preserve behavior.** Lock it with regression tests before editing.
2. **Follow project conventions.** Simplification means consistency with the codebase, not imposing external taste.
3. **Clarity over brevity.** Explicit beats clever. Fewer lines is not the goal — easier comprehension is.
4. **One smell per pass.** Bundled refactors hide failure modes and block bisection.
5. **Evidence over speculation.** Remove only what is provably unused, duplicated, or indirect.
6. **Stay in scope.** Do not expand cleanup beyond the resolved files without explicit approval.
7. **Split from feature work.** A commit that refactors and adds a feature is two commits — split them.

## Understand Before Touching (Chesterton's Fence)

If you cannot explain why a piece of code exists, you are not ready to remove or restructure it. Before every non-trivial change, answer:

- What is this code's responsibility?
- What calls it? What does it call?
- What are the edge cases and error paths?
- Which tests (if any) define its expected behavior?
- Why might it have been written this way — performance, platform constraint, historical reason?
- Check `git blame` and the originating commit/PR for context.

If you cannot answer these, read more context first. Do not guess.

## Scope Resolution

Resolve the target in this fixed order:

1. User-provided file list, path, or range.
2. Recently modified code in the current session.
3. Staged changes.
4. Working tree changes.

If no reviewable changes are found, stop and report:
`No simplify target found (no diff in selected scope).`

## Smell Taxonomy

Classify every candidate change into exactly one category:

1. **Dead code** — unused imports/exports, unreachable branches, stale feature flags, debug leftovers, commented-out code.
2. **Duplication** — repeated logic, copy-paste branches, parallel helpers doing the same thing.
3. **Needless abstraction** — pass-through wrappers, single-use helpers, speculative indirection, premature generalization.
4. **Boundary leaks** — wrong-layer imports, hidden coupling, side effects in pure modules, leaky responsibilities.
5. **Weak tests** — behavior not locked, thin coverage around the edited paths, assertions on implementation details instead of behavior.

## Pattern Reference

Concrete signals mapped to concrete fixes. Use these to classify and resolve candidates, not as a license to churn.

### Structural complexity

| Pattern                    | Signal                         | Simplification                                |
| -------------------------- | ------------------------------ | --------------------------------------------- |
| Deep nesting (3+ levels)   | Hard to follow control flow    | Guard clauses, early returns, extract helpers |
| Long functions (50+ lines) | Multiple responsibilities      | Split into focused, well-named functions      |
| Nested ternaries           | Requires mental stack to parse | `if/else` chain, `switch`, or lookup map      |
| Boolean parameter flags    | `doThing(true, false, true)`   | Options object or separate functions          |
| Repeated conditionals      | Same check in multiple places  | Extract a named predicate                     |

### Naming and readability

| Pattern                 | Signal                                         | Simplification                                       |
| ----------------------- | ---------------------------------------------- | ---------------------------------------------------- |
| Generic names           | `data`, `result`, `temp`, `val`                | Rename to describe the content                       |
| Unhelpful abbreviations | `usr`, `cfg`, `btn`, `evt`                     | Full words (keep universal ones: `id`, `url`, `api`) |
| Misleading names        | `get*` that also mutates                       | Rename to reflect real behavior                      |
| "What" comments         | `// increment counter` above `count++`         | Delete — code is self-evident                        |
| "Why" comments          | `// Retry because the API is flaky under load` | Keep — intent the code cannot express                |

### Redundancy and abstraction

| Pattern                  | Signal                                 | Simplification                     |
| ------------------------ | -------------------------------------- | ---------------------------------- |
| Duplicated logic         | Same 5+ lines in multiple places       | Extract a shared function          |
| Dead code                | Unreachable, unused, commented-out     | Remove after confirming truly dead |
| Pass-through wrapper     | Adds no value over underlying call     | Inline and call directly           |
| Over-engineered pattern  | Factory-for-a-factory, strategy-of-one | Replace with the direct approach   |
| Redundant type assertion | Cast to a type already inferred        | Remove the cast                    |

### Canonical example: nested ternary → readable branches

```typescript
// Before — dense, requires mental stack
const label = isNew
  ? "New"
  : isUpdated
    ? "Updated"
    : isArchived
      ? "Archived"
      : "Active";

// After — scannable, each branch independent
function getStatusLabel(item: Item): string {
  if (item.isNew) return "New";
  if (item.isUpdated) return "Updated";
  if (item.isArchived) return "Archived";
  return "Active";
}
```

## Procedure (Always This Order)

1. **Lock behavior with regression tests**
   - Identify the observable behavior that must survive the cleanup.
   - If not currently tested, add the narrowest tests needed to lock it.
   - Run the tests. They must pass before any simplification edit.

2. **Plan before editing**
   - List the specific smells to remove, bounded to the resolved scope.
   - Order from safest to riskiest: dead code → duplication → needless abstraction → boundary fixes → clarity → test reinforcement.
   - No code changes until the plan is explicit.

3. **Execute one smell per pass**
   - Pass 1: Dead code deletion.
   - Pass 2: Duplicate removal.
   - Pass 3: Needless-abstraction removal.
   - Pass 4: Boundary fixes (only when regression tests fully cover affected paths).
   - Pass 5: Naming and error-handling clarity.
   - Pass 6: Test reinforcement.
   - Re-run regression tests after every pass. Revert on red before continuing.

4. **Run quality gates after each pass**
   - Regression tests pass.
   - Lint passes.
   - Typecheck passes.
   - Relevant unit/integration tests pass.
   - Static/security scan passes when available.
   - Diff stays minimal and bounded to the resolved files.
   - No new abstractions or dependencies introduced.

5. **Deliver the simplify report** — see Output Contract.

## Rule of 500

If a simplification would touch more than ~500 lines, stop and automate: codemods, `jscodeshift`/AST transforms, `sed` scripts, or similar. Manual edits at that scale are error-prone and hostile to review. When in doubt, propose the automation before running it.

## Clarity Rules (Pass 5)

- Prefer `function` declarations over arrow functions for top-level functions.
- Prefer explicit `if`/`else` or `switch` chains over nested ternaries.
- Prefer early returns over deep nesting.
- Prefer named constants over repeated magic values.
- Prefer descriptive names; rename only when the current name is misleading or ambiguous.
- Delete "what" comments; keep "why" comments.
- Do not rewrite working code purely to match personal taste.

## Anti-Patterns

Do not:

- Collapse multiple smells into one commit.
- Mix refactor with feature or bugfix work in the same commit.
- Introduce nested ternaries, dense one-liners, or point-free tricks in the name of brevity.
- Add new abstractions, helper layers, or dependencies.
- Rewrite architecture, move modules, or rename public APIs.
- Delete tests to "reduce noise" — weak tests get reinforced, not removed.
- Remove error handling because it "looks cleaner".
- Bundle formatter or style-only churn with behavior-sensitive edits.
- Expand scope beyond resolved files without explicit user approval.
- Proceed to the next pass while regression tests are red.
- Remove code you suspect is unused without proving it.

## Common Rationalizations

| Rationalization                                      | Reality                                                                                                 |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| "It's working — no need to touch it"                 | Working code that is hard to read is hard to fix when it breaks. Simplify now, save later.              |
| "Fewer lines is always simpler"                      | A one-line nested ternary is not simpler than a five-line `if/else`. Comprehension speed is the metric. |
| "I'll just quickly simplify this unrelated code too" | Unscoped churn creates noisy diffs and risks regressions outside the intended change. Stay bounded.     |
| "The types make it self-documenting"                 | Types document structure, not intent. Names carry the _why_.                                            |
| "This abstraction might be useful later"             | Speculative abstraction is complexity without value. Remove it; re-add when a real caller appears.      |
| "The original author must have had a reason"         | Maybe — check `git blame`. Often it is just residue of iteration under pressure, not design.            |
| "I'll refactor while adding this feature"            | Mixed commits are harder to review, revert, and understand in history. Split them.                      |
| "Tests are noisy — let me trim them"                 | Weak tests get reinforced, not removed. Trimming tests during simplify hides behavior changes.          |

## Red Flags — Stop and Reconsider

- Simplification requires modifying existing tests to pass (you likely changed behavior).
- "Simplified" code is longer or harder to follow than the original.
- You are renaming to match your preferences, not project conventions.
- You are removing error handling to "clean up".
- You are editing code you do not fully understand.
- You are batching many simplifications into one large commit.
- You are touching files outside the requested scope.

All of these mean: pause, revert the current edit, and return to the plan.

## Output Contract (Stable Format)

Use this exact section order:

```markdown
Simplify Report
Scope: [files or range]
Behavior Lock: [regression tests added / pre-existing]

Passes Completed

1. Dead code — [concise change or N/A]
2. Duplication — [concise change or N/A]
3. Needless abstraction — [concise change or N/A]
4. Boundary fixes — [concise change or N/A]
5. Clarity — [concise change or N/A]
6. Test reinforcement — [concise change or N/A]

Quality Gates

- Regression tests: PASS | FAIL
- Lint: PASS | FAIL | N/A
- Typecheck: PASS | FAIL | N/A
- Tests: PASS | FAIL | N/A
- Static/security scan: PASS | FAIL | N/A

Changed Files

- [path:line] — [simplification]

Remaining Risks

- [none | specific deferred item with reason]
```

When a pass makes no changes, mark it `N/A` — do not omit the row.

## Verification Checklist

Before reporting complete:

- [ ] All pre-existing tests pass without modification.
- [ ] New regression tests (if added) lock observable behavior, not implementation.
- [ ] Lint and typecheck pass with no new warnings.
- [ ] Each pass is a reviewable, incremental change.
- [ ] Diff is clean — no unrelated files, no formatter churn, no scope creep.
- [ ] Simplified code matches project conventions (CLAUDE.md or neighboring patterns).
- [ ] No error handling removed or weakened.
- [ ] No dead code left behind (unused imports, unreachable branches).
- [ ] Refactor commits are separate from any feature/bugfix work.

## Reliability Hardening

- Use the same pass order every time.
- Do not proceed to Pass N+1 while Pass N leaves any gate red.
- Prefer deleting code over moving it.
- If you cannot prove code is dead, leave it and note it in Remaining Risks.
- If a boundary change is ambiguous, stop and ask one concise clarifying question before editing.
- Never invent new requirements, constraints, or abstractions.
- Prefer omission over weak or uncertain changes.
