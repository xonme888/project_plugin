#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="loaring-product-ops"
MARKETPLACE_NAME="loaring"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

fail() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

require_command codex
require_command uv

test -f "$SCRIPT_DIR/.agents/plugins/marketplace.json" || fail "missing .agents/plugins/marketplace.json"
test -f "$SCRIPT_DIR/.codex-plugin/plugin.json" || fail "missing .codex-plugin/plugin.json"
test -f "$SCRIPT_DIR/.mcp.json" || fail "missing .mcp.json"

printf 'Installing %s from %s\n' "$PLUGIN_NAME" "$SCRIPT_DIR"
codex plugin marketplace add "$SCRIPT_DIR"
codex plugin add "$PLUGIN_NAME@$MARKETPLACE_NAME"

printf '\nInstalled %s@%s.\n' "$PLUGIN_NAME" "$MARKETPLACE_NAME"
printf 'Open a new Codex task to load the updated plugin tools.\n'
