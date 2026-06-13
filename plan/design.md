# 📐 해마(Headmaster) 시스템 설계 및 스키마 명세 (Design)

> **버전**: v1.0 (2026-06-11)
> **SDD 3-Tier Spec**: Design (아키텍처/API/스키마)
> **정본(canonical)**: `backend/headmaster/schemas/`의 Pydantic v2 모델. 본 문서는 설계 의도와 필드 의미를 기록한다.

---

## 1. 🏗️ 아키텍처 결정

### 1.1 3평면 구조

```
┌─────────────────────────────────────────────────────────┐
│ 제어 평면 (Control Plane) ← "해마 본체"                    │
│  Task Compiler · Harness Registry · Policy Engine        │
│  Topology Selector · Scheduler · Budget Ledger           │
├─────────────────────────────────────────────────────────┤
│ 실행 평면 (Execution Plane)                               │
│  Orchestrator Runtime · Agent Runtime (역할별 에이전트)    │
│  Model Gateway (LLM 어댑터) · Tool Gateway (MCP)          │
│  Memory Fabric (STM/EPI/SEM/SKILL/EVID)                  │
├─────────────────────────────────────────────────────────┤
│ 보증 평면 (Assurance Plane)                               │
│  Critic Service · Human Approval Gateway · Guardrails    │
│  Tracing (OTel) · Audit Log · Eval Runner                │
└─────────────────────────────────────────────────────────┘
```

### 1.2 LLM-agnostic 전략

- **ModelGateway 인터페이스** 하나로 통일: `complete(request: ModelRequest) -> ModelResponse`
  - 어댑터: `anthropic_adapter`, `openai_adapter`, `gemini_adapter`, `local_adapter`(Ollama)
  - tool-calling 형식 차이, reasoning 모델 차이를 어댑터 내부에서 정규화
  - 내부 구현에서 LiteLLM 활용 가능하되, 인터페이스는 자체 소유 (종속 방지)
- **모델 선택은 정책**: `config/models.yaml`에서 cost_tier(mini/standard/heavy)별 라우팅. 하네스는 tier만 지정, 실제 모델명은 모름
- **하네스 = 모델 무관 계약**: 역할, 입출력 JSON Schema, 도구 allowlist, 금지행위, 언어정책

### 1.3 조건부 오케스트레이션

"항상 멀티에이전트"가 아니라 Topology Selector가 작업 특성에 따라 4레벨 중 선택:

1. `single-hop` — 단순 응답
2. `single-agent-with-tools` — 도구 사용 단일 에이전트
3. `multi-agent-supervised` — 오케스트레이터-워커 (병렬 fan-out)
4. `multi-agent-with-HITL` — 고위험: 인간 승인 게이트 포함

### 1.4 핵심 루프

```
compile_task_spec → load_policy → compile_harness
  → [루프] plan → execute(I-B-F 강제) → critique
      → 반려 시: replan / repair (수리 루프)
      → 고위험: await_human_approval
      → 통과 시: publish → assimilate(지식 자본화) → 종료
```

상태머신: `Registered → Classified → Planned → Executing → (AwaitingTool | AwaitingHumanApproval) → Critiquing → (Replanning | Validated) → Publishing → Assimilating → Completed` (+ `Recovering`, `Failed`)

### 1.5 메모리 (5계층)

| 계층 | 내용 | MVP 도입 시기 |
|------|------|--------------|
| STM | 현재 task graph + 최근 메시지 | Phase 1 (in-memory) |
| EVID | 증거·인용·검증 결과 (불변) | Phase 1 (필수 — I-B-F Proof 저장소) |
| EPI | 에피소드 (전략→결과, 실패 원인) | Phase 2 |
| SEM | 검증된 사실, 도메인 지식 | Phase 2 (pgvector/sqlite-vec) |
| SKILL | SOP, 프롬프트팩, 코드 패턴 | Phase 3 (test_pass_rate ≥ 0.9 시만 승격) |

---

## 2. 📁 파일 및 디렉터리 구조

