---
name: contract-registry-lookup
description: "Fetch and inspect LoaRing product API contracts and shared contract registry from GitHub without requiring backend or frontend developers to clone loaring-product."
---

# Contract Registry Lookup

이 스킬은 Backend 또는 Frontend 개발자가 자기 구현 저장소만 clone한 상태에서 product 계약을 조회할 때 사용한다.

## Source Of Truth

- GitHub repo: `loaring-story/loaring-product`
- 기본 ref: `develop`
- 확정 계약:
  - `docs/api/api-catalog.yml`
  - `docs/api/*.api-spec.json`
  - `docs/contracts/*.yml`
- 검토 중 계약:
  - product repo의 PR diff
  - Story Issue의 `[계약 질문]`, `[계약 결정]`

## Local Clone Rule

Backend/Frontend 개발자에게 `loaring-product` clone을 요구하지 않는다. 조회는 GitHub API, GitHub connector, 또는 `gh` CLI로 수행한다.

## Script

기본 registry와 API catalog 조회:

```bash
python3 scripts/fetch_product_contract.py
```

특정 API 명세 조회:

```bash
python3 scripts/fetch_product_contract.py --path docs/api/212-auth-signup-login.api-spec.json
```

검토 중인 branch 또는 tag 조회:

```bash
python3 scripts/fetch_product_contract.py --ref docs/123-auth-contract
```

## Workflow

1. Story Issue 번호 또는 API domain/feature를 확인한다.
2. `docs/api/api-catalog.yml`을 조회해 관련 API spec 경로를 찾는다.
3. `docs/contracts/error-codes.yml`, `naming-rules.yml`, `response-envelope.yml`을 조회한다.
4. 기존 error code, endpoint naming, field naming, envelope 규칙으로 표현 가능한지 판단한다.
5. 기존 규칙이 있으면 재사용을 제안한다.
6. 새 규칙이 필요하면 `shared-contract-rules`와 `api-contract-change`로 변경 유형을 분류한다.
7. 확정 전에는 product Story 또는 product PR에 남길 초안만 작성한다.

## Output

- 조회한 product ref
- 관련 API spec
- 재사용 가능한 registry 항목
- 새로 필요한 registry 항목 후보
- Backend 영향
- Frontend 영향
- product Story/PR에 남길 `[계약 질문]` 또는 `[계약 결정]` 초안
