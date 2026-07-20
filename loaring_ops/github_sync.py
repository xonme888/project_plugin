"""Read-only GitHub Issue and Project sync."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .config import legacy_story_repos, project_number, story_repo_name
from .db import connect, init_db
from .github_client import gh_api_paginated, gh_graphql
from .product_sync import now_iso


PROJECT_ITEMS_QUERY = """
query($owner: String!, $number: Int!%s) {
  %s(login: $owner) {
    projectV2(number: $number) {
      items(first: 100%s) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue {
              number
              title
              state
              url
              repository { nameWithOwner }
            }
          }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldNumberValue {
                number
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldIterationValue {
                title
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
        }
      }
    }
  }
}
"""


def sync_stories(repo: str | None = None, label: str | None = None, include_legacy: bool = False) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    repos = [selected_repo]
    if include_legacy and repo is None:
        repos.extend(item for item in legacy_story_repos() if item not in repos)
    synced_at = now_iso()
    conn = connect()
    init_db(conn)

    counts: dict[str, int] = {}
    for selected in repos:
        counts[selected] = sync_stories_for_repo(conn, selected, label, synced_at)

    conn.execute(
        """
        INSERT INTO sync_state (source, repo, ref, last_synced_at)
        VALUES ('github-stories', ?, '', ?)
        ON CONFLICT(source) DO UPDATE SET
          repo = excluded.repo,
          ref = excluded.ref,
          last_synced_at = excluded.last_synced_at
        """,
        (",".join(repos), synced_at),
    )
    conn.commit()
    return {"repo": selected_repo, "legacyRepos": repos[1:], "label": label, "syncedAt": synced_at, "issueCounts": counts}


def sync_stories_for_repo(conn: sqlite3.Connection, selected_repo: str, label: str | None, synced_at: str) -> int:
    path = f"repos/{selected_repo}/issues?state=all&per_page=100"
    if label:
        path += f"&labels={label}"
    issues = gh_api_paginated(path)
    saved = 0
    for issue in issues:
        if "pull_request" in issue:
            continue
        save_issue(conn, selected_repo, issue, synced_at)
        saved += 1
    return saved


def sync_project(repo: str | None = None, number: int | None = None) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    owner = selected_repo.split("/", 1)[0]
    selected_project = project_number(number)
    synced_at = now_iso()
    conn = connect()
    init_db(conn)

    saved = 0
    cursor: str | None = None
    owner_kind = "organization"
    while True:
        query = project_items_query(owner_kind, cursor)
        variables: dict[str, object] = {"owner": owner, "number": selected_project}
        if cursor:
            variables["cursor"] = cursor
        try:
            payload = gh_graphql(query, variables)
        except RuntimeError as exc:
            if is_project_scope_error(exc):
                return {
                    "repo": selected_repo,
                    "projectNumber": selected_project,
                    "syncedAt": synced_at,
                    "itemCount": saved,
                    "status": "blocked",
                    "reason": "GitHub token is missing read:project scope.",
                    "detail": str(exc),
                }
            if owner_kind == "organization" and cursor is None:
                owner_kind = "user"
                payload = gh_graphql(project_items_query(owner_kind, cursor), variables)
            else:
                raise
        project = (((payload.get("data") or {}).get(owner_kind) or {}).get("projectV2") or {})
        items = (project.get("items") or {})
        for node in items.get("nodes") or []:
            content = node.get("content") or {}
            if content.get("repository", {}).get("nameWithOwner") != selected_repo:
                continue
            issue_number = content.get("number")
            if not isinstance(issue_number, int):
                continue
            fields = project_fields(node.get("fieldValues", {}).get("nodes") or [])
            conn.execute(
                """
                INSERT INTO project_items (
                  repo, project_number, issue_number, item_id, fields_json, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo, project_number, issue_number) DO UPDATE SET
                  item_id = excluded.item_id,
                  fields_json = excluded.fields_json,
                  synced_at = excluded.synced_at
                """,
                (
                    selected_repo,
                    selected_project,
                    issue_number,
                    node.get("id"),
                    json.dumps(fields, ensure_ascii=False),
                    synced_at,
                ),
            )
            saved += 1
        page_info = items.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    conn.execute(
        """
        INSERT INTO sync_state (source, repo, ref, last_synced_at)
        VALUES ('github-project', ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
          repo = excluded.repo,
          ref = excluded.ref,
          last_synced_at = excluded.last_synced_at
        """,
        (selected_repo, str(selected_project), synced_at),
    )
    conn.commit()
    return {
        "repo": selected_repo,
        "projectNumber": selected_project,
        "syncedAt": synced_at,
        "itemCount": saved,
        "status": "synced",
    }


def project_items_query(owner_kind: str, cursor: str | None) -> str:
    return PROJECT_ITEMS_QUERY % (
        ", $cursor: String" if cursor else "",
        owner_kind,
        ", after: $cursor" if cursor else "",
    )


def is_project_scope_error(exc: RuntimeError) -> bool:
    text = str(exc)
    return "read:project" in text or "required scopes" in text and "projectV2" in text


def sync_github(repo: str | None = None, number: int | None = None, include_legacy: bool = False) -> dict[str, Any]:
    stories = sync_stories(repo=repo, include_legacy=include_legacy)
    project = sync_project(repo=repo, number=number)
    return {"stories": stories, "project": project}


def get_story(issue_number: int, repo: str | None = None, number: int | None = None) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    selected_project = project_number(number)
    conn = connect()
    init_db(conn)
    matched_repo, story_row = find_story_row(conn, issue_number, selected_repo, repo is None)
    project_row = None
    if matched_repo:
        project_row = conn.execute(
            "SELECT * FROM project_items WHERE repo = ? AND project_number = ? AND issue_number = ?",
            (matched_repo, selected_project, issue_number),
        ).fetchone()
    return {
        "repo": matched_repo or selected_repo,
        "primaryRepo": selected_repo,
        "legacyFallbackUsed": matched_repo is not None and matched_repo != selected_repo,
        "issueNumber": issue_number,
        "story": decode_story(story_row),
        "project": decode_project(project_row),
    }


def find_cached_stories(query: str, limit: int = 10, repo: str | None = None) -> dict[str, Any]:
    selected_repo = story_repo_name(repo)
    repos = [selected_repo]
    if repo is None:
        repos.extend(item for item in legacy_story_repos() if item not in repos)
    like = f"%{query}%"
    conn = connect()
    init_db(conn)
    rows = conn.execute(
        """
        SELECT * FROM stories
        WHERE repo IN (%s) AND (title LIKE ? OR body LIKE ?)
        ORDER BY updated_at DESC
        LIMIT ?
        """ % ",".join("?" for _ in repos),
        (*repos, like, like, limit),
    ).fetchall()
    return {"repo": selected_repo, "legacyRepos": repos[1:], "stories": [decode_story(row) for row in rows]}


def save_issue(conn: sqlite3.Connection, selected_repo: str, issue: dict[str, Any], synced_at: str) -> None:
    labels = [item.get("name") for item in issue.get("labels", []) if isinstance(item, dict)]
    assignees = [item.get("login") for item in issue.get("assignees", []) if isinstance(item, dict)]
    conn.execute(
        """
        INSERT INTO stories (
          repo, issue_number, title, state, url, labels_json,
          assignees_json, body, updated_at, synced_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo, issue_number) DO UPDATE SET
          title = excluded.title,
          state = excluded.state,
          url = excluded.url,
          labels_json = excluded.labels_json,
          assignees_json = excluded.assignees_json,
          body = excluded.body,
          updated_at = excluded.updated_at,
          synced_at = excluded.synced_at
        """,
        (
            selected_repo,
            issue.get("number"),
            issue.get("title") or "",
            issue.get("state") or "",
            issue.get("html_url"),
            json.dumps(labels, ensure_ascii=False),
            json.dumps(assignees, ensure_ascii=False),
            issue.get("body") or "",
            issue.get("updated_at") or synced_at,
            synced_at,
        ),
    )


def find_story_row(
    conn: sqlite3.Connection,
    issue_number: int,
    primary_repo: str,
    allow_legacy: bool,
) -> tuple[str | None, sqlite3.Row | None]:
    repos = [primary_repo]
    if allow_legacy:
        repos.extend(item for item in legacy_story_repos() if item not in repos)
    for repo in repos:
        row = conn.execute(
            "SELECT * FROM stories WHERE repo = ? AND issue_number = ?",
            (repo, issue_number),
        ).fetchone()
        if row:
            return repo, row
    return None, None


def project_fields(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for node in nodes:
        field = node.get("field") or {}
        name = field.get("name")
        if not name:
            continue
        name = canonical_project_field_name(name)
        if "text" in node:
            fields[name] = node.get("text")
        elif "number" in node:
            fields[name] = node.get("number")
        elif "name" in node:
            fields[name] = node.get("name")
        elif "title" in node:
            fields[name] = node.get("title")
        elif "date" in node:
            fields[name] = node.get("date")
    return fields


def canonical_project_field_name(name: str) -> str:
    canonical = {
        "contract readiness": "Contract Readiness",
        "contract required": "Contract Required",
        "epic": "Epic",
        "implementation target": "Implementation Target",
        "sprint": "Sprint",
        "status": "Status",
        "story point": "Story Point",
    }
    return canonical.get(name.strip().lower(), name)


def decode_story(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["labels"] = json.loads(data.pop("labels_json") or "[]")
    data["assignees"] = json.loads(data.pop("assignees_json") or "[]")
    return data


def decode_project(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["fields"] = json.loads(data.pop("fields_json") or "{}")
    return data
