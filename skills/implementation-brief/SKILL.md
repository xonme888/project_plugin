---
name: implementation-brief
description: "Create backend or frontend implementation briefs from LoaRing product Story and API contracts without requiring backend and frontend repositories to know each other."
---

# Implementation Brief

이 스킬은 product의 확정 Story와 API 계약을 backend 또는 frontend 작업 지시서로 변환한다. 구현 저장소끼리 직접 대화하거나 서로의 코드를 참조하지 않게 만드는 것이 목적이다.

## Required Context

- GitHub Story Issue
- Project fields: `Epic`, `Status`, `Sprint`, `Story Point`, `Contract Required`
- 관련 `docs/requirements/traceability.yml`
- 관련 `docs/api/*.api-spec.json`
- 대상 역할: `backend`, `frontend`, `qa` 중 하나

## Backend Brief

Backend 지시서에는 다음만 포함한다.

- Story 번호와 사용자 가치
- 승인된 endpoint, request, response, status code, error code, validation
- 필요한 서버 테스트 범위
- 변경 금지 조건
- 계약 질문 또는 PM 결정 요청 초안

Frontend 내부 파일, 컴포넌트, 상태 관리 방식은 포함하지 않는다.

## Frontend Brief

Frontend 지시서에는 다음만 포함한다.

- Story 번호와 사용자 가치
- 승인된 endpoint, request, response, error handling, `uiRules`
- 필요한 화면 상태와 수동 검증 범위
- 변경 금지 조건
- 계약 질문 또는 PM 결정 요청 초안

Backend 내부 패키지, 엔티티, 서비스 구조는 포함하지 않는다.

## Contract Change

구현 중 계약 변경이 필요하면 구현 repo에서 직접 product 문서를 수정했다고 가정하지 않는다.

1. 변경 지점을 endpoint, request, response, status, error, validation, `uiRules`로 분류한다.
2. `api-contract-change`로 변경 유형을 분류한다.
3. product Story 또는 product PR에 남길 `[계약 질문]`, `[계약 결정]`, `[PM 결정 요청]` 초안을 작성한다.
4. 사용자의 명시 승인 전에는 GitHub 댓글, Project 상태, PR을 변경하지 않는다.
