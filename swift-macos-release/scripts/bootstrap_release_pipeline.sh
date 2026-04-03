#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Bootstrap reusable macOS Swift release pipeline into a repository.

Usage:
  $(basename "$0") [repo_path] [--force]

Defaults:
  repo_path: current directory

Options:
  --force   overwrite existing workflow/script files
USAGE
}

FORCE=0
REPO_PATH=""

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -z "$REPO_PATH" ]]; then
        REPO_PATH="$arg"
      else
        echo "error: unexpected argument '$arg'" >&2
        usage
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$REPO_PATH" ]]; then
  REPO_PATH="$PWD"
fi

REPO_PATH=$(cd "$REPO_PATH" && pwd)

if ! git -C "$REPO_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: '$REPO_PATH' is not a git repository" >&2
  exit 1
fi

SKILL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TEMPLATE_DIR="$SKILL_DIR/assets/template"

PROJECT_FILE=$(find "$REPO_PATH" -maxdepth 2 -type d -name "*.xcodeproj" | head -n 1 || true)
if [[ -z "$PROJECT_FILE" ]]; then
  echo "error: no .xcodeproj found under '$REPO_PATH'" >&2
  exit 1
fi

PROJECT_NAME=$(basename "$PROJECT_FILE" .xcodeproj)
XCODE_PROJECT="${PROJECT_NAME}.xcodeproj"

SCHEME_DIR="$PROJECT_FILE/xcshareddata/xcschemes"
if [[ -d "$SCHEME_DIR" ]]; then
  SCHEME_FILE=$(find "$SCHEME_DIR" -maxdepth 1 -type f -name "*.xcscheme" | head -n 1 || true)
else
  SCHEME_FILE=""
fi

if [[ -n "$SCHEME_FILE" ]]; then
  XCODE_SCHEME=$(basename "$SCHEME_FILE" .xcscheme)
else
  XCODE_SCHEME="$PROJECT_NAME"
fi

APP_NAME="$XCODE_SCHEME"

ORIGIN_URL=$(git -C "$REPO_PATH" remote get-url origin 2>/dev/null || true)
GITHUB_REPO_SLUG="owner/repo"
if [[ "$ORIGIN_URL" =~ ^https://github.com/([^/]+)/([^/.]+)(\.git)?$ ]]; then
  GITHUB_REPO_SLUG="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
elif [[ "$ORIGIN_URL" =~ ^git@github.com:([^/]+)/([^/.]+)(\.git)?$ ]]; then
  GITHUB_REPO_SLUG="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
fi

copy_file() {
  local src="$1"
  local dst="$2"

  if [[ -e "$dst" && "$FORCE" -ne 1 ]]; then
    echo "skip: $dst (already exists; use --force to overwrite)"
    return
  fi

  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  echo "write: $dst"
}

copy_file "$TEMPLATE_DIR/.github/workflows/release.yml" "$REPO_PATH/.github/workflows/release.yml"

for script in appcast.sh build.sh common.sh notarize.sh package.sh publish.sh config.env.example; do
  copy_file "$TEMPLATE_DIR/Scripts/release/$script" "$REPO_PATH/Scripts/release/$script"
done

if [[ -f "$REPO_PATH/.gitignore" ]]; then
  if ! grep -q '^Scripts/release/config.env$' "$REPO_PATH/.gitignore"; then
    printf '\nScripts/release/config.env\n' >> "$REPO_PATH/.gitignore"
    echo "update: $REPO_PATH/.gitignore"
  fi
fi

for f in "$REPO_PATH/Scripts/release/common.sh" "$REPO_PATH/Scripts/release/config.env.example"; do
  [[ -f "$f" ]] || continue
  sed -i.bak \
    -e "s|__APP_NAME__|$APP_NAME|g" \
    -e "s|__XCODE_SCHEME__|$XCODE_SCHEME|g" \
    -e "s|__XCODE_PROJECT__|$XCODE_PROJECT|g" \
    -e "s|__GITHUB_REPO_SLUG__|$GITHUB_REPO_SLUG|g" \
    "$f"
  rm -f "$f.bak"
done

chmod +x "$REPO_PATH/Scripts/release/"*.sh 2>/dev/null || true

echo ""
echo "Release pipeline bootstrapped for: $GITHUB_REPO_SLUG"
echo "Detected: APP_NAME=$APP_NAME, XCODE_SCHEME=$XCODE_SCHEME, XCODE_PROJECT=$XCODE_PROJECT"
echo ""
echo "Next steps:"
echo "1. Commit generated files."
echo "2. Add repo secrets/vars (Phase A/B checklist in skill references)."
echo "3. Push a tag like v0.1.0-preview.1 to test release assets."
