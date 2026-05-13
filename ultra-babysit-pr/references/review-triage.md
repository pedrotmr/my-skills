# Review Triage

Classify every pending review item before acting. Read the referenced code first.

## Buckets

| Bucket | Meaning | Action |
| --- | --- | --- |
| A. AI slop | Bot comment is generic, duplicative, contradicted by local convention, or asks for impossible defensive handling | For bot comments only: reply with code-backed reason, resolve, mark handled |
| B. False positive | The issue does not exist in current code, was already fixed, or the reviewer misread the flow | For bots: reply and resolve. For humans: propose the exact reply to the user |
| C. Trivial fix | Mechanical and low risk: typo, missing guard, import, rename, dead code, obvious lint/test issue | Fix, validate, push, reply/resolve if needed, mark handled |
| D. Substantive bounded fix | Real behavior, type, data, or test issue where the correct change is clear and local | Add or update tests when risk warrants it, validate, push, reply/resolve, mark handled |
| E. Design or under-80-percent confidence | Architecture, product behavior, tradeoff, broad refactor, ambiguous request, or unclear ownership | Do not resolve. Present options with recommendation |
| F. Out of scope | Valid issue outside the PR diff or beyond the current branch intent | If small and safe, treat as C/D. Otherwise propose opening an issue and ask before replying to humans |

## Bot Noise Heuristics

Treat a supported bot comment as A only when at least one is true:

- It flags a pattern used consistently in nearby code.
- It asks for a defensive check for a state that cannot occur at this callsite.
- It suggests naming, comments, or TODOs with no correctness, safety, or maintainability impact.
- It duplicates a human comment that is already being handled.
- It makes a generic "consider" suggestion with no concrete failure mode.
- It contradicts tests, types, framework guarantees, or repository conventions.

Never dismiss a bot comment that identifies a concrete bug, security issue, data loss, authorization gap, race, type error, nullability error, or deterministic test failure.

## Human Review Rules

- Fix valid human feedback directly when the fix is safe.
- Do not post disagreement, explanation-only, or clarification replies to humans without the user's explicit approval.
- If approved to reply as Codex, prefix the reply with `[codex]`.
- Do not resolve human design threads unless the requested decision has been made and reflected in code or the user explicitly approves the response.

## Marking Items Handled

After a fix or approved decision is on GitHub, mark the item handled with:

```bash
python3 scripts/ultra_pr_watch.py --pr auto --mark-handled '<item-id>'
```

Do this after resolving a thread, after the user approves a human reply, or after deciding a bot comment is safely dismissed.
