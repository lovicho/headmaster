# ✅ 해마(Headmaster) 실행 및 검증 체크리스트 (Tasks)

> **버전**: v1.0 (2026-06-11)
> **SDD 3-Tier Spec**: Tasks (작업 체크리스트 / Living Document)
> 실행 명령은 모두 `backend/` 디렉터리 기준.

---

## 0. 공통 게이트 (모든 Phase, 모든 커밋)

- [ ] `uv run ruff check .` (린트 통과)
- [ ] `uv run mypy headmaster` (strict 모드 타입 체크 통과)
- [ ] `uv run pytest` (전체 테스트 통과)
- [ ] Python 코드: type hints 필수, `Any` 남용 금지 (TS strict 규칙의 Python 등가)
- [ ] 하드코딩된 시크릿/API 키 금지 — 모델 키는 환경변수만
- [ ] 커밋: Conventional Commits

---

## 1. Phase 0 — 스펙 고정 (완료됨)

코드보다 계약 먼저 (1st 보고서 "정책 우선" 원칙).

- [x] 6대 스키마가 Pydantic v2로 컴파일 (`pytest headmaster/tests/test_schemas.py`)
- [x] **v8 Critic 출력 예시 JSON이 CritiqueReport 스키마를 무수정 통과** (`test_v8_critic_example_validates`)
- [x] 2nd 보고서 TaskSpec 예시가 검증 통과 (`test_task_spec_from_2nd_report`)
- [x] confidence/salience 범위 [0,1] 위반 시 ValidationError (`test_*_bounds`)
- [x] 상태머신: 정상 경로 전이 허용, 비정상 전이 거부 (`test_state_machine.py`)
- [x] v8 하네스 9종 + 오케스트라 1종 YAML이 HarnessManifest 검증 통과 (`test_harness_templates.py`)
- [x] 모든 하네스의 `language_policy.internal == en` (English-Core)
- [x] 대면 에이전트(consultant/planner/content)만 `external == ko`
- [x] 프로젝트 스캐폴드 생성 + pyproject.toml + mypy/ruff/pytest 설정
- [x] mypy strict + ruff 클린

---

## 2. Phase 1 — 코어 MVP (진행 중)

목표: "작업 1건이 게이트를 통과한다."
병렬 트랙 A (실행 경로): ModelGateway + 어댑터 → AgentRuntime → Orchestrator 루프
병렬 트랙 B (제어 경로): TaskCompiler → HarnessRegistry/Compiler → EventStore(SQLite) → CLI

- [x] `headmaster run "<작업>"` 1회로 TaskSpec→하네스→실행→Critic→publish E2E 동작 (수동 + E2E 테스트)
- [x] I-B-F Proof 누락 산출물이 Critic에서 자동 REJECTED (`zero_shot_detected: true`)
- [x] 동일 이벤트 로그에서 상태 replay 100% 일치 (`test_event_replay.py`)
- [x] 어댑터 2종(Anthropic/OpenAI)이 동일 계약 테스트 스위트 통과 — LLM-agnostic 입증 (`test_model_gateway.py`)
- [x] 모델/도구 호출이 전부 이벤트로 기록됨 (누락 0 - replay 테스트로 간접 검증)
- [x] LLM 호출 없는 단위 테스트는 전부 오프라인 실행 가능 (CI에서 키 없이 pytest 통과)

---

## 3. Phase 2 — 도구 + 지식 순환

- [x] MCP Gateway + 도구 allowlist 강제 (policy_engine 연동)
- [x] Memory Fabric: EPI/SEM 구현 (sqlite-vec), quarantine·consolidation 알고리즘
- [x] KnowledgeManager 에이전트: Pre-work supply(Imitate 베이스 공급) + Post-work maintain(자산화)
- [x] Topology Selector: 4레벨 조건부 오케스트레이션 선택 로직
- [x] **검증**: 작업 2건 연속 실행 시 2번째가 1번째 자산을 Imitate 베이스로 재사용 (trace로 확인)
- [x] **검증**: 검증 실패 기록이 quarantine에 격리되고 일반 검색에서 제외됨
- [x] **검증**: allowlist 밖 MCP 도구 호출이 policy_engine에서 거부됨

---

## 4. Phase 3 — 보증 평면 완성

- [x] Policy Engine 고도화 (risk_tier 기반 allow/deny/review)
- [x] Human Approval Gateway (CLI 승인 → API)
- [x] 오케스트라(멀티에이전트) fan-out 실행 연동
- [x] Budget Ledger: soft limit(모델 다운그레이드) / hard limit(중단+승인 요구)
- [x] OTel 트레이싱 + 감사 로그 (who decided / based on what / who approved)
- [x] Eval Runner: golden set 회귀 평가, 핵심 지표 측정 시작
- [x] SKILL 계층 + 승격 자동화 (benchmark gate 통과 시만)
- [x] **검증**: 고위험 작업(`needs_human_approval: true`)이 승인 없이 publish되지 않음
- [x] **검증**: golden set 회귀 시 배포 차단 (Eval Runner)

---

## 5. Phase 4 — 운영 고도화 및 API (Phase 4a)

- [x] React 대시보드 (frontend/): 승인 큐, 실행 상태, 비용/품질 지표
- [x] OpenAPI 외부 노출: `POST /v1/tasks` 제출 → 백그라운드 실행 → `GET /v1/tasks/{id}`로 상태 조회
- [x] 승인 API: 고위험 작업이 `GET /v1/approvals` 큐에 잡히고, HTTP 승인/거부가 실행을 재개/차단함
- [x] 자기개선 루프: trace 분석 → 실패 패턴 → PromptPack/PolicyPatch 제안 → 검증 후 승격
- [x] 확장 어댑터: LangGraph 백엔드 옵션, PostgreSQL 이행, NATS/Temporal 검토
- [x] **검증**: `test_api.py` (ASGI 오프라인) + `headmaster serve` 라이브 스모크
- [x] **UI 프리미엄 업데이트**: 대시보드에 현대적인 Glassmorphism 및 인터랙션 애니메이션 적용

---

## 6. 측정 지표 모니터링 목표

| 지표 | 파일럿 목표 |
|------|------------|
| Task Success Rate | ≥ 70% |
| Evidence Coverage | ≥ 95% |
| Verification Pass Rate | 60~75% |
| Replay Determinism | ≥ 99% |
| Cost per Task | use-case별 상한 설정 |

---

## 7. 🚀 [NEW] Ultra-Review 개선 사항 (To-Do)

이 항목들은 `agtcode-zto`의 Ultra-Review 과정에서 도출된 추가 개선 사항입니다. 적절한 Phase에 포함되어 수행되어야 합니다.

- [x] **SDD 스펙 검증 파이프라인**: `sdd_validator.py` 스크립트를 `backend/scripts` 에 구현하여 `proposal.md`, `design.md`, `tasks.md`의 정합성을 기계적으로 검증하고 pre-commit 훅으로 연동.
- [x] **에러 복구 경계 강화**: `orchestrator.py`의 `ModelGatewayError` 발생 시 `max_recoveries` 한도 초과 시 `AWAITING_HUMAN_APPROVAL` 상태로 전환하여 수동으로 `Resume`을 가능하게 개선.
- [x] **Tasks의 역추적성 확보**: `commit_validator.py`를 구현하고 `.pre-commit-config.yaml`에 `commit-msg` 훅으로 등록하여 커밋 메시지에 태깅(`[task: X]`)을 강제해 Validation 보장.
