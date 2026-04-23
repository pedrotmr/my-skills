---
name: ultra-review
description: Maximum-depth code review using seven parallel specialist lanes, per-finding confidence scoring against a 0-100 rubric, and deterministic consolidation. Use when the user says "ultra-review", "ultra review", "deep review", "super review", "big review", or "thorough review", and before merging high-stakes changes (auth, payments, migrations, security paths). Prioritizes reliability and determinism over speed or cost. Provider-agnostic — any orchestrator can execute it.
---

# Ultra Review

## Mission

Produce the most reliable, deterministic code review possible by running many independent specialist passes in parallel, scoring every candidate finding against a strict rubric, and reporting only what survives.

Non-goals: speed, token efficiency, running on trivial changes. Use a lighter review for small or obvious diffs.

## When to Use

- User says "ultra-review", "ultra review", "deep review", "super review", "big review", or "thorough review"
- Before merging high-stakes changes: auth, payments, data migrations, security-sensitive paths, anything customer-facing
- When a previous lighter review felt thin and the user wants more depth
- When the user explicitly says cost is not a concern

## Arguments

- `--pr <number|url>` — target a GitHub PR (uses `gh`)
- `--diff <ref>` — target a local ref range (default: working tree vs `main`)
- `--plan <path>` — optional plan/PRD/spec file for alignment checking
- `--output <path>` — report file path (default: `./ultra-review-<scope-slug>.md`)
- `--post` — after writing the report, also post it as a PR comment (requires `--pr`); off by default

Resolve scope in this fixed order: `--pr` → `--diff` → staged → working tree. If nothing is found, stop with `No review target found.`

## Pipeline

Six phases. Phases 1, 2, and 3 each dispatch multiple workers in parallel — issue all workers for a phase in one batch.

```
Phase 0: Eligibility gate    (1 worker; PR targets only)
Phase 1: Context pass        (3 parallel workers)
Phase 2: Specialist lanes    (7 parallel workers)
Phase 3: Confidence scoring  (N parallel workers, one per candidate)
Phase 4: Consolidation       (deterministic; no worker)
Phase 5: Delivery            (file; optional PR comment)
```

Worker prompts live in [reference/PROMPTS.md](reference/PROMPTS.md). The scoring rubric lives in [reference/RUBRIC.md](reference/RUBRIC.md). Do not paraphrase them; pass them verbatim.

### Phase 0 — Eligibility (PR targets only)

Skip for `--diff` targets.

Run the eligibility worker (see `reference/PROMPTS.md` → "Eligibility"). It verifies the PR is not closed, not a draft, not already ultra-reviewed in a prior comment, and not a trivial automated PR (dependabot, formatter-only, etc.). If any check fails, stop and report the reason. Do not proceed.

### Phase 1 — Context Pass

Dispatch the three context workers in parallel (`reference/PROMPTS.md` → "Context A", "Context B", "Context C"):

- **A — Change Summary.** Compact description of what changed and why, file list with LOC, referenced tickets, language/framework mix.
- **B — Convention Discovery.** Paths (not contents) to CLAUDE.md, AGENTS.md, README, CONTRIBUTING, linter/editor config relevant to changed files.
- **C — Historical Signals.** Recent commits, blame for modified regions, prior PRs touching the same files.

Cache all three outputs. They feed Phase 2 and Phase 3.

### Phase 2 — Seven Specialist Lanes

Dispatch all seven lanes in parallel (`reference/PROMPTS.md` → "Specialist 1" through "Specialist 7"):

1. **Correctness & Bugs**
2. **Security** (OWASP, secrets, trust boundaries)
3. **Architecture & Design**
4. **Performance**
5. **Readability & Simplicity**
6. **Convention Adherence** (against files found in Phase 1 B)
7. **Plan Alignment** (skip entirely if `--plan` not provided)

Each lane returns **candidate findings only**, in the schema below. Independent reasoning is what makes multi-lane signal trustworthy — do not let any lane see another lane's output during Phase 2.

### Phase 3 — Per-Finding Confidence Scoring

For every candidate finding from Phase 2, dispatch a parallel scoring worker (`reference/PROMPTS.md` → "Scorer"). Each scorer receives the finding, the relevant diff hunk, and the convention file paths from Phase 1 B. Each finding is scored independently.

**Cross-lane confirmation boost.** Before filtering, cluster findings by `location` (±3 lines) with overlapping `claim`. If a cluster contains findings from two or more distinct lanes, raise each member's final score by +10 (cap at 100). Independent agreement across lanes is strong evidence.

**Threshold.** Drop every finding whose final score is `< 80`.

Also drop findings matching the false-positive patterns in `reference/RUBRIC.md`, regardless of score.

### Phase 4 — Consolidation

Deterministic. No worker.

1. **Cluster duplicates.** Findings with the same `location` (±3 lines) and overlapping `claim` merge into one. Keep the highest-scored instance; record which other lanes flagged it as `also-flagged-by`.
2. **Sort.** Severity (Critical → Important → Suggestion), then file path A–Z, then line ascending.
3. **Cap Suggestions at 3.** Drop the remainder — do not promote them into Important.
4. **Compute verdict** using the rules below.
5. **Re-verify eligibility** for PR targets by repeating Phase 0. PRs move fast; state may have changed while workers ran.