```
해마프로젝트/
├── plan/                                # SDD 3-Tier Spec 문서
│   ├── proposal.md                      # [배경/범위/기준]
│   ├── design.md                        # (이 문서) [아키텍처/API]
│   └── tasks.md                         # [작업 체크리스트]
├── backend/
│   └── headmaster/
│       ├── control_plane/
│       │   ├── task_compiler.py         # 자연어 → TaskSpec
│       │   ├── topology_selector.py     # 4레벨 오케스트레이션 선택
│       │   ├── harness_registry.py      # 하네스 템플릿 로드/버전관리
│       │   ├── harness_compiler.py      # manifest → 실행 가능 하네스
│       │   ├── policy_engine.py         # allow/deny/review 판정
│       │   └── budget_ledger.py         # 토큰/비용/호출 예산 추적
│       ├── execution_plane/
│       │   ├── orchestrator.py          # 핵심 루프 + 상태머신
│       │   ├── agent_runtime.py         # 하네스 주입된 에이전트 실행기
│       │   ├── models/                  # ★ LLM-agnostic 어댑터
│       │   │   ├── gateway.py           # ModelGateway 인터페이스
│       │   │   ├── anthropic_adapter.py
│       │   │   ├── openai_adapter.py
│       │   │   ├── gemini_adapter.py
│       │   │   └── local_adapter.py     # Ollama 등
│       │   ├── tools/
│       │   │   └── mcp_gateway.py       # MCP 클라이언트 + allowlist 강제
│       │   └── memory/
│       │       ├── fabric.py            # 5계층 통합 인터페이스
│       │       ├── episodic.py
│       │       ├── semantic.py
│       │       ├── skill_store.py
│       │       └── evidence_store.py    # 불변 EVID 저장소
│       ├── assurance_plane/
│       │   ├── critic_service.py        # I-B-F Proof 기계 검증 + CritiqueReport
│       │   ├── approval_gateway.py      # HITL 승인 대기/재개
│       │   ├── tracer.py                # OTel 설정
│       │   └── evaluator.py             # golden set 회귀 평가
│       ├── storage/
│       │   ├── event_store.py           # ★ 이벤트 소싱 (source of truth)
│       │   └── task_store.py
│       ├── schemas/                     # Pydantic 모델 (= JSON Schema 원본)
│       │   ├── task_spec.py
│       │   ├── agent_manifest.py
│       │   ├── harness_manifest.py
│       │   ├── evidence_bundle.py       # I-B-F Proof 포함
│       │   ├── critique_report.py
│       │   └── memory_record.py
│       ├── templates/
│       │   ├── harnesses/               # 하네스 매니페스트
│       │   └── policies/                # 정책 파일
│       ├── config/
│       │   ├── settings.yaml
│       │   └── models.yaml              # cost_tier → 모델 라우팅 정책
│       ├── api/
│       │   └── main.py                  # FastAPI (2nd 보고서 API 명세 기반)
│       ├── cli.py                       # headmaster run "작업내용"
│       └── tests/
│           ├── test_schemas.py
│           ├── test_task_compiler.py
│           ├── test_orchestrator.py
│           ├── test_critic_service.py   # zero-shot 탐지 테스트 포함
│           ├── test_model_gateway.py    # 어댑터별 정규화 검증
│           ├── test_event_replay.py     # replay 결정성
│           └── golden/                  # 회귀 평가용 golden set
└── frontend/                            # Phase 4: 승인/관측 대시보드 (React)
```

---

## 3. 스키마 명세 (6대 스키마)

### 3.1 TaskSpec

자연어 요청 → Task Compiler가 생성하는 정규화 명세.

| 필드 | 타입 | 설명 |
|------|------|------|
| `task_id` | str (`tsk_` 접두) | 고유 ID. MVP는 uuid4 hex, 추후 UUIDv7 전환(3rd 권장) |
| `title`, `intent` | str | 제목 / 목표 서술 |
| `constraints.language` | `ko`\|`en` | 대면 출력 언어 (기본 ko — Korean-Edge) |
| `constraints.deadline` | datetime? | 기한 |
| `constraints.budget` | Budget | `max_model_cost_usd`, `max_tool_calls`, `max_tokens` |
| `constraints.quality_criteria` | list[str] | 품질 기준 |
| `risk_profile.data_sensitivity` | `public`\|`internal`\|`confidential` | 데이터 민감도 |
| `risk_profile.action_risk` | `low`\|`medium`\|`high` | 행위 위험 |
| `risk_profile.needs_human_approval` | bool | HITL 게이트 필요 여부 |
| `inputs[]` | {type, ref, trust} | 입력 자료 (file/url/text, 신뢰 출처 표기) |
| `success_criteria[]` | list[str] | 성공 판정 기준 |
| `required_evidence[]` | list[str] | 요구 증거 수준 |
| `policy_checks[]` | list[str] | 적용할 정책 체크 ID |

