---
name: swift-macos-release
description: Bootstrap and operate a reusable GitHub release pipeline for Swift macOS apps (DMG/ZIP/appcast) with Phase A preview and Phase B notarized production. Use for new app repos or when release assets are missing.
---

# Swift macOS Release

Use this skill when setting up or fixing the standard release pipeline used in Termscape/GitBar.

## Quick command

Run the bootstrap command in the target repository (or pass repo path):

```bash
/swift-macos-release/scripts/bootstrap_release_pipeline.sh [repo_path]
```

Use `--force` only if you intentionally want to overwrite existing release files.

## What this sets up

- `.github/workflows/release.yml`
- `Scripts/release/{build,package,notarize,appcast,publish,common}.sh`
- `Scripts/release/config.env.example`
- `.gitignore` entry for `Scripts/release/config.env`

It auto-detects:
- `APP_NAME`
- `XCODE_SCHEME`
- `XCODE_PROJECT`
- GitHub repo slug for feed URLs

## Execution protocol

1. Run bootstrap command.
2. Validate generated files:
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/release.yml")'`
- `for f in Scripts/release/*.sh; do bash -n "$f"; done`
3. Commit and push.
4. Trigger preview tag release (`v*`) and verify assets in GitHub Release.
5. If the request includes production readiness, apply Phase B secrets and rerun with a fresh tag.

## Troubleshooting order

1. Check `Release` workflow run status and failed step logs.
2. If `.dmg` missing, confirm `Package artifacts` succeeded.
3. If appcast step fails, inspect `Generate appcast` logs.
4. If binary link errors mention unexpected file types, verify LFS checkout + tracked files.
5. If duplicate runs appear for one tag, confirm `concurrency` block exists in workflow.

## Phase checklist

Read:
- `references/phase-checklist.md`
