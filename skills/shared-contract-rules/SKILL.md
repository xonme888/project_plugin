---
name: shared-contract-rules
description: "Define and review LoaRing shared API contract rules such as common error codes, naming conventions, response envelopes, validation wording, and cross-team compatibility rules."
---

# Shared Contract Rules

이 스킬은 Backend와 Frontend가 모두 알아야 하는 공통 계약 규칙을 정리한다. 팀별 구현 방식은 각 팀 저장소의 skill과 `AGENTS.md`가 관리하고, 이 스킬은 product 계약의 공통 언어만 다룬다.

공통 규칙의 원본은 `loaring-product`의 `docs/contracts/`다. 구현 저장소에 product clone이 없으면 `contract-registry-lookup`으로 GitHub 원본을 먼저 조회한다.

## Scope

- 공통 error code naming
- response envelope
- ProblemDetail 또는 error response shape
- endpoint, field, enum naming convention
- pagination, sorting, filtering 표현
- validation rule 표현 방식
- auth/permission failure 표현
- compatibility와 breaking change 판단 기준

## Workflow

1. product `docs/api`의 기존 명세와 `api-catalog.yml`을 확인한다.
2. product `docs/contracts/error-codes.yml`, `naming-rules.yml`, `response-envelope.yml`을 확인한다.
3. 같은 의미를 다른 이름이나 error code로 표현하는 중복을 찾는다.
4. Backend 구현 세부 패키지나 Frontend 컴포넌트 구조가 아니라 wire contract 기준으로 정리한다.
5. 변경이 필요한 경우 `api-contract-change`로 additive, behavioral, breaking 여부를 분류한다.
6. 확정 전에는 `[계약 질문]` 또는 `[PM 결정 요청]` 초안만 작성한다.
7. 확정된 규칙만 product API 명세와 `docs/contracts/`에 반영한다.

## Output

- 공통 규칙 이름
- 영향을 받는 API 명세
- Backend 영향
- Frontend 영향
- breaking 여부
- product Story 또는 PR에 남길 질문/결정 초안
