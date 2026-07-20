---
name: harness-story-api-workflow
description: "Route LoaRing Story workflow requests to the current 4-person operating model, API contract skill, delivery checklist, or read-only quality gate."
---

# Story Workflow Router

Use this router only to choose the current Story workflow entry point. The source of truth is the GitHub Story Issue plus the Project fields defined in `.github/story-project-schema.json`.

Route by intent:

| Request | Skill |
|---|---|
| Create/refine Story, assign pair, Sprint planning | `harness-story-intake` and `.github/ISSUE_TEMPLATE/user-story.yml` |
| Create/review/change API contract | `harness-api-contract` |
| Create Story-linked docs/BE/FE branches, PR coordination, QA handoff | `harness-story-delivery` and PR template |
| Check Project fields, PRs, CI, QA, Done | `quality-story-gate` in read-only mode |

For mixed requests, use the skills in lifecycle order. Story requirements live in the GitHub Issue. Do not create separate Story documents.
