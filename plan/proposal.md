# 📋 해마(Headmaster) 구현 마스터플랜 (Proposal)

> **버전**: v1.0 (2026-06-11)
> **근거 자료**: `소스자료/리서치/1st~3rd 보고서`, `소스자료/테스트설계/` (Master Orchestrator Harness v8 + 개별 에이전트 하네스 9종, Antigravity 환경 검증 완료)
> **프레임워크**: Boris Cherny PVE — 본 문서는 PLAN 단계의 Proposal(배경/범위/기준) 산출물
> **SDD 3-Tier Spec**: Proposal (배경/목표/정책)

---

## 1. 🎯 요구사항 분석

### 목표

**해마(Headmaster)** = LLM 종류에 상관없이, 작업이 주어지면 그 작업에 맞는 **오케스트라 전체(오케스트레이터 그래프, 에이전트 구성, 하네스, 룰, 루프)를 설계·컴파일·실행·검증·유지관리하는 메타 시스템**.

해마는 에이전트가 아니라 **에이전트들을 만들고 부리는 제어 평면**이다. (1st 보고서: "오케스트레이터가 PM이면 해마는 PMO")

### 입력

- 사용자의 작업 요청 (한국어 자연어) + 제약조건 (예산, 기한, 위험 수준, 증거 요구 수준)
- 시스템 자산: 하네스 템플릿, 에이전트 매니페스트, 정책 팩, 과거 지식(RAG)

### 출력

- 검증 게이트(Critic)를 통과한 최종 산출물 (한국어, 대면용)
- 증거 번들(EvidenceBundle), 실행 트레이스, 감사 로그
- 지식베이스로 환류되는 자산 (MemoryItem / Skill / PolicyPatch) — v8의 Phase 7 "지식 자본화"

### 제약사항 (불변 원칙 — 테스트설계 v8에서 검증됨)

| # | 원칙 | 구현 방식 |
|---|------|----------|
| 1 | **No Zero-Shot Invention** | 모든 산출물에 I-B-F Proof(모방 출처 + 벤치마크 출처 + 융합 방법) 필수. Critic이 스키마 필드 존재·일관성을 기계 검증 |
| 2 | **I-B-F 루프** | Imitate(내부 자산) → Benchmark(외부 레퍼런스) → Fusion(고유 데이터 융합) → Maintain(자산화) |
| 3 | **English-Core / Korean-Edge** | 내부 스키마·추론·하네스는 EN, 사용자 대면 출력만 KO |
| 4 | **Evidence-Based Arbitration** | 에이전트 충돌 시 증거 > 정책 > 소유권 > 비용 순으로 해결 (3rd) |
| 5 | **LLM-agnostic** | 모델 종속 로직은 어댑터 계층에 격리. 하네스/스키마/정책은 모델 무관 |
| 6 | **정책 우선 + 검증 게이트 기본값** | 프롬프트보다 먼저 정책이 컴파일됨. Critic/승인 게이트는 옵션이 아닌 기본값 |
| 7 | **상태 명시화** | 이벤트 소싱 기반. 모든 상태 전이가 기록되고 replay 가능 |

### 환경 제약

- 솔로 개발 (Windows 11, Antigravity / Claude Code)
- 글로벌 규칙: `plan/ · frontend/ · backend/` 3폴더 구조 준수
- 코어 언어: **Python 3.12+** (3개 보고서 일치 권장 — LLM 생태계 완성도), 대시보드는 TypeScript/React
- Python 코딩 규약: type hints 필수 + mypy strict + pytest (TS strict 규칙의 Python 등가물)

---

## 2. ⚠️ 위험 요소

### 🚨 Critical

- **과잉 설계 (최대 리스크)**: 보고서 3개를 합치면 28주+ 엔터프라이즈 프로젝트. 솔로 개발에서 Temporal/NATS/K8s를 초기 도입하면 코어 가치(하네스 컴파일·검증 루프) 도달 전에 소진됨.
  → **완화**: 인프라는 어댑터 경계 뒤로 미루고, Phase 1에서 "CLI로 작업 1건이 I-B-F 게이트를 통과해 산출물이 나오는 것"을 최우선 목표로.
