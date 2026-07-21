#!/usr/bin/env python3
"""Validate the plugin bundle before team distribution."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "README.md",
    "LICENSE",
    "mcp/server.py",
]
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[abp]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?i)(password|secret|api[_-]?key)\s*=\s*['\"][^'\"]+['\"]"),
]
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yml",
    ".yaml",
}


def main() -> int:
    errors: list[str] = []
    errors.extend(validate_required_files())
    errors.extend(validate_manifest())
    errors.extend(validate_mcp_tool_list())
    errors.extend(validate_no_secrets())
    errors.extend(validate_compile())

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Release validation passed.")
    return 0


def validate_required_files() -> list[str]:
    return [f"Missing required file: {path}" for path in REQUIRED_FILES if not (ROOT / path).is_file()]


def validate_manifest() -> list[str]:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - release validation boundary
        return [f"Invalid plugin manifest: {exc}"]

    errors: list[str] = []
    if manifest.get("name") != "loaring-product-ops":
        errors.append("plugin.json name must be loaring-product-ops.")
    if not manifest.get("version"):
        errors.append("plugin.json version is required.")
    if manifest.get("skills") != "./skills/":
        errors.append("plugin.json skills must point to ./skills/.")
    if manifest.get("mcpServers") != "./.mcp.json":
        errors.append("plugin.json mcpServers must point to ./.mcp.json.")
    if "hooks" in manifest:
        errors.append("plugin.json must not contain unsupported hooks.")
    return errors


def validate_mcp_tool_list() -> list[str]:
    server = ROOT / "mcp" / "server.py"
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    result = subprocess.run(
        [sys.executable, str(server)],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        return [f"MCP tools/list failed: {result.stderr.strip() or result.stdout.strip()}"]
    try:
        response = json.loads(result.stdout)
        tool_names = {tool["name"] for tool in response["result"]["tools"]}
    except Exception as exc:  # noqa: BLE001 - release validation boundary
        return [f"MCP tools/list returned invalid JSON: {exc}"]

    required = {
        "loaring_sync_product",
        "loaring_get_story",
        "loaring_get_contract",
        "loaring_update_project_fields",
        "loaring_apply_workflow_transition",
        "loaring_create_work_branch",
        "loaring_prepare_pr",
        "loaring_contract_gap_report",
    }
    missing = sorted(required - tool_names)
    return [f"MCP tool is missing: {name}" for name in missing]


def validate_no_secrets() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"Potential secret pattern found in {rel}.")
                break
    return errors


def validate_compile() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "compileall", "loaring_ops", "mcp", "scripts"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode == 0:
        return []
    return [result.stderr.strip() or result.stdout.strip() or "compileall failed"]


def should_skip(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    return bool(parts & {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "dist", "tmp"})


if __name__ == "__main__":
    raise SystemExit(main())
