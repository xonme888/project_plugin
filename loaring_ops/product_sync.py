"""Read-only product metadata synchronization."""

from __future__ import annotations

import re
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from .config import PRODUCT_PATHS, repo_name, repo_ref
from .db import connect, init_db
from .github_client import fetch_file


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sync_product(repo: str | None = None, ref: str | None = None) -> dict[str, Any]:
    selected_repo = repo_name(repo)
    selected_ref = repo_ref(ref)
    fetched_at = now_iso()
    conn = connect()
    init_db(conn)

    fetched: list[dict[str, Any]] = []
    for path in PRODUCT_PATHS:
        content, sha = fetch_file(selected_repo, selected_ref, path)
        conn.execute(
            """
            INSERT INTO product_snapshots (repo, ref, path, sha, content, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo, ref, path) DO UPDATE SET
              sha = excluded.sha,
              content = excluded.content,
              fetched_at = excluded.fetched_at
            """,
            (selected_repo, selected_ref, path, sha, content, fetched_at),
        )
        fetched.append({"path": path, "sha": sha})

    index_cached_product(conn, selected_repo, selected_ref, fetched_at)
    conn.execute(
        """
        INSERT INTO sync_state (source, repo, ref, last_synced_at)
        VALUES ('product-docs', ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
          repo = excluded.repo,
          ref = excluded.ref,
          last_synced_at = excluded.last_synced_at
        """,
        (selected_repo, selected_ref, fetched_at),
    )
    conn.commit()
    return {"repo": selected_repo, "ref": selected_ref, "fetchedAt": fetched_at, "files": fetched}


