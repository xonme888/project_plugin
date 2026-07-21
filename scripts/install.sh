#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LOARING_PRODUCT_OPS_REPO:-https://github.com/xonme888/project_plugin.git}"
REF="${LOARING_PRODUCT_OPS_REF:-develop}"
INSTALL_DIR="${LOARING_PRODUCT_OPS_DIR:-$HOME/.codex/loaring-product-ops}"

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

if [ -e "$INSTALL_DIR" ] && [ ! -d "$INSTALL_DIR/.git" ]; then
  fail "$INSTALL_DIR already exists and is not a git checkout"
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
  mkdir -p "$(dirname "$INSTALL_DIR")"
  printf 'Cloning LoaRing Product Ops into %s\n' "$INSTALL_DIR"
  git clone --branch "$REF" "$REPO_URL" "$INSTALL_DIR"
else
  current_remote="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
  if [ "$current_remote" != "$REPO_URL" ]; then
    fail "$INSTALL_DIR origin is $current_remote, expected $REPO_URL"
  fi
  if [ -n "$(git -C "$INSTALL_DIR" status --porcelain)" ]; then
    fail "$INSTALL_DIR has local changes; commit or clean them before updating"
  fi
  printf 'Updating LoaRing Product Ops in %s\n' "$INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch origin "$REF"
  git -C "$INSTALL_DIR" switch "$REF" >/dev/null 2>&1 || git -C "$INSTALL_DIR" switch -c "$REF" --track "origin/$REF"
  git -C "$INSTALL_DIR" pull --ff-only origin "$REF"
fi

test -x "$INSTALL_DIR/install.sh" || fail "missing executable installer: $INSTALL_DIR/install.sh"
"$INSTALL_DIR/install.sh"
