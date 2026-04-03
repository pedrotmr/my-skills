# Swift macOS Release Phases

## Phase A (Preview channel, no Apple Developer account required)

Goal: publish downloadable `.dmg` and `.zip` assets + `appcast-preview.xml` from tags.

Required:
- No Apple notarization secrets required

Recommended (Sparkle integrity):
- `SPARKLE_PRIVATE_KEY` (secret)
- `SPARKLE_PUBLIC_KEY` (variable or secret)
- `SPARKLE_FEED_URL` (variable, optional override)

Expected workflow behavior:
- `release_mode=preview`
- `Import Developer ID certificate` skipped
- `Notarize` step skipped
- `Create GitHub release` uploads `.dmg`, `.zip`, and preview appcast

## Phase B (Production notarized channel)

Goal: publish notarized DMG and production appcast once Apple enrollment is ready.

Required secrets:
- `DEV_ID_CERT_BASE64`
- `DEV_ID_CERT_PASSWORD`
- `APPLE_ID`
- `APPLE_TEAM_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`
- `SPARKLE_PRIVATE_KEY`

Recommended:
- `SPARKLE_PUBLIC_KEY`
- `SPARKLE_FEED_URL`

Expected workflow behavior:
- `release_mode=production`
- Developer ID certificate imported
- Notarization + stapling executed
- release uploads `.dmg`, `.zip`, and `appcast.xml`

## Known failure guards included in template

- Per-tag workflow `concurrency` to avoid duplicate `push` + `release` races
- `actions/checkout` with `lfs: true` for LFS-tracked binaries
- explicit tag resolution for `push`, `release`, and `workflow_dispatch`
- Xcode pinning (`macos-15` + Xcode 16)
- appcast tool build logs redirected to stderr to keep command substitution clean

## Smoke test

1. Merge pipeline files to default branch.
2. Create/push a preview tag (for example `v0.1.0-preview.1`).
3. Wait for `Release` workflow to complete.
4. Verify release assets include:
- `<AppName>-<version>.dmg`
- `<AppName>-<version>.zip`
- `appcast-preview.xml`