- **LLM-agnostic 추상화 누수**: tool-calling 포맷, structured output 지원, reasoning 토큰 등이 모델마다 다름.
  → **완화**: ModelGateway 계약 테스트(`test_model_gateway.py`)를 어댑터마다 동일 시나리오로 강제. structured output은 JSON Schema 검증 + 재시도로 어댑터 내부에서 보정.
- **Critic 게이트 비용 폭증**: 모든 산출물 검증 시 토큰 비용 ~2배.
  → **완화**: Critic은 mini tier 기본 + 고위험만 heavy tier (1st 보고서 최적화 전략). I-B-F Proof는 **필드 존재·참조 무결성의 기계 검증 우선**, LLM 비평은 2차.

### ⚠️ Warning

- **메모리 오염 (false memory)**: 잘못된 산출물이 SEM/SKILL로 승격되면 이후 모든 작업이 오염됨.
  → 완화: quarantine + 승격 게이트(재사용 2회+, confidence ≥ 0.85, skill은 test_pass_rate ≥ 0.9) 알고리즘을 2nd 보고서 그대로 구현.
- **Prompt Injection / 도구 보안**: MCP 도구 결과가 신뢰 컨텍스트로 유입.
  → 완화: tool-origin labeling, 도구별 allowlist, 외부 쓰기 작업은 human approval 기본값.
- **Replay 결정성 vs LLM 비결정성**: LLM 응답은 재현 불가.
  → 완화: replay는 "재호출"이 아니라 **기록된 이벤트의 재생**. 모델 응답도 이벤트로 저장하므로 상태 복원은 결정적.

### 💡 Low

- 한국어 출력 품질 (English-Core의 부작용): Korean-Edge 변환 시 뉘앙스 손실 → 대면 출력 전용 KO 검수 단계를 Critic 루브릭에 포함.
- Windows 환경에서 일부 라이브러리 호환성 → 초기부터 CI에 Windows 러너 포함 또는 WSL 병행.

---

## 3. 🤔 대안 고려

### 오케스트레이터 런타임

| 옵션 | 판단 |
|------|------|
| **자체 asyncio 런타임 (선택)** | ✅ LLM-agnostic 핵심 가치 보존, 작은 코어, 상태머신·이벤트소싱 완전 통제. 해마의 본질이 "오케스트라를 설계하는 시스템"이므로 런타임 자체가 학습 자산 |
| LangGraph 기반 | 성숙한 persistence/HITL 제공하나 프레임워크 종속. Phase 4에 어댑터로 수용 |
| Temporal 기반 | replay/내구성 최강이나 솔로 MVP엔 운영 부담 과대. 이벤트 소싱 데이터 모델로 이행 경로만 확보 |

### LLM 어댑터

| 옵션 | 판단 |
|------|------|
| **자체 ModelGateway 인터페이스 (선택)** | ✅ 계약 소유권 확보. 내부에서 LiteLLM 활용 가능 |
| LiteLLM 직접 사용 | 빠르나 LiteLLM 추상화에 종속 — "LLM-agnostic 시스템이 어댑터 라이브러리에 lock-in" 모순 |

### 코어 언어

| 옵션 | 판단 |
|------|------|
| **Python (선택)** | ✅ 3개 보고서 일치 권장, MCP/에이전트 생태계 최선 |
| TypeScript | 사용자 주력 언어이나 에이전트 런타임 생태계 열세. 대시보드(frontend/)에서 활용 |

### 시작 규모

| 옵션 | 판단 |
|------|------|
| **단일 프로세스 모노리스 → 어댑터 경계로 분리 준비 (선택)** | ✅ 코어 가치 우선 도달 |
| 보고서 원안 (K8s+NATS+Temporal, 28주) | 솔로 개발 현실성 부족. Phase 4 이후 규모 증명 시 채택 |
