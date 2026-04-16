---
name: review-code
description: Performs deterministic, high-signal code review across correctness, readability, architecture, security, and performance. Use for local changes or PR reviews when the user needs trustworthy, consistent, low-noise findings before merge.
---

# Code Review

## Mission

Produce a reliable, repeatable review that prioritizes real risk.

Required outcomes:

- Catch issues that can materially impact correctness, security, reliability, architecture, or performance.
- Suppress low-value noise, preference-only comments, and speculative claims.
- Keep results stable across repeated runs on the same review input.

## Review Target Resolution

Resolve scope in this fixed order:

1. User-provided files/range/commit range
2. PR diff (when a PR is explicitly targeted)
3. Staged changes
4. Working tree changes

If no reviewable changes are found, stop and report:
`No review target found (no diff in selected scope).`

## Five-Axis Framework

Evaluate every review target across all five axes:

1. **Correctness**

- Requirements alignment, logic correctness, edge cases, failure paths, state integrity.

2. **Readability**

- Naming clarity, control flow simplicity, local comprehensibility, maintainable structure.

3. **Architecture**

- Pattern consistency, boundary integrity, coupling direction, abstraction fitness.

4. **Security**

- Input trust boundaries, auth/authz correctness, secret handling, injection and exposure risks.

5. **Performance**

- Hot-path cost, data access shape, unbounded work, avoidable latency/throughput regressions.

Every `Critical` and `Important` finding must map to one primary axis.

## Mode Selection (Deterministic)

Select exactly one mode using these deterministic rules:

- `Sanity`:
  - <= 50 changed lines and
  - docs/config/non-runtime-only edits and
  - no security-sensitive paths touched
- `Standard` (default):
  - Any normal feature/fix/refactor review not matching `Sanity` or `Deep`
- `Deep`:
  - > 400 changed lines, or
  - > 15 files changed, or
  - security/authorization/identity/payment/data-migration/runtime-critical areas changed

## Review Architecture

### Standard Path

Use one reviewer pass, then run a strict validation pass before reporting.

### Deep Path (Parallel by Default)

If subagents/parallel lanes are available, run four independent reviewer lanes in parallel:

- Lane 1: Correctness + data integrity + failure handling
- Lane 2: Security + trust boundaries + sensitive data paths
- Lane 3: Architecture + maintainability + coupling
- Lane 4: Performance + operability + test adequacy

Then run a separate validation pass for every candidate issue before final output.

Fallback when subagents are unavailable:

- Run the same four lanes sequentially with the same output schema and validation gate.

## Candidate Issue Schema

Each review lane must return candidate issues in this shape:

- `title`
- `severity` (`Critical` | `Important` | `Suggestion`)
- `axis` (one of the five axes)
- `location` (`path:line`)
- `claim` (what is wrong)
- `impact` (why it matters)
- `evidence` (fact from diff/context)
- `fix` (concrete remediation)
- `confidence` (`high` | `medium` | `low`)

## High-Signal Policy

Report findings only when all conditions are true:

1. The issue is grounded in the reviewed diff (or immediate surrounding context needed to verify it).
2. There is a concrete failure mode, not a stylistic preference.
3. The impact is meaningful (security, correctness, reliability, or measurable operability/performance risk).
4. A specific fix direction is available.
5. Confidence is `medium` or `high`.

If confidence is `low`, emit a `Question`, not a finding.

## False-Positive Guardrails

Do not report:

- Preference-only style comments unless the user explicitly requests style review.
- Issues that are not verifiable from reviewed code/context.
- Hypothetical risks without a concrete failure path.
- Pre-existing issues outside the review scope unless explicitly requested.
- Pure lint/formatter findings without meaningful runtime or design impact.

## Severity Model

- `Critical`:
  - Security vulnerability, auth bypass, data loss/corruption risk, guaranteed runtime failure, or contract-breaking behavior
  - Must be fixed before merge
- `Important`:
  - Significant correctness/reliability/maintainability issue likely to cause defects or expensive incidents
  - Should be fixed before merge unless explicitly accepted debt
- `Suggestion`:
  - Non-blocking improvement with clear benefit
  - Cap at 3 suggestions per review

## Review Procedure (Always This Order)

1. **Intent check**
   - Identify expected behavior from task/PR description.
2. **Tests first**
   - Evaluate whether tests validate behavior and regressions, not implementation details.
3. **High-level design pass**
   - Validate boundaries, invariants, and dependency direction.
4. **Line-level risk pass**
   - Review by priority: security -> correctness -> data integrity/reliability -> operability -> performance -> maintainability.
5. **Issue validation pass**
   - Validate each candidate issue independently for evidence, impact, and confidence.
6. **Deduplicate + normalize**
   - Merge repeated root causes; avoid repeated comments for the same issue.
7. **Verdict**
   - Apply deterministic verdict rules below.

## Deterministic Verdict Rules

- `REQUEST CHANGES`:
  - Any `Critical`, or
  - Any `Important` with unresolved high-confidence impact
- `COMMENT`:
  - No Critical findings, but unresolved `Important` findings with medium confidence or unresolved Questions
- `APPROVE`:
  - No Critical or Important findings

## Output Contract (Stable Format)

Use this exact section order:

```markdown
Review: [Sanity|Standard|Deep] — [APPROVE|REQUEST CHANGES|COMMENT]
Scope: [what was reviewed]
Confidence: [high|medium|low]
Axes Covered: [Correctness, Readability, Architecture, Security, Performance]

Critical ([count])

- [path:line] [short title] [axis]
  Why it matters: [impact]
  Evidence: [fact from code/diff]
  Fix: [concrete action]

Important ([count])

- [path:line] [short title] [axis]
  Why it matters: [impact]
  Evidence: [fact from code/diff]
  Fix: [concrete action]

Suggestions ([count, max 3])

- [path:line] [short title] [axis]
  Benefit: [why it helps]
  Suggestion: [concrete improvement]

Questions ([count])

- ...

Strengths ([count])

- [specific strong decision observed]

Verification

- Tests reviewed: [yes/no + note]
- Build/typecheck evidence: [available/not available]
- Security-sensitive paths touched: [yes/no]
```

When there are zero findings, still output all sections with `0` counts.

## Consistency Guards

Before finalizing, run this check:

1. Every `Critical`/`Important` has `path:line`, impact, evidence, and fix.
2. Every `Critical`/`Important` includes one primary axis tag.
3. No duplicate root-cause findings.
4. Every reported finding passed the validation pass.
5. Suggestions are <= 3 and non-blocking.
6. No style-only findings unless explicitly requested.
7. Findings are sorted by:
   - severity (`Critical` -> `Important` -> `Suggestion`)
   - file path (A-Z)
   - line number (ascending)
8. If parallel lanes were used:
   - include only issues confirmed by validation
   - keep one merged issue per unique root cause

If a finding fails this check, remove it or downgrade it to `Question`.

## Reliability Hardening

To improve run-to-run consistency:

- Use the same mode selection thresholds every time.
- Use the same five-axis pass order every time.
- Do not exceed three Suggestions.
- Prefer omission over weak or uncertain claims.
- Never invent requirements or hidden constraints.
- Never block merge on speculation.
- If key context is missing, ask one concise clarifying question and provide the best bounded review.

## Multi-Agent Orchestration Notes

When parallel lanes are available, enforce:

- Independent lane reasoning before cross-lane merge.
- No lane sees another lane's findings until merge stage.
- Validation pass runs after merge-candidate list is assembled.
- Final report includes only validated findings.

This pattern improves recall while reducing false positives and keeps outputs stable.
