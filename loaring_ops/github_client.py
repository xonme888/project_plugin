"""Small GitHub client backed by the gh CLI."""

from __future__ import annotations

import base64
import json
import subprocess


def gh_api(path: str) -> dict:
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
    )
    check_result(result)
    return json.loads(result.stdout)


def gh_api_paginated(path: str) -> list[dict]:
    result = subprocess.run(
        ["gh", "api", "--paginate", path],
        capture_output=True,
        text=True,
    )
    check_result(result)
    payloads: list[dict] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        decoded = json.loads(line)
        if isinstance(decoded, list):
            payloads.extend(item for item in decoded if isinstance(item, dict))
        elif isinstance(decoded, dict):
            payloads.append(decoded)
    return payloads


def gh_graphql(query: str, variables: dict[str, object]) -> dict:
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        flag = "-F" if isinstance(value, int) else "-f"
        args.extend([flag, f"{key}={value}"])
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
    )
    check_result(result)
    return json.loads(result.stdout)


def check_result(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode == 0:
        return
    detail = result.stderr.strip() or result.stdout.strip() or f"exit status {result.returncode}"
    raise RuntimeError(f"gh command failed: {detail}")


def fetch_file(repo: str, ref: str, path: str) -> tuple[str, str | None]:
    payload = gh_api(f"repos/{repo}/contents/{path}?ref={ref}")
    if payload.get("type") != "file":
        raise RuntimeError(f"{path}: expected a file in {repo}@{ref}")
    encoded = payload.get("content")
    if not isinstance(encoded, str):
        raise RuntimeError(f"{path}: GitHub response did not include file content")
    content = base64.b64decode(encoded).decode("utf-8")
    sha = payload.get("sha")
    return content, sha if isinstance(sha, str) else None