def snapshot(conn: sqlite3.Connection, path: str, repo: str | None = None, ref: str | None = None) -> str | None:
    row = conn.execute(
        """
        SELECT content FROM product_snapshots
        WHERE path = ?
          AND (? IS NULL OR repo = ?)
          AND (? IS NULL OR ref = ?)
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (path, repo, repo, ref, ref),
    ).fetchone()
    return None if row is None else str(row["content"])


def index_cached_product(conn: sqlite3.Connection, repo: str | None, ref: str | None, updated_at: str) -> None:
    catalog_content = snapshot(conn, "docs/api/api-catalog.yml", repo, ref)
    if catalog_content:
        for spec in parse_api_catalog(catalog_content):
            conn.execute(
                """
                INSERT INTO api_specs (
                  path, domain, title, story_issue, requirement_ids_json,
                  endpoints_json, lifecycle, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                  domain = excluded.domain,
                  title = excluded.title,
                  story_issue = excluded.story_issue,
                  requirement_ids_json = excluded.requirement_ids_json,
                  endpoints_json = excluded.endpoints_json,
                  lifecycle = excluded.lifecycle,
                  updated_at = excluded.updated_at
                """,
                (
                    spec.get("path"),
                    spec.get("domain"),
                    spec.get("title"),
                    spec.get("storyIssue"),
                    json.dumps(spec.get("requirementIds") or [], ensure_ascii=False),
                    json.dumps(spec.get("endpoints") or [], ensure_ascii=False),
                    spec.get("lifecycle"),
                    updated_at,
                ),
            )

    trace_content = snapshot(conn, "docs/requirements/traceability.yml", repo, ref)
    if trace_content:
        for req in parse_traceability(trace_content):
            conn.execute(
                """
                INSERT INTO requirements (
                  requirement_id, title, status, epic, story_issues_json,
                  api_specs_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(requirement_id) DO UPDATE SET
                  title = excluded.title,
                  status = excluded.status,
                  epic = excluded.epic,
                  story_issues_json = excluded.story_issues_json,
                  api_specs_json = excluded.api_specs_json,
                  updated_at = excluded.updated_at
                """,
                (
                    req.get("id"),
                    req.get("title"),
                    req.get("status"),
                    req.get("epic"),
                    json.dumps(req.get("storyIssues") or [], ensure_ascii=False),
                    json.dumps(req.get("apiSpecs") or [], ensure_ascii=False),
                    updated_at,
                ),
            )


def find_story(query: str, limit: int = 10) -> dict[str, Any]:
    conn = connect()
    init_db(conn)
    like = f"%{query}%"
    req_rows = conn.execute(
        """
        SELECT * FROM requirements
        WHERE requirement_id LIKE ? OR title LIKE ? OR epic LIKE ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (like, like, like, limit),
    ).fetchall()
    spec_rows = conn.execute(
        """
        SELECT * FROM api_specs
        WHERE path LIKE ? OR title LIKE ? OR domain LIKE ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (like, like, like, limit),
    ).fetchall()
    story_map = snapshot(conn, "docs/requirements/story-map.md")
    story_map_hits = search_story_map(story_map or "", query, limit)
    return {
        "requirements": [decode_json_fields(dict(row)) for row in req_rows],
        "apiSpecs": [decode_json_fields(dict(row)) for row in spec_rows],
        "storyMapHits": story_map_hits,
    }


def get_contract(story_issue: int | None = None, requirement_id: str | None = None) -> dict[str, Any]:
    conn = connect()
    init_db(conn)
    specs: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []

    if requirement_id:
        req_row = conn.execute("SELECT * FROM requirements WHERE requirement_id = ?", (requirement_id,)).fetchone()
        if req_row:
            req = decode_json_fields(dict(req_row))
            requirements.append(req)
            for path in req.get("api_specs", []):
                spec_row = conn.execute("SELECT * FROM api_specs WHERE path = ?", (path,)).fetchone()
                if spec_row:
                    specs.append(decode_json_fields(dict(spec_row)))

    if story_issue is not None:
        for row in conn.execute("SELECT * FROM api_specs WHERE story_issue = ?", (story_issue,)).fetchall():
            specs.append(decode_json_fields(dict(row)))
        for row in conn.execute("SELECT * FROM requirements").fetchall():
            req = decode_json_fields(dict(row))
            if story_issue in req.get("story_issues", []):
                requirements.append(req)

    return {"storyIssue": story_issue, "requirementId": requirement_id, "requirements": requirements, "apiSpecs": dedupe_by_path(specs)}


def validate_contract_readiness(story_issue: int | None = None, requirement_id: str | None = None) -> dict[str, Any]:
    contract = get_contract(story_issue=story_issue, requirement_id=requirement_id)
    specs = contract["apiSpecs"]
    issues: list[str] = []
    if not specs:
        issues.append("No linked full api-spec entry found in api-catalog.yml.")
    for spec in specs:
        if spec.get("lifecycle") not in {"accepted", "review", "draft"}:
            issues.append(f"{spec.get('path')}: lifecycle is missing or unknown.")
        if not spec.get("endpoints"):
            issues.append(f"{spec.get('path')}: no endpoints indexed.")
    ready = not issues and bool(specs)
    return {
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "issues": issues,
        "contract": contract,
    }


def decode_json_fields(row: dict[str, Any]) -> dict[str, Any]:
    renamed = dict(row)
    for old, new in [
        ("requirement_ids_json", "requirement_ids"),
        ("endpoints_json", "endpoints"),
        ("story_issues_json", "story_issues"),
        ("api_specs_json", "api_specs"),
    ]:
        if old in renamed:
            renamed[new] = json.loads(renamed.pop(old) or "[]")
    return renamed


def dedupe_by_path(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for spec in specs:
        path = str(spec.get("path"))
        if path in seen:
            continue
        seen.add(path)
        result.append(spec)
    return result


def search_story_map(content: str, query: str, limit: int) -> list[str]:
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return []
    hits: list[str] = []
    for line in content.splitlines():
        if any(term.lower() in line.lower() for term in terms):
            hits.append(line)
            if len(hits) >= limit:
                break
    return hits


def parse_api_catalog(content: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_endpoints = False

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("- path:"):
            if current:
                specs.append(current)
            current = {
                "path": scalar(stripped.split(":", 1)[1]),
                "endpoints": [],
            }
            in_endpoints = False
            continue
        if current is None:
            continue
        if stripped.startswith("domain:"):
            current["domain"] = scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("title:"):
            current["title"] = scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("storyIssue:"):
            current["storyIssue"] = int_or_none(scalar(stripped.split(":", 1)[1]))
        elif stripped.startswith("requirementIds:"):
            current["requirementIds"] = inline_list(stripped.split(":", 1)[1])
        elif stripped.startswith("lifecycle:"):
            current["lifecycle"] = scalar(stripped.split(":", 1)[1])
        elif stripped.startswith("endpoints:"):
            in_endpoints = True
        elif in_endpoints and stripped.startswith("- id:"):
            current["endpoints"].append({"id": scalar(stripped.split(":", 1)[1])})
        elif in_endpoints and stripped.startswith("changePolicy:") and current["endpoints"]:
            current["endpoints"][-1]["changePolicy"] = scalar(stripped.split(":", 1)[1])

    if current:
        specs.append(current)
    return specs


def parse_traceability(content: str) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    active_list: str | None = None

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- id:"):
            if current:
                requirements.append(current)
            current = {"id": scalar(stripped.split(":", 1)[1]), "storyIssues": [], "apiSpecs": []}
            active_list = None
            continue
        if current is None:
            continue
        if stripped.startswith("title:"):
            current["title"] = scalar(stripped.split(":", 1)[1])
            active_list = None
        elif stripped.startswith("status:"):
            current["status"] = scalar(stripped.split(":", 1)[1])
            active_list = None
        elif stripped.startswith("epic:"):
            current["epic"] = scalar(stripped.split(":", 1)[1])
            active_list = None
        elif stripped.startswith("storyIssues:"):
            current["storyIssues"] = [int(item) for item in inline_list(stripped.split(":", 1)[1]) if str(item).isdigit()]
            active_list = "storyIssues"
        elif stripped.startswith("apiSpecs:"):
            current["apiSpecs"] = inline_list(stripped.split(":", 1)[1])
            active_list = "apiSpecs"
        elif stripped.endswith(":"):
            active_list = None
        elif stripped.startswith("- ") and active_list == "apiSpecs":
            current["apiSpecs"].append(scalar(stripped[2:]))

    if current:
        requirements.append(current)
    return requirements


def scalar(value: str) -> str:
    cleaned = value.strip()
    if cleaned in {"null", "None", "~"}:
        return ""
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        return cleaned[1:-1]
    return cleaned


def inline_list(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if not (cleaned.startswith("[") and cleaned.endswith("]")):
        return []
    inner = cleaned[1:-1].strip()
    if not inner:
        return []
    return [scalar(part) for part in inner.split(",")]


def int_or_none(value: str) -> int | None:
    return int(value) if value.isdigit() else None