### 3.2 AgentManifest

| 필드 | 타입 | 설명 |
|------|------|------|
| `agent_id`, `role` | str | 식별자 / 역할명 |
| `capabilities[]` | list[str] | 능력 태그 (라우팅 매칭용) |
| `input_schema`, `output_schema` | str | 입출력 스키마 이름 참조 |
| `cost_tier` | `mini`\|`standard`\|`heavy` | 모델 티어 — 실제 모델명은 `config/models.yaml` 정책이 결정 (LLM-agnostic) |
| `max_concurrency` | int | 동시 실행 한도 |
| `requires_tools[]` | list[str] | 필요 도구 (MCP allowlist 대상) |
| `requires_memory_scopes[]` | MemoryScope[] | 접근 가능 메모리 계층 |
| `policy_tags[]` | list[str] | 정책 태그 (예: `no_final_publish`) |

### 3.3 HarnessManifest

**하네스 = "프롬프트 묶음"이 아니라 정책화된 실행 계약** (1st 보고서).

#### 3.3.1 AgentHarness (`kind: agent`)

| 필드 | 설명 |
|------|------|
| `harness_id`, `version` | 식별자, semver |
| `role` | 에이전트 역할 (AgentManifest.role과 매칭) |
| `persona.role`, `persona.objective` | "System Persona & Role" 절 |
| `inherited_directives[]` | "Inherited Master Directives" 절 |
| `ibf_protocol.imitate/benchmark/fusion/maintain` | "Specific I-B-F Protocol" 절 |
| `output_contract.format` | `json`\|`markdown`\|`json+markdown` |
| `output_contract.schema_ref` | 출력 스키마 참조 (있을 시 기계 검증 대상) |
| `language_policy.internal/external` | EN-Core / KO-Edge |
| `tool_policy` | MCP allowlist, sandbox 필수 여부, 외부 쓰기 승인 |
| `cost_tier` | 모델 티어 |

#### 3.3.2 OrchestraHarness (`kind: orchestra`)

| 필드 | 설명 |
|------|------|
| `harness_id`, `version`, `task_class`, `risk_tier` | 오케스트라 기본 정보 |
| `core_directives[]` | Core Directives (No Zero-Shot 등) |
| `required_roles[]` | 필요 에이전트 역할 목록 |
| `phases[]` | Phase 정보: `{phase_id, title, agents, description, gate}` |
| `phases[].gate` | `{gate_id, description, approver}` — approver: `critic`\|`human`\|`secops_qa` |
| `ibf_requirements` | `must_reference_internal_assets`, `must_reference_external_benchmarks`, `proof_format[]` |
| `approval_gates[]`, `tool_policy`, `eval_suite[]`, `rollback_policy` | 공통 정책 |

### 3.4 EvidenceBundle + IBFProof

**No Zero-Shot Invention의 기계적 강제 장치.** 

```
EvidenceBundle
├── bundle_id (evb_), task_id
├── ibf_proof: IBFProof
│   ├── imitated_assets[]        # 내부 RAG 자산 ID (Imitate 증빙)
│   ├── benchmarked_references[] # 외부 레퍼런스 URI (Benchmark 증빙)
│   ├── fusion_method            # 융합 방법 서술
│   ├── trace_ids[]              # 실행 trace span ID
│   └── artifact_hashes[]        # 산출물 해시
├── claims[]: Claim
│   ├── claim_id, text
│   ├── claim_type: factual_assertion | design_inference
│   ├── supports[]: {source, kind: file|web|rag_asset|trace|artifact}
│   └── confidence: float [0,1]
├── counterevidence[]: Claim
└── verifier_status: pending | pass | fail | revise
```

### 3.5 CritiqueReport

v8 Critic 출력 스키마와 **하위 호환**되며 3rd 보고서 findings 구조를 확장.

