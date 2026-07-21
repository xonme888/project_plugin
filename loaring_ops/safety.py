"""Safety hooks for operations that mutate shared external state."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from .config import db_path
from .db import connect, init_db


DEFAULT_MAX_SYNC_AGE_SECONDS = 60 * 60


class SafetyViolation(RuntimeError):
    """Raised when a write operation cannot prove its safety preconditions."""


@contextmanager
def operation_lock(scope: str) -> Iterator[None]:
    """Serialize operations that share an external resource."""
    lock_dir = db_path().parent / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{lock_name(scope)}.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def require_recent_sync(source: str, repo: str, ref: str, max_age_seconds: int | None = None) -> dict[str, str]:
    """Require a recent cache sync before an apply operation."""
    conn = connect()
    init_db(conn)
    row = conn.execute("SELECT * FROM sync_state WHERE source = ?", (source,)).fetchone()
    if row is None:
        raise SafetyViolation(f"{source} cache is missing. Run the matching sync tool before apply=true.")

    data = dict(row)
    if data["repo"] != repo:
        raise SafetyViolation(f"{source} cache repo is {data['repo']}, expected {repo}.")
    if data["ref"] != ref:
        raise SafetyViolation(f"{source} cache ref is {data['ref']}, expected {ref}.")

    synced_at = parse_iso_datetime(data["last_synced_at"])
    age_limit = timedelta(seconds=max_age_seconds or configured_max_sync_age_seconds())
    if datetime.now(synced_at.tzinfo) - synced_at > age_limit:
        raise SafetyViolation(f"{source} cache is stale. Run the matching sync tool before apply=true.")
    return {"source": source, "repo": data["repo"], "ref": data["ref"], "lastSyncedAt": data["last_synced_at"]}


def require_recent_product_sync(repo: str, ref: str) -> dict[str, str]:
    return require_recent_sync("product-docs", repo, ref)


def require_recent_story_sync(repo: str) -> dict[str, str]:
    return require_recent_sync("github-stories", repo, "")


def require_recent_project_sync(repo: str, project_number: int) -> dict[str, str]:
    return require_recent_sync("github-project", repo, str(project_number))


def configured_max_sync_age_seconds() -> int:
    configured = os.environ.get("LOARING_PRODUCT_OPS_MAX_SYNC_AGE_SECONDS")
    if configured:
        return int(configured)
    return DEFAULT_MAX_SYNC_AGE_SECONDS


def parse_iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SafetyViolation(f"Invalid sync timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise SafetyViolation(f"Sync timestamp must include timezone: {value}")
    return parsed


def lock_name(scope: str) -> str:
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:12]
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", scope).strip("-").lower()
    return f"{normalized[:80] or 'operation'}-{digest}"


def db_lock_path(scope: str) -> Path:
    return db_path().parent / "locks" / f"{lock_name(scope)}.lock"
