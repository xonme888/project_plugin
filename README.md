# LoaRing Product Ops Plugin

Codex에서 LoaRing의 product 운영을 돕는 독립 플러그인 프로젝트다.

이 플러그인은 제품 데이터의 원본이 아니다. 원본은 `loaring-product` 저장소이며, 이 플러그인은 Codex가 그 원본을 조회해서 Story, 요구사항, API 계약, 구현 지시서를 다루도록 돕는다.

## 저장소 관계

```txt
loaring-product
  - Story, 요구사항, API 계약, 공통 계약 registry, GitHub Project 운영 기준

loaring-product-ops
  - loaring-product를 조회하고 작업을 보조하는 Codex 플러그인

loaring-backend
  - product의 확정 Story/API 계약을 기준으로 provider 구현

loaring-frontend
  - product의 확정 Story/API 계약을 기준으로 consumer 구현
```

`loaring-product-ops`는 `loaring-product`, `loaring-backend`, `loaring-frontend` 안에 복사하지 않는다. 팀원은 Codex 환경에 플러그인으로 설치해서 사용한다.

## 노출 스킬

| Skill | 책임 |
|------|------|
| `story-intake` | Story 초안, Project 필드 후보, backlog 정리 |
| `requirement-analysis` | 요구사항 분류, 기존 Story/API 중복 확인, API 영향 분석 |
| `api-contract` | API spec 작성/변경, registry 조회, 공통 규칙, breaking change 판단 |
| `implementation-brief` | product 계약을 provider/consumer/QA 작업 지시서로 변환 |

계약 조회, 공통 에러코드, 명명규칙, response envelope, 변경 분류는 별도 스킬로 노출하지 않고 `api-contract` 내부 절차로 처리한다.

## 사용 원칙

- `loaring-product`가 Story, 요구사항, API 계약의 단일 원본이다.
- 구현 저장소는 product 문서를 vendoring하지 않는다.
- Backend와 frontend는 서로의 저장소를 직접 읽거나 수정하지 않는다.
- 구현 중 계약 변경이 필요하면 product Story 또는 product PR에 질문/결정 이력을 남긴다.
- GitHub Issue, PR, Project 변경은 사용자가 명시적으로 승인한 외부 action만 수행한다.
- 팀별 구현 skill은 각 구현 저장소에서 관리한다.

## GitHub 계약 조회

`gh` 인증이 되어 있으면 product repo를 clone하지 않고 계약 파일을 조회할 수 있다.

```bash
python3 scripts/fetch_product_contract.py
python3 scripts/fetch_product_contract.py --path docs/api/212-auth-signup-login.api-spec.json
python3 scripts/fetch_product_contract.py --ref docs/123-auth-contract
```

기본 조회 대상은 `loaring-story/loaring-product@develop`이다.

## 독립성 점검

```bash
python3 scripts/audit_independence.py /path/to/loaring-product /path/to/loaring-backend /path/to/loaring-frontend
```

이 검증은 각 저장소 문서에 monorepo 전제나 상대 경로 결합이 남아 있는지 확인한다.
