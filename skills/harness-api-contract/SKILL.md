---
name: harness-api-contract
description: "Prepare, review, and update LoaRing API contracts linked to a GitHub Story. Use for initial docs/api creation, Backend/Frontend contract questions and decisions, contract PR preparation, review evidence, or implementation-time API contract changes."
---

# API Contract

`docs/api` contains only the final technical contract. Story requirements, contract questions, decisions, PM escalation, review, and approval history live in GitHub.

## Collaboration Records

- Before a contract PR, write unresolved technical questions on the Story Issue with `[계약 질문]`.
- Record the accepted answer with `[계약 결정]` and mention both owners.
- Use PR Review comments for questions tied to an exact contract line.
- Use `[PM 결정 요청] @pm-login` only for product scope, schedule, priority, breaking compatibility, or unresolved pair conflict.
- Set Project `Status=Blocked` and record the reason on the Story Issue when the missing decision prevents both owners from proceeding.
- Codex may detect questions and draft comments, but must not treat separate local Codex conversations as team agreement.
- Codex must stop at a comment draft by default. It must not post an Issue or PR comment, mention a teammate, or mutate Project state until the user explicitly approves the exact external action.

## Initial Contract

1. Read the Story Issue and Project fields.
2. Confirm `Contract Required=Yes` and the relevant Backend/Frontend assignees or reviewers.
3. Check `docs/requirements/traceability.yml` and `docs/api/api-catalog.yml` for existing requirement/API links.
4. Create or update `docs/api/{issue}-{domain}-{feature}.api-spec.json`.
5. Add or update metadata in `docs/api/api-catalog.yml`.
6. Move unresolved questions to the Story Issue or PR Review; do not put them in the API file.
7. Apply only accepted decisions to the API contract.
8. Update `docs/requirements/traceability.yml` when a new Story/API link is created.
9. Open one initial `docs/{issue}-{slug}-contract` PR into `develop`.
10. Require:
   - docs CI success
   - no unresolved review threads
   - `Status` is not `Blocked`
   - counterpart approval when the author is one of the Story assignees
   - both Backend and Frontend approval when the author is outside the assigned pair
11. The author may merge after the gate passes. PM merge is not required for an ordinary contract.
12. Link the PR to the Story with `Related #<issue>`. Do not record PR URLs in Project fields.

## Approval Rule

| Contract PR author | Required approval |
|---|---|
| Backend owner | Frontend owner |
| Frontend owner | Backend owner |
| Anyone else | Backend owner and Frontend owner |

PR submission represents the author's own role agreement. GitHub approval represents the counterpart agreement.

## Reopening a Contract

Classify a missing item before changing files:

| Discovery | Action |
|---|---|
| Implementation or test omission only | Fix in the existing implementation PR |
| Contract omission before implementation branches | Move Project `Status` back to `Todo` if needed and open an amendment contract PR |
| Contract change during implementation | One BE or FE implementation PR owns code, tests, and contract |
| Change blocks both sides or affects shared/multiple Stories | Open an exceptional docs-only contract PR |
| New user value or expanded Story scope | Create a new Story |
| Scope, schedule, priority, or pair conflict | Request a PM decision on the Story Issue |

Before changing an existing contract, check `docs/api/api-catalog.yml` for the target endpoint and use `api-contract-change` classification when the change affects endpoint, request, response, status code, error code, validation, auth, or frontend `uiRules`.

## Changes During Implementation

Use exactly one implementation PR as owner:

| Change | Owner PR | Counterpart review |
|---|---|---|
| Endpoint, request/response, validation, error/status code | Backend PR | Frontend owner |
| Frontend-only `uiRules` without wire change | Frontend PR | Backend owner when relevant |
| Change blocking both sides or shared by several Stories | Exceptional docs-only PR | Both owners |

Do not duplicate the same API file change in BE and FE PRs. Merge the owner PR, then update the other branch from `develop`.

For breaking changes, require a compatibility plan before merge:

- backward-compatible server rollout, or
- coordinated BE/FE merge window, or
- feature flag/versioned endpoint.

## Validation

Reviewers must verify the latest relevant PR, counterpart approvals, unresolved review threads, CI, base branch, blocker state, merge state, and API contract structure. Use `docs/team-operating-model.md`, `.github/pull_request_template.md`, and `docs/api/README.md` as the review checklist.
