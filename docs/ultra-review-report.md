# 🔍 해마(Headmaster) Ultra-Review 보고서

> **리뷰 일자**: 2026-06-13
> **리뷰 대상**: Headmaster 오케스트레이션 컨트롤 플레인 시스템 (v1.0 초기 구조)
> **기준 프레임워크**: agtcode-zto PVE / SDD (Spec Driven Development) 표준 설계

## 1. 아키텍처 및 구현 강점 (Strengths)

코드베이스(특히 `execution_plane/orchestrator.py` 및 `schemas` 등)를 심층 분석한 결과, 시스템의 뼈대가 현대적인 AI 에이전트 시스템의 요구사항을 고수준으로 충족하고 있습니다.

### 1.1 견고한 PVE(Plan-Verify-Execute) 상태머신 구현
- 작업의 시작부터 종료까지 **명시적인 상태 전이(TaskState)**를 강제하며, 상태 전이의 검증을 거칩니다.
- 단일 에이전트 루프와 다중 에이전트(Fan-out) 루프 모두 `CRITIQUING` 단계를 거쳐 `REPLANNING` 혹은 `VALIDATED`로 이어지는 제어 흐름이 매우 견고합니다.

### 1.2 이벤트 소싱(Event Sourcing) 기반 재현성
- 모델 응답, 도구 호출, 상태 변경 등 모든 이벤트를 `EventStore`에 기록함으로써 상태를 완벽히 Replay할 수 있도록 구현되었습니다.
- 이는 LLM의 비결정성(Non-determinism)을 제어하고 감사 추적(Audit Trail)을 완벽히 지원하는 엔터프라이즈급 설계입니다.

### 1.3 LLM-Agnostic(모델 독립적) 어댑터 패턴
- 하네스는 비용 티어(`cost_tier`)만을 선언하고, 실제 모델 매핑은 `config/models.yaml`에서 `ModelGateway`를 통해 추상화되어 있습니다.
- 특정 프롬프트 벤더나 API 호출 라이브러리(LiteLLM 등)에 직접 종속되지 않아 시스템의 영속성과 주권(Sovereignty)을 확보했습니다.

### 1.4 No Zero-Shot 발명 원칙의 기계적 통제
- Pydantic 스키마인 `EvidenceBundle`과 `IBFProof`를 통해 산출물이 단순히 LLM의 상상으로 생성된 것이 아님(Imitate-Benchmark-Fusion)을 스키마 레벨에서 강제하고 있습니다.

---

## 2. Ultra-Review 주요 개선 제안 (Action Items)

현재의 훌륭한 설계를 바탕으로, **SDD 표준의 기계적 검증**과 **오류 복원력(Resilience)**을 극대화하기 위해 다음 세 가지 항목을 제안합니다. (현재 `plan/tasks.md`의 [NEW] Ultra-Review 개선 사항으로 등록됨)

### 2.1 SDD 스펙 정합성 검증 파이프라인 도입
- **현상**: SDD의 3-Tier Spec(`proposal.md`, `design.md`, `tasks.md`) 구조를 채택했으나, 이 파일들의 구조와 동기화 상태가 오직 문서로만 관리됩니다.
- **개선안**: `zto-spec-validator.js` 혹은 파이썬 버전의 `sdd_validator.py`를 `backend/scripts/`에 추가.
  - 마크다운 AST 파싱 등을 통해 각 파일의 필수 섹션 존재 여부 및 동기화를 검증.
  - CI 파이프라인의 pre-commit 훅으로 연동하여 "계약(Contract)" 파손을 미연에 방지.

### 2.2 Orchestrator 에러 복구 경계 강화 (Resume API)
- **현상**: `orchestrator.py` 내부에서 `ModelGatewayError` 발생 시 일시적인 `RECOVERING` 모드로 진입하며, `max_recoveries` 초과 시 작업을 `FAILED` 처리합니다.
- **개선안**: `FAILED` 처리 이후 사용자가 근본 원인(예: API 키 만료, 일시적 네트워크 장애)을 해결한 뒤, 해당 지점부터 수동으로 재개(Resume)할 수 있는 API 엔드포인트나 CLI 커맨드 `/resume` 등을 도입해야 합니다. 이벤트 소싱을 채택했으므로 상태의 리플레이 후 멈춘 지점부터 즉시 재개 가능합니다.

### 2.3 Tasks (체크리스트) 역추적성 확보
- **현상**: `plan/tasks.md` 파일이 단순히 마크다운 체크박스로 관리되며, 완료 여부를 사람이 직접 기입해야 합니다.
- **개선안**: 
  - 커밋 메시지에 `[task: 4.1]` 형태의 태그를 포함하도록 강제하거나, GitHub Actions 등에서 `tasks.md`의 해소 비율을 자동으로 측정해 대시보드 리포팅으로 보내는 역추적 로직이 필요합니다.
  - 오케스트레이터의 에이전트들이 스스로 코드 구현 후 `tasks.md`의 체크박스를 `[x]`로 갱신하게 만드는 "Self-updating Task" 루프 구현 고려.

---

## 3. 총평

Headmaster 프로젝트는 기존의 단순 프롬프트 체이닝 수준의 에이전트를 넘어, 명시적 컨트랙트와 감사(Audit), 그리고 이벤트 소싱을 통해 "통제 가능하고 예측 가능한 에이전트 시스템"을 만들고자 하는 SDD/PVE의 철학을 거의 완벽에 가깝게 코드로 풀어냈습니다. 

위에서 제안된 추가 개선 사항들만 시스템에 편입된다면, 단일 개발자 환경뿐만 아니라 다중 에이전트가 협업하는 엔터프라이즈 환경에서도 곧바로 사용 가능한 세계적 수준의 프레임워크로 완성될 것입니다.
