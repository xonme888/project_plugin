# LoaRing Product Ops Plugin

Codex에서 LoaRing의 product 운영을 돕는 독립 플러그인 프로젝트다.

이 플러그인은 `loaring-product`, `loaring-backend`, `loaring-frontend` 저장소 안에 복사하지 않는다. 팀원이 Codex 환경에 설치해서 사용하고, 각 저장소는 자기 `AGENTS.md`, GitHub 문서, 팀별 `.agents/skills/`를 버전 관리한다.

## 책임

| 영역 | 책임 |
|------|------|
| Story intake | 사용자 가치를 GitHub Story 초안과 Project 필드 후보로 정리 |
| Requirement analysis | 기존 Story/API와의 중복, 충돌, 미결정 질문 분석 |
| API contract | 확정 계약 작성, 변경 분류, breaking change 판단 |
| Contract registry lookup | GitHub의 product repo에서 API 명세와 registry 조회 |
| Shared contract rules | 공통 에러코드, API 명명규칙, response envelope, validation 표현 기준 정리 |
| Project gate | GitHub Issue, PR, Project 필드의 준비 상태를 읽기 전용으로 점검 |

## 저장소 관계

```txt
loaring-product
  - Story, 요구사항, API 계약, GitHub Project 운영의 원본

loaring-backend
  - product의 확정 Story/API 계약을 기준으로 서버 구현
  - frontend 저장소를 직접 참조하지 않음
  - backend 팀 전용 skill은 backend repo에서 관리

loaring-frontend
  - product의 확정 Story/API 계약을 기준으로 화면과 API client 구현
  - backend 저장소의 내부 코드를 직접 참조하지 않음
  - frontend 팀 전용 skill은 frontend repo에서 관리

loaring-product-ops
  - 위 흐름을 Codex에서 보조하는 플러그인
  - 제품 데이터의 원본이 아님
  - 팀 공통 Story/API/GitHub Project/계약 규칙만 제공
```

## 사용 원칙

- product repo가 Story, 요구사항, API 계약의 단일 원본이다.
- backend/frontend 개발자는 product repo를 clone하지 않아도 GitHub 조회로 계약을 확인할 수 있어야 한다.
- backend와 frontend는 서로의 저장소를 직접 읽거나 수정하지 않는다.
- backend/frontend 작업 중 계약 변경이 필요하면 product Story 또는 product PR에 변경 요청을 남긴다.
- backend/frontend 팀 고유의 개발 skill은 각 팀 저장소에서 관리한다.
- 플러그인은 GitHub Issue, PR, Project 변경을 자동 수행하지 않는다. 사용자가 명시적으로 승인한 외부 action만 실행한다.
- product repo의 문서와 GitHub 상태가 충돌하면 GitHub Story Issue와 Project 필드를 우선 확인한다.

## 설치 위치

권장 위치:

```txt
~/plugins/loaring-product-ops
```

팀 공용으로 버전 관리하려면 이 디렉터리를 별도 Git 저장소 `loaring-product-ops`로 관리한다. `loaring-product`, `loaring-backend`, `loaring-frontend` 안에 vendoring하지 않는다.

## 로컬 검증

```bash
python3 scripts/audit_independence.py /path/to/loaring-product /path/to/loaring-backend /path/to/loaring-frontend
```

이 검증은 각 저장소 문서에 monorepo 전제나 상대 경로 결합이 남아 있는지 확인한다.

## GitHub 계약 조회

`gh` 인증이 되어 있으면 product repo를 clone하지 않고 계약 파일을 조회할 수 있다.

```bash
python3 scripts/fetch_product_contract.py
python3 scripts/fetch_product_contract.py --path docs/api/212-auth-signup-login.api-spec.json
```

기본 조회 대상은 `loaring-story/loaring-product@develop`이다.