| 필드 | 타입 | 비고 |
|------|------|------|
| `target_agent` | str | v8 필수 |
| `status` | `APPROVED`\|`REJECTED` | v8 필수 |
| `zero_shot_detected` | bool | v8 필수 |
| `verification_details` | {imitation_check, benchmark_check, fusion_coherence} | v8 필수 |
| `mandatory_revisions[]` | list[str] | v8 |
| `findings[]` | {issue_type, severity, description, proposed_fix} | 확장 |
| `requires_human_approval`, `requires_replan` | bool | 확장 |
| `task_id`, `critique_id` | str? / str | 자동 생성 식별자 |

### 3.6 MemoryRecord

| 필드 | 타입 | 설명 |
|------|------|------|
| `memory_id` | str (`mem_`) | |
| `scope` | `stm`\|`episodic`\|`semantic`\|`skill`\|`evidence` | 5계층 |
| `task_id` | str? | 출처 작업 |
| `timestamp` | datetime (UTC) | |
| `summary` | str | |
| `embedding_ref` | str? | 벡터 참조 (Phase 2) |
| `salience` | float [0,1] | 작업 영향도 — 승격 게이트 입력 |
| `confidence` | float [0,1] | 증거 신뢰도 — 승격 게이트 입력 |
| `decay_policy` | `reinforce_on_reuse`\|`fixed_ttl`\|`immutable` | EVID는 immutable |
| `source_refs[]` | list[str] | |
| `quarantine` | bool | **검증 실패 기록 격리 (폐기 금지)** — 기본 false |
| `reuse_count` | int | 승격 조건 (≥2) 추적용 |

---

## 4. 상태머신 (TaskState)

```
REGISTERED → CLASSIFIED → PLANNED → EXECUTING
EXECUTING ⇄ AWAITING_TOOL
EXECUTING ⇄ AWAITING_HUMAN_APPROVAL
EXECUTING → CRITIQUING → VALIDATED → PUBLISHING → ASSIMILATING → COMPLETED
CRITIQUING → REPLANNING → PLANNED          (반려 → 재계획)
CRITIQUING → AWAITING_HUMAN_APPROVAL       (고위험 판정 / human 게이트)
CRITIQUING → PLANNED                       (오케스트라: 페이즈 게이트 통과 → 다음 페이즈)
AWAITING_HUMAN_APPROVAL → REPLANNING       (승인 거부 → 재계획)
AWAITING_HUMAN_APPROVAL → PLANNED          (페이즈 게이트 승인 → 다음 페이즈)
AWAITING_HUMAN_APPROVAL → VALIDATED        (발행 승인)
{EXECUTING, AWAITING_TOOL} → RECOVERING → EXECUTING   (장애 복구)
임의 비종료 상태 → FAILED
종료 상태: COMPLETED, FAILED
```

---

## 5. 이벤트 목록 (CloudEvents 정렬)

**이벤트 로그가 상태의 source of truth** (event sourcing). replay = 기록된 이벤트의 재생.

| 이벤트 타입 | 발생 시점 |
|------------|----------|
| `task.registered` / `task.classified` | 접수 / 분류·하네스 선택 |
| `harness.compiled` | 하네스 컴파일 완료 |
| `plan.created` | 작업 그래프 생성 |
| `agent.dispatched` | 에이전트 배치 |
| `model.called` / `model.responded` | LLM 호출/응답 (응답 본문 포함 — replay 근거) |
| `tool.called` / `tool.responded` | 도구 호출/응답 |
| `artifact.produced` | 산출물 생성 |
| `critique.issued` | CritiqueReport 발행 |
| `approval.requested` / `approval.granted` / `approval.denied` | HITL 게이트 |
| `replan.triggered` | 재계획 |
| `budget.exceeded` | 예산 초과 (soft/hard) |
| `state.changed` | 상태 전이 (from/to 기록) |
| `artifact.published` | 발행 |
| `knowledge.supplied` | KM의 Imitate 베이스 공급 |
| `knowledge.assimilated` | 지식 자본화 (v8 Phase 7) |
| `policy.denied` | 정책 거부 |
| `recovery.started` | 복구 개시 |
| `task.completed` / `task.failed` | 종료 |
