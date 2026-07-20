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

## MCP와 로컬 캐시

패키징된 플러그인은 MCP 서버를 통해 `loaring-product` 조회를 캡슐화한다. Backend나 frontend 저장소에서 플러그인을 실행하는 사용자는 product 저장소 구조를 직접 알 필요 없이 Story/API 계약 메타데이터를 조회할 수 있다.

로컬 sqlite 캐시는 기본적으로 `~/.codex/loaring-product-ops/loaring-product-ops.sqlite`에 저장한다. 이 캐시는 조회 성능, 검색, readiness 점검을 위한 보조 데이터이며 Story/API 계약의 원본이 아니다. 승인된 Story, API spec, registry, Project 결정의 source of truth는 계속 `loaring-product`다.

현재 MCP 도구는 read-only 동기화 범위다.

- `loaring_sync_product`: product docs를 sqlite에 동기화
- `loaring_find_story`: 요구사항, Story map, API catalog 캐시 검색
- `loaring_get_contract`: Story 또는 requirement에 연결된 API 계약 메타데이터 조회
- `loaring_validate_contract_readiness`: backend/frontend 구현 착수 가능한 API 계약 준비 상태 점검
- `loaring_infer_project_fields`: Story/API 문서 기준으로 `Contract Required`, `Contract Readiness`, `Implementation Target` 권장값 계산
- `loaring_sync_stories`: GitHub Story Issue를 sqlite에 동기화
- `loaring_sync_project`: GitHub Project 필드값을 sqlite에 동기화
- `loaring_sync_github`: Story Issue와 Project 필드값을 함께 동기화
- `loaring_get_story`: Story Issue와 Project 필드값 조회
- `loaring_find_cached_stories`: 캐시된 Story Issue 제목/본문 검색
- `loaring_migration_dry_run`: legacy Story Issue를 `loaring-product`로 옮기기 전 read-only 마이그레이션 계획 생성
- `loaring_plan_story_work`: Story의 Status, 계약 상태, target을 기준으로 다음 액션과 브랜치 후보 계산
- `loaring_prepare_branch`: Story 번호와 target으로 표준 브랜치명과 git 명령 생성
- `loaring_validate_workflow`: Project Story들의 필드 누락, 계약 상태 불일치, Status 리스크 점검

GitHub 동기화는 read-only다. Issue comment 작성, PR 생성, Project 필드 수정은 다음 단계의 승인 기반 write action으로 분리한다.

GitHub Project v2 필드 조회에는 `gh` 토큰의 `read:project` scope가 필요하다. 해당 scope가 없으면 Project 동기화는 실패로 중단하지 않고 `blocked` 상태와 필요한 scope를 반환한다.

Story Issue는 마이그레이션 중에도 기본적으로 `loaring-story/loaring-product`를 조회한다. 과거 Story가 `loaring-story/loaring-sotry`에 남아 있는 경우 `--include-legacy` 또는 MCP `includeLegacy: true`로 legacy repo를 read-only 보강 조회할 수 있다. 새 Story, 새 계약, Project 운영의 기준은 `loaring-product`다.

## Workflow 도구

표준 브랜치 규칙:

- Product/API 계약: `docs/{story-id}-{slug}-contract`
- Backend: `be/{story-id}-{slug}`
- Frontend: `fe/{story-id}-{slug}`
- Fix: `fix/{issue-id}-{slug}`
- 일반 문서/운영: `docs/{slug}` 또는 `chore/{slug}`

`loaring_plan_story_work`는 캐시된 Story, Project 필드, API 계약 연결을 함께 읽어 다음 액션을 계산한다. API 계약이 `Missing`인 Story는 backend/frontend 구현 시작 전 `api-contract`로 넘기고, `Backend Ready`인 Story는 backend 브랜치만, `Frontend Ready`인 Story는 frontend 브랜치만, `Ready`인 Story는 양쪽 브랜치 후보를 반환한다.

`loaring_validate_workflow`는 Sprint 단위 점검에 사용한다. 예를 들어 `sprint: "sprint 3"`으로 호출하면 해당 Sprint Story만 대상으로 필수 Project 필드, MCP 추론값과 실제 필드값 불일치, 계약 없이 구현 상태로 넘어간 Story를 점검한다.

Contract Readiness 값:

- `Not Required`: API 계약이 필요 없는 Story
- `Missing`: API 계약이 필요하지만 연결된 full api-spec이 없음
- `Draft`: 계약 초안은 있으나 backend/frontend 구현 착수 기준이 아직 부족함
- `Backend Ready`: API provider인 backend가 구현 시작 가능한 상태
- `Frontend Ready`: API consumer인 frontend가 구현 시작 가능한 상태
- `Ready`: backend와 frontend 모두 구현 시작 가능한 상태
- `Blocked`: 권한, 응답, 에러, API 분리 등 계약 결정이 막힌 상태

마이그레이션 전에는 먼저 드라이런 리포트를 만든다.

```bash
python3 scripts/migration_dry_run.py
```

이 스크립트는 product docs와 legacy Issue를 조회하지만 GitHub에는 쓰지 않는다. 실제 Issue 생성, Project 필드 복원, `traceability.yml`/`api-catalog.yml` 갱신은 별도 승인 기반 단계로 진행한다.

드라이런 리포트에서 `create-in-product`는 아직 product repo에서 매칭되는 Story Issue를 찾지 못했다는 뜻이다. `linkedRequirements`와 `linkedApiSpecs`가 있는 항목은 product 문서가 이미 legacy Issue 번호를 참조하고 있으므로, 실제 마이그레이션 후 새 product Issue 번호로 연결 파일을 갱신해야 한다.

## 독립성 점검

```bash
python3 scripts/audit_independence.py /path/to/loaring-product /path/to/loaring-backend /path/to/loaring-frontend
```

이 검증은 각 저장소 문서에 monorepo 전제나 상대 경로 결합이 남아 있는지 확인한다.
