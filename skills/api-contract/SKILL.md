---
name: api-contract
description: "Prepare, inspect, or change LoaRing product API contracts. Use for API spec creation, contract registry lookup, shared error/naming rules, provider/consumer review, breaking-change classification, and product PR preparation."
---

# API Contract

`loaring-product` owns final API contracts. Implementation repositories consume the contract; they do not vendor product files and do not treat each other as source of truth.

## Source Of Truth

Read from `loaring-story/loaring-product@develop` unless the user gives another repo/ref:

- `docs/contracts/registry.yml`
- `docs/contracts/error-codes.yml`
- `docs/contracts/naming-rules.yml`
- `docs/contracts/response-envelope.yml`
- `docs/api/api-catalog.yml`
- related `docs/api/*.api-spec.json`
- `docs/requirements/traceability.yml`

If `loaring-product` is not cloned, use GitHub, the GitHub connector, or:

```bash
python3 scripts/fetch_product_contract.py
python3 scripts/fetch_product_contract.py --path docs/api/<file>.api-spec.json
```

## Contract Shape

API specs use provider/consumer language:

- endpoint contract: `method`, `path`, `auth`, `request`, `response`, `errors`
- schemas: request/response DTO shape at the wire level
- consumer guidance: `consumerGuidance.schemaNames`, `consumerGuidance.uiRules`
- validation checks: `provider`, `consumer`, `qa`

Do not add implementation repository paths such as `frontend/lib/...` or `backend/...` to product API specs.

## Registry Lookup

Before adding names, fields, envelopes, or errors:

1. Read `registry.yml` to find the active files.
2. Check existing error codes, endpoint naming, field naming, enum naming, pagination, sorting, filtering, auth, and response envelope rules.
3. Reuse an existing rule when semantics match.
4. If a new rule is needed, describe the proposed entry and affected API specs.

## Change Classification

| Discovery | Action |
|---|---|
| Implementation or test omission only | Fix in the implementation PR |
| Contract omission before implementation branches | Open or update a product contract PR |
| Contract change during implementation | One provider or consumer PR owns code/tests and proposes product contract change |
| Change blocks both sides or affects multiple Stories | Use an exceptional product docs-only PR |
| New user value or expanded Story scope | Create a new Story |
| Scope, schedule, priority, breaking compatibility, or owner conflict | Draft `[PM 결정 요청]` |

Change type values are `additive`, `behavioral`, `breaking`, and `unknown`.

## Workflow

1. Locate the Story, requirement IDs, affected endpoints, and existing API specs.
2. Inspect shared contract registry before inventing names or errors.
3. Draft or update `docs/api/{issue}-{domain}-{feature}.api-spec.json` using `template.api-spec.json`.
4. Update `api-catalog.yml` and `traceability.yml` when links change.
5. Move unresolved questions to `[계약 질문]`; record accepted outcomes as `[계약 결정]`.
6. Require counterpart review: provider author needs consumer approval, consumer author needs provider approval, external author needs both.
7. For breaking changes, include a compatibility plan before merge.

## External Actions

Do not post comments, open PRs, edit Project state, or mention owners until the user approves the exact GitHub action.
