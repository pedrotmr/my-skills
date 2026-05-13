# Scoring Rubric and Filters

This document defines the confidence rubric each Phase 3 scorer uses and the filter policy the orchestrator applies before producing the final report.

## The 0–100 Scale

| Score | Meaning |
|------:|---------|
| **0** | False positive. Does not survive light scrutiny, or it is a pre-existing issue outside the diff. |
| **25** | Somewhat confident. Might be real but cannot be verified from the evidence. Stylistic issues not explicitly called out in a convention file live here. |
| **50** | Moderately confident. Verified as real, but a nitpick or rare in practice, and unimportant relative to the rest of the change. |
| **75** | Highly confident. Double-checked, very likely to hit in practice, the existing approach is insufficient, or it is a rule directly named in a convention file. |
| **100** | Certain. Directly confirmed by the evidence, will happen frequently in practice. |

Scorers may return any integer 0–100, not just the anchor values. Anchors are reference points, not buckets.

## Orchestrator Filter Policy

Applied after every candidate has been scored. Order matters.

### 1. False-positive hard filters

Drop these regardless of score:

- Issue is on a line **not present in the diff** (pre-existing code outside the change)
- Issue would be caught by a linter, typechecker, compiler, or formatter — imports, types, syntax, formatting, trailing whitespace, unused variables a tool already flags
- General quality complaint (test coverage, documentation, style) that is **not required** by a convention file
- Change in functionality that looks intentional and matches the PR description or commit messages
- Rule the code **explicitly opts out of** with a waiver comment (`// eslint-disable-next-line`, `# noqa`, `// intentional:`, etc.)
- "Nice to have" without a concrete failure or cost

### 2. Cross-lane confirmation boost

Before threshold filtering:

1. Cluster findings by location (same `path`, line numbers within ±3) with overlapping `claim`.
2. If a cluster contains findings from **two or more distinct lanes**, add `+10` to each member's final score (cap at 100).
3. If a cluster contains findings from **three or more distinct lanes**, add `+15` instead of +10.

Independent agreement across lenses is strong evidence a finding is real.

### 3. Threshold

Drop every finding whose **final** score (after the boost) is `< 80`.

### 4. Cluster collapse

For each remaining cluster, keep the single highest-scored finding. Record which other lanes flagged it as `also-flagged-by: [lens, lens, ...]`. Do not list the same issue twice.

### 5. Severity normalization

Within a cluster, the kept finding's severity is the **maximum** severity across the cluster. If one lane called it `Important` and another called it `Critical`, it is `Critical`.

### 6. Suggestion cap

After sorting, keep at most **3** Suggestions in the final report. Drop the rest; do not promote them to Important.

## What the Scorer Must Verify

Every scoring call must apply all of these checks before assigning a score:

- [ ] The `location` is inside the diff, not outside it.
- [ ] The `evidence` quote actually supports the `claim`.
- [ ] The `fix` is concrete enough to act on. If it is vague, the score is capped at 50.
- [ ] For convention findings: the cited file exists, the rule exists in that file, and the rule is phrased as a requirement (not a preference).
- [ ] For spec findings: the cited spec source exists or is included in the review context, the quoted requirement exists, and the requirement applies to this diff.
- [ ] The finding is not something a linter or typechecker would catch. If it is, the score is 0.
- [ ] The finding describes a concrete failure mode, not a hypothetical "could be better."

## Example Scores

| Finding | Score | Why |
|---|---:|---|
| SQL string built via `+` with unsanitized user input, call path confirmed reachable | 100 | Injection, directly evidenced, exploit path clear. |
| Function name is `doStuff`, no convention rule against it | 25 | Stylistic, no rule cited. |
| Potential race between `read` and `write` with no evidence either is concurrent | 50 | Plausible but unverified concurrency. |
| New `O(N²)` loop over request body with N user-controlled up to 10k | 90 | Concrete workload, DOS risk. |
| Import ordering differs from the rest of the file | 0 | Formatter's job. |
| CLAUDE.md says "never import from `internal/` outside the owner package" and the diff does | 90 | Rule exists, phrased as a requirement, diff violates it. |
| Spec says "export must include archived projects" and the diff only queries active projects | 90 | Requirement exists, diff implements a narrower behavior. |
| `// TODO: handle errors` left in a function that already returns `Result` | 25 | Vague, no failure mode named. |
| `eval()` on value from `req.body` | 100 | Confirmed RCE path. |

## Why This Works

The rubric exists to push the orchestrator toward **precision over recall**. An ultra review spawns many independent lanes precisely so it can afford to drop uncertain findings — the cost of missing a borderline issue is lower than the cost of overwhelming the reader with low-confidence noise.

Two signals dominate:

1. **Evidence anchored to the diff.** If a finding cannot be pointed at a specific changed line, it does not survive.
2. **Independent cross-lane agreement.** If multiple lenses notice the same thing from different angles, the finding is almost always real. The boost rewards this.

Everything else — severity, lens, title — is organization. These two signals decide whether a finding ships.
