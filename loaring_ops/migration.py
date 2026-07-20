"""Read-only migration planning from legacy Story issues into product."""

from __future__ import annotations

import json
import re
from typing import Any

from .config import legacy_story_repos, story_repo_name
from .db import connect, init_db
from .github_sync import sync_stories
from .product_sync import sync_product


def migration_dry_run(
    sync: bool = True,
    include_bodies: bool = False,
    issue_numbers: list[int] | None = None,
) -> dict[str, Any]:
    if sync:
        product_sync = sync_product()
        story_sync = sync_stories(include_legacy=True)
    else:
        product_sync = None
        story_sync = None

    conn = connect()
    init_db(conn)
    primary_repo = story_repo_name()
    legacy_repos = legacy_story_repos()
    primary_rows = conn.execute(
        "SELECT * FROM stories WHERE repo = ?",
        (primary_repo,),
    ).fetchall()
    legacy_rows = conn.execute(
        "SELECT * FROM stories WHERE repo IN (%s) ORDER BY issue_number"
        % ",".join("?" for _ in legacy_repos),
        tuple(legacy_repos),
    ).fetchall()

    primary_stories = [decode_story_row(row) for row in primary_rows]
    selected_issue_numbers = set(issue_numbers or [])
    legacy_stories = [
        decode_story_row(row)
        for row in legacy_rows
        if not selected_issue_numbers or int(row["issue_number"]) in selected_issue_numbers
    ]
    traceability = load_traceability()
    catalog = load_catalog()

    items = []
    for legacy in legacy_stories:
        matches = find_matches(legacy, primary_stories)
        linked_requirements = [
            req for req in traceability if legacy["issueNumber"] in req.get("storyIssues", [])
        ]
        linked_specs = [
            spec for spec in catalog if spec.get("storyIssue") == legacy["issueNumber"]
        ]
        action = "already-migrated" if matches else "create-in-product"
        item = {
            "legacyRepo": legacy["repo"],
            "legacyIssue": legacy["issueNumber"],
            "title": legacy["title"],
            "state": legacy["state"],
            "labels": legacy["labels"],
            "assignees": legacy["assignees"],
            "action": action,
            "candidateProductMatches": matches,
            "linkedRequirements": [
                {
                    "id": req.get("requirementId"),
                    "title": req.get("title"),
                    "apiSpecs": req.get("apiSpecs", []),
                }
                for req in linked_requirements
            ],
            "linkedApiSpecs": [
                {
                    "path": spec.get("path"),
                    "title": spec.get("title"),
                    "endpoints": spec.get("endpoints", []),
                }
                for spec in linked_specs
            ],
        }
        if include_bodies:
            item["body"] = legacy["body"]
        items.append(item)

    return {
        "primaryRepo": primary_repo,
        "legacyRepos": legacy_repos,
        "productSync": product_sync,
        "storySync": story_sync,
        "summary": {
            "primaryStoryCount": len(primary_stories),
            "legacyStoryCount": len(legacy_stories),
            "selectedIssues": sorted(selected_issue_numbers),
            "createInProduct": sum(1 for item in items if item["action"] == "create-in-product"),
            "alreadyMigrated": sum(1 for item in items if item["action"] == "already-migrated"),
        },
        "items": items,
    }


def find_matches(legacy: dict[str, Any], primary_stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    legacy_title = normalize_title(legacy["title"])
    legacy_key_terms = title_terms(legacy_title)
    matches = []
    for story in primary_stories:
        title = normalize_title(story["title"])
        score = 0
        if title == legacy_title:
            score = 100
        elif legacy_title and (legacy_title in title or title in legacy_title):
            score = 80
        else:
            overlap = legacy_key_terms & title_terms(title)
            if legacy_key_terms:
                score = int(len(overlap) / len(legacy_key_terms) * 60)
        if score >= 40:
            matches.append(
                {
                    "repo": story["repo"],
                    "issueNumber": story["issueNumber"],
                    "title": story["title"],
                    "state": story["state"],
                    "url": story["url"],
                    "matchScore": score,
                }
            )
    return sorted(matches, key=lambda item: item["matchScore"], reverse=True)


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"^\s*\[story\]\s*", "", title, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def title_terms(title: str) -> set[str]:
    return {term for term in re.split(r"[\s/_-]+", title) if len(term) >= 2}


def load_traceability() -> list[dict[str, Any]]:
    conn = connect()
    init_db(conn)
    rows = conn.execute("SELECT * FROM requirements ORDER BY requirement_id").fetchall()
    result = []
    for row in rows:
        data = dict(row)
        result.append(
            {
                "requirementId": data["requirement_id"],
                "title": data["title"],
                "status": data["status"],
                "epic": data["epic"],
                "storyIssues": json.loads(data["story_issues_json"] or "[]"),
                "apiSpecs": json.loads(data["api_specs_json"] or "[]"),
            }
        )
    return result


def load_catalog() -> list[dict[str, Any]]:
    conn = connect()
    init_db(conn)
    rows = conn.execute("SELECT * FROM api_specs ORDER BY path").fetchall()
    result = []
    for row in rows:
        data = dict(row)
        result.append(
            {
                "path": data["path"],
                "domain": data["domain"],
                "title": data["title"],
                "storyIssue": data["story_issue"],
                "requirementIds": json.loads(data["requirement_ids_json"] or "[]"),
                "endpoints": json.loads(data["endpoints_json"] or "[]"),
                "lifecycle": data["lifecycle"],
            }
        )
    return result


def decode_story_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "repo": data["repo"],
        "issueNumber": data["issue_number"],
        "title": data["title"],
        "state": data["state"],
        "url": data["url"],
        "labels": json.loads(data["labels_json"] or "[]"),
        "assignees": json.loads(data["assignees_json"] or "[]"),
        "body": data["body"] or "",
        "updatedAt": data["updated_at"],
    }
