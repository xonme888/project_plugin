#!/usr/bin/env python3
"""Validate the plugin bundle before team distribution."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    ".python-version",
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "README.md",
    "LICENSE",
    "mcp/server.py",
    "pyproject.toml",
    "uv.lock",
]
REQUIRED_PYTHON_VERSION = (3, 11)
REQUIRED_PYTHON_VERSION_TEXT = "3.11"
REQUIRED_PYTHON_SPEC = ">=3.11,<3.12"
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
    errors.extend(validate_python_policy())
    errors.extend(validate_dependencies())
    errors.extend(validate_manifest())
    errors.extend(validate_skills())
    errors.extend(validate_commit_message_policy())
    errors.extend(validate_mcp_tool_list())
    errors.extend(validate_no_secrets())
    errors.extend(validate_no_personal_paths())
    errors.extend(validate_compile())

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Release validation passed.")
    return 0


def validate_required_files() -> list[str]:
    return [f"Missing required file: {path}" for path in REQUIRED_FILES if not (ROOT / path).is_file()]


def validate_python_policy() -> list[str]:
    errors: list[str] = []
    if sys.version_info[:2] != REQUIRED_PYTHON_VERSION:
        errors.append(
            "Release validation must run on Python "
            f"{REQUIRED_PYTHON_VERSION_TEXT}; current runtime is {sys.version_info.major}.{sys.version_info.minor}."
        )

    python_version_path = ROOT / ".python-version"
    if python_version_path.is_file():
        configured_version = python_version_path.read_text(encoding="utf-8").strip()
        if configured_version != REQUIRED_PYTHON_VERSION_TEXT:
            errors.append(f".python-version must be {REQUIRED_PYTHON_VERSION_TEXT}.")

    pyproject_path = ROOT / "pyproject.toml"
    if pyproject_path.is_file():
        pyproject_text = pyproject_path.read_text(encoding="utf-8")
        expected_line = f'requires-python = "{REQUIRED_PYTHON_SPEC}"'
        if expected_line not in pyproject_text:
            errors.append(f"pyproject.toml must declare {expected_line}.")

    return errors


def validate_dependencies() -> list[str]:
    errors: list[str] = []
    pyproject_path = ROOT / "pyproject.toml"
    if pyproject_path.is_file() and '"fastmcp>=' not in pyproject_path.read_text(encoding="utf-8"):
        errors.append("pyproject.toml must declare fastmcp as a dependency.")

    try:
        import fastmcp  # noqa: F401, PLC0415
    except Exception as exc:  # noqa: BLE001 - release validation boundary
        errors.append(f"fastmcp must be importable in the release environment: {exc}")

    return errors


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
    errors.extend(validate_mcp_config())
    return errors


def validate_skills() -> list[str]:
    required_skills = {
        "api-contract",
        "commit-message",
        "git-workflow",
        "implementation-brief",
        "requirement-analysis",
        "story-intake",
    }
    skills_dir = ROOT / "skills"
    errors: list[str] = []
    for skill_name in sorted(required_skills):
        skill_path = skills_dir / skill_name / "SKILL.md"
        if not skill_path.is_file():
            errors.append(f"Missing required skill: {skill_name}.")
            continue
        text = skill_path.read_text(encoding="utf-8")
        if f"name: {skill_name}" not in text and f'name: "{skill_name}"' not in text:
            errors.append(f"{skill_path.relative_to(ROOT)} must declare name: {skill_name}.")
        if "description:" not in text:
            errors.append(f"{skill_path.relative_to(ROOT)} must declare a description.")
    return errors


def validate_commit_message_policy() -> list[str]:
    script = ROOT / "scripts" / "validate_commit_message.py"
    if not script.is_file():
        return ["Missing scripts/validate_commit_message.py."]

    valid_messages = [
        "docs(api): 회원가입 계약 준비 규칙 추가",
        "feat(mcp): Story 워크플로 전이 검증 추가",
        "chore(release): 번들 스킬 메타데이터 검증 추가",
    ]
    invalid_messages = [
        "updated files",
        "Fix stuff.",
        "docs(api): add signup contract readiness rules",
        "docs(api): 회원가입 계약 준비 규칙 추가.",
    ]

    errors: list[str] = []
    for message in valid_messages:
        result = run_commit_message_validator(script, message)
        if result.returncode != 0:
            errors.append(f"Valid commit message rejected: {message}")
    for message in invalid_messages:
        result = run_commit_message_validator(script, message)
        if result.returncode == 0:
            errors.append(f"Invalid commit message accepted: {message}")
    return errors


def run_commit_message_validator(script: Path, message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--message", message],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def validate_mcp_config() -> list[str]:
    config_path = ROOT / ".mcp.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - release validation boundary
        return [f"Invalid MCP config: {exc}"]

    server = (config.get("mcpServers") or {}).get("loaring-product-ops") or {}
    errors: list[str] = []
    if server.get("command") != "uv":
        errors.append(".mcp.json loaring-product-ops command must be uv.")
    if server.get("args") != ["run", "python", "./mcp/server.py"]:
        errors.append(".mcp.json loaring-product-ops args must be ['run', 'python', './mcp/server.py'].")
    if server.get("cwd") != ".":
        errors.append(".mcp.json loaring-product-ops cwd must be .")
    return errors


def validate_mcp_tool_list() -> list[str]:
    try:
        import anyio  # noqa: PLC0415

        tools = anyio.run(list_mcp_tools)
        tool_names = {tool.name for tool in tools}
    except Exception as exc:  # noqa: BLE001 - release validation boundary
        return [f"MCP tools/list failed: {exc}"]

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
    errors = [f"MCP tool is missing: {name}" for name in sorted(required - tool_names)]

    sys.path.insert(0, str(ROOT))
    from loaring_ops.mcp_schema import available_schema_names  # noqa: PLC0415
    from loaring_ops.mcp_tools import available_tool_names  # noqa: PLC0415

    schema_names = available_schema_names()
    handler_names = available_tool_names()
    for name in sorted(schema_names - tool_names):
        errors.append(f"MCP schema module tool is missing from tools/list: {name}")
    for name in sorted(tool_names - schema_names):
        errors.append(f"MCP tools/list exposes a tool missing from schema module: {name}")
    for name in sorted(handler_names - tool_names):
        errors.append(f"MCP handler has no schema: {name}")
    for name in sorted(tool_names - handler_names):
        errors.append(f"MCP schema has no handler: {name}")
    errors.extend(validate_representative_tool_call())
    return errors


async def list_mcp_tools() -> list[Any]:
    server = load_mcp_server()
    return await server.list_tools()


def load_mcp_server() -> Any:
    server_path = ROOT / "mcp" / "server.py"
    spec = importlib.util.spec_from_file_location("loaring_product_ops_mcp_server", server_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load mcp/server.py module spec.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_server()


def validate_representative_tool_call() -> list[str]:
    try:
        import anyio  # noqa: PLC0415

        anyio.run(call_representative_tool)
    except Exception as exc:  # noqa: BLE001 - release validation boundary
        return [f"MCP representative tools/call failed: {exc}"]
    return []


async def call_representative_tool() -> None:
    server = load_mcp_server()
    result = await server.call_tool("loaring_find_story", {"query": "auth", "limit": 1})
    if not result.content:
        raise RuntimeError("loaring_find_story returned no content.")


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


def validate_no_personal_paths() -> list[str]:
    blocked_literals = [
        "/" + "Users" + "/",
        "/" + "home" + "/",
        "~" + "/.agents",
        "@" + "personal",
    ]
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", ".gitignore"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT)
        for literal in blocked_literals:
            if literal in text:
                errors.append(f"Personal or machine-local path found in {rel}.")
                break
    return errors


def validate_compile() -> list[str]:
    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="loaring-product-ops-pycache-") as pycache_dir:
        env["PYTHONPYCACHEPREFIX"] = pycache_dir
        result = subprocess.run(
            [sys.executable, "-m", "compileall", "loaring_ops", "mcp", "scripts"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )
    if result.returncode == 0:
        return []
    return [result.stderr.strip() or result.stdout.strip() or "compileall failed"]


def should_skip(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    return bool(parts & {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "dist", "tmp"})


if __name__ == "__main__":
    raise SystemExit(main())
