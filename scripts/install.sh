#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LOARING_PRODUCT_OPS_REPO:-https://github.com/xonme888/project_plugin.git}"
REF="${LOARING_PRODUCT_OPS_REF:-develop}"
PLUGIN_NAME="loaring-product-ops"
MARKETPLACE_NAME="loaring"

fail() {
  printf 'loaring-product-ops install: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_command git
require_command codex
require_command uv

printf 'Registering LoaRing marketplace from %s @ %s\n' "$REPO_URL" "$REF"
codex plugin marketplace add "$REPO_URL" --ref "$REF" >/dev/null

printf 'Refreshing marketplace %s\n' "$MARKETPLACE_NAME"
codex plugin marketplace upgrade "$MARKETPLACE_NAME" >/dev/null

printf 'Installing %s@%s\n' "$PLUGIN_NAME" "$MARKETPLACE_NAME"
codex plugin add "$PLUGIN_NAME@$MARKETPLACE_NAME" >/dev/null

printf '\nInstalled %s@%s from %s @ %s.\n' "$PLUGIN_NAME" "$MARKETPLACE_NAME" "$REPO_URL" "$REF"
printf 'Open a new Codex task to load the updated plugin tools.\n'
