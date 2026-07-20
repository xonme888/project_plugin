"""Configuration for LoaRing Product Ops."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_PRODUCT_REPO = "loaring-story/loaring-product"
DEFAULT_STORY_REPO = DEFAULT_PRODUCT_REPO
DEFAULT_LEGACY_STORY_REPOS = ["loaring-story/loaring-sotry"]
DEFAULT_REF = "develop"
DEFAULT_PROJECT_NUMBER = 2
DEFAULT_DATA_DIR = Path.home() / ".codex" / "loaring-product-ops"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "loaring-product-ops.sqlite"


PRODUCT_PATHS = [
    "docs/contracts/registry.yml",
    "docs/contracts/error-codes.yml",
    "docs/contracts/naming-rules.yml",
    "docs/contracts/response-envelope.yml",
    "docs/requirements/story-map.md",
    "docs/requirements/traceability.yml",
    "docs/api/api-catalog.yml",
]


def db_path() -> Path:
    configured = os.environ.get("LOARING_PRODUCT_OPS_DB")
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_DB_PATH


def repo_name(repo: str | None = None) -> str:
    return product_repo_name(repo)


def product_repo_name(repo: str | None = None) -> str:
    return repo or os.environ.get("LOARING_PRODUCT_REPO") or DEFAULT_PRODUCT_REPO


def story_repo_name(repo: str | None = None) -> str:
    return repo or os.environ.get("LOARING_STORY_REPO") or DEFAULT_STORY_REPO


def legacy_story_repos() -> list[str]:
    configured = os.environ.get("LOARING_LEGACY_STORY_REPOS")
    if configured is None:
        return list(DEFAULT_LEGACY_STORY_REPOS)
    return [repo.strip() for repo in configured.split(",") if repo.strip()]


def repo_ref(ref: str | None = None) -> str:
    return ref or os.environ.get("LOARING_PRODUCT_REF") or DEFAULT_REF


def project_number(number: int | None = None) -> int:
    if number is not None:
        return number
    configured = os.environ.get("LOARING_PRODUCT_PROJECT_NUMBER")
    if configured:
        return int(configured)
    return DEFAULT_PROJECT_NUMBER