### Phase 5 — Delivery

1. Always write the report to the `--output` path, using the File Output Format below.
2. If `--post` and `--pr` are both set, post the report as a PR comment using `gh pr comment <pr>`, using the PR Comment Format below.
3. Never auto-post without `--post`.

## Finding Schema

Every Phase 2 lane returns findings in exactly this shape:

```yaml
- title: <short imperative>
  severity: Critical | Important | Suggestion
  lens: correctness | security | architecture | performance | readability | convention | plan
  location: path:line  OR  path:startLine-endLine
  claim: <what is wrong>
  impact: <concrete failure mode — who is affected, what breaks>
  evidence: <quote from diff or context that proves the claim>
  fix: <concrete remediation, specific enough to act on>
```

## Severity Definitions

- **Critical** — security vulnerability, auth bypass, data loss/corruption risk, guaranteed runtime failure, or broken contract. Must fix before merge.
- **Important** — significant correctness, reliability, or maintainability issue likely to cause defects or incidents. Should fix before merge unless explicitly accepted as debt.
- **Suggestion** — non-blocking improvement with clear benefit. Final report caps at 3.

## Verdict Rules (Deterministic)

Apply in order:

- `REQUEST CHANGES` — any Critical survives, OR any Important scored ≥ 90
- `COMMENT` — Important findings present, all scored 80–89
- `APPROVE` — no Critical or Important findings survive Phase 3

## File Output Format

Write to `--output` path. Use this structure exactly — all sections appear even with zero findings.

```markdown
# Ultra Review — <scope>

**Verdict:** APPROVE | REQUEST CHANGES | COMMENT
**Generated:** <ISO timestamp>
**Scope:** <PR #N with URL, or commit range, or working tree>
**Lenses run:** Correctness, Security, Architecture, Performance, Readability, Convention[, Plan]
**Findings:** <N> Critical, <N> Important, <N> Suggestions
**Threshold:** findings scored < 80 were dropped

## Summary

<2-3 sentence overview of the change and overall assessment>

## Critical (<count>)

### 1. <title>
- **Location:** `path:line`
- **Lens:** <primary> (also flagged by: <others or none>)
- **Confidence:** <score>/100
- **Impact:** <concrete failure mode>
- **Evidence:**
  ```<lang>
  <quoted code>
  ```
- **Fix:** <concrete action>

## Important (<count>)

<same format as Critical>

## Suggestions (<count, max 3>)

### 1. <title>
- **Location:** `path:line`
- **Lens:** <primary>
- **Benefit:** <why it helps>
- **Suggestion:** <concrete improvement>

## Strengths

- <1–3 specific strong decisions observed — always include at least one>

## Verification Notes

- Tests reviewed: <yes/no + short note>
- Security-sensitive paths touched: <yes/no>
- Plan alignment checked: <yes — path / no — not provided>

## Process Log

- Context workers: 3
- Specialist lanes: <6 or 7>
- Candidate findings: <N>
- Dropped (score < 80): <N>
- Deduplicated: <N>
- Final findings: <N>
```

## PR Comment Format (`--post` only)

Shorter than the file. The file contains full detail; the comment is a pointer.

```markdown
### Ultra review

**Verdict:** <APPROVE | REQUEST CHANGES | COMMENT>
Found <N> issues (<N> critical, <N> important, <N> suggestions).

<For each Critical and Important finding, numbered:>
1. <short description> — <path:line>

  <permalink with full commit SHA, format: https://github.com/<owner>/<repo>/blob/<sha>/<path>#L<start>-L<end>>

<If zero findings:>
No blocking issues found. Checked across correctness, security, architecture, performance, readability, convention[, plan].

Full report: <link to file path or artifact>
```

Permalink rules (critical for rendering):

- Always use a full 40-char commit SHA, never `HEAD` or a branch name
- File anchor must use `#L<start>-L<end>` format
- Provide at least one line of context before and after the referenced line
- Do not embed shell substitutions like `$(git rev-parse HEAD)` — GitHub will not resolve them

## Hard Rules

1. Do not skip Phase 3 scoring — it is what makes the skill reliable.
2. Do not let Phase 2 lanes see each other's outputs. Independence is the signal.
3. Do not include findings with score < 80 in the final report.
4. Every Critical and Important finding must include `path:line`, an evidence quote, and a concrete fix.
5. Always write the report to the output file. Do not emit only to the terminal.
6. If `--pr` is set, include the PR URL in the scope line.
7. Cap Suggestions at 3. Drop extras; do not promote them to Important.
8. If any phase fails (missing `gh` auth, no diff, worker returns malformed output), stop and report which phase failed. Never fabricate results.
9. For PR targets, re-run the eligibility gate after Phase 4 before delivery.
10. Never auto-post without `--post`.

## Cost Note

One ultra review typically dispatches 3 context workers, 6–7 specialist lanes, and 5–30 scoring workers — roughly 14–40 delegations per run. This is deliberate: reliability and determinism are the product. For smaller changes or routine work, use a lighter review skill instead.

## See Also

- [reference/PROMPTS.md](reference/PROMPTS.md) — verbatim prompts for every worker
- [reference/RUBRIC.md](reference/RUBRIC.md) — the 0–100 confidence rubric and false-positive patterns
