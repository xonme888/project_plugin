---
name: story-intake
description: "Create or refine LoaRing product Story issues and backlog entries. Use for Story scope, acceptance criteria, Epic, Sprint, Story Point, assignees, Contract Required, and GitHub Project readiness without creating Task or Epic issues."
---

# Story Intake

GitHub Story Issue is the source of truth for user value, scenarios, acceptance criteria, work scope, QA, and done criteria. Do not create separate Story documents, Task issues, or Epic issues.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- `.github/ISSUE_TEMPLATE/user-story.yml`
- `.github/story-project-schema.json`
- `docs/requirements/user-story-template.v1.yml`
- `docs/requirements/story-map.md`
- `docs/requirements/traceability.yml`

If `loaring-product` is not cloned, fetch files through GitHub or `scripts/fetch_product_contract.py --path <path>`.

## Required Story Data

- Purpose and user value
- As a / I want / So that
- Acceptance criteria for normal and exception flows
- Provider / consumer / QA checklist, with `해당 없음` when a role has no work
- Done criteria
- Open questions or `없음`
- Epic, Story Point, Contract Required, Sprint when known
- GitHub assignees for owner roles

## Workflow

1. Check `story-map.md` and `traceability.yml` for duplicate or related value.
2. Draft with `user-story-template.v1.yml`.
3. If the Story should be created in GitHub, map the draft to `.github/ISSUE_TEMPLATE/user-story.yml`.
4. Use only Project fields: `Epic`, `Status`, `Sprint`, `Story Point`, `Contract Required`.
5. Keep owner assignment in GitHub assignees, not custom Project fields.
6. If API work is needed, hand off to `api-contract`.
7. After a GitHub Issue number exists, update `traceability.yml`.

## External Actions

Do not create Issues, edit Project fields, post comments, or mention people until the user explicitly approves the exact GitHub action.
