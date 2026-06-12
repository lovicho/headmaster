# 해마 (Headmaster)

> LLM 종류에 상관없이, 작업이 주어지면 그에 맞는 **오케스트라 전체(오케스트레이터·에이전트·하네스·룰·루프)를 설계하고 실행·검증·유지관리하는 메타 시스템**.
> 해마는 에이전트가 아니라, 에이전트들을 만들고 부리는 **제어 평면**이다.

![Dashboard E2E](dashboard-e2e-approved.png)

## 핵심 원칙 (Antigravity 환경에서 검증된 v8 하네스 계승)

| 원칙 | 구현 |
|------|------|
| **No Zero-Shot Invention** | 모든 산출물에 I-B-F Proof(모방 자산 ID + 벤치마크 URI + 융합 방법) 필수 — Critic이 필드 존재·참조 무결성을 기계 검증 |
| **I-B-F 루프** | Imitate(내부 자산) → Benchmark(외부 레퍼런스) → Fusion(고유 데이터) → Maintain(자산화) |
| **English-Core / Korean-Edge** | 내부 스키마·추론은 EN, 대면 출력만 KO |
| **LLM-agnostic** | 하네스는 cost_tier만 선언 — 실제 모델은 `config/models.yaml` 라우팅 정책이 결정. 어댑터 2종(Anthropic/OpenAI)이 동일 계약 테스트 통과 |
| **상태 명시화** | 이벤트 소싱이 단일 진실 — replay는 LLM 재호출이 아닌 기록 재생(결정적) |
| **Safety-by-default** | 승인 게이트웨이 미설정 = 고위험 작업 거부. 검증 실패 기억은 격리(quarantine), 승격은 게이트 통과 시만 |

## 아키텍처 (3평면)

```
제어 평면   Task Compiler · Harness Registry/Compiler · Policy Engine
            Topology Selector(4레벨 조건부 오케스트레이션) · Budget Ledger
실행 평면   Orchestrator(상태머신+이벤트소싱) · Agent Runtime
            ModelGateway(어댑터: anthropic/openai/fake) · Tool Gateway(allowlist)
            Memory Fabric(STM/EPI/SEM/SKILL/EVID + 격리/승격) · KnowledgeManager
보증 평면   Critic(I-B-F 기계검증) · Approval Gateway(HITL) · Eval Runner(golden 회귀 차단)
            Metrics · Audit Trail(who decided/based on what/who approved) · Self-Improvement
```

상세 설계: [`plan/01_해마_구현계획.md`](plan/01_해마_구현계획.md) · 스키마: [`plan/02_스키마_명세.md`](plan/02_스키마_명세.md) · 검증 기준: [`plan/03_검증기준.md`](plan/03_검증기준.md)

## 빠른 시작 (오프라인 — API 키 불필요)

```powershell
cd backend
uv venv --python 3.12
uv pip install -e ".[dev]"

# 단일 작업 (fake provider = 오프라인 데모)
uv run headmaster run "B2B 랜딩 카피 초안" --provider fake

# 멀티에이전트 오케스트라 (7 페이즈 x 9 에이전트)
uv run headmaster run "B2B 웹사이트 구축" --orchestra b2b_website_v8 --provider fake --approval grant

# 상태 replay / 지표 / golden 회귀 / 자기개선
uv run headmaster replay <task_id>
uv run headmaster metrics
uv run headmaster eval
uv run headmaster improve            # 실패 패턴 분석 (--apply로 하네스 패치 승격)
```

### 대시보드 + 제어 API

```powershell
cd frontend && npm ci && npm run build
cd ../backend && uv run headmaster serve --provider fake
# http://127.0.0.1:8400 — 작업 제출, 승인 큐(HITL), 지표, 이벤트 트레이스
```

실제 LLM 사용:
- **`--provider agy`** — Google **Antigravity CLI** OAuth (API 키 불필요, Windows: ConPTY 호스팅). agy CLI 설치 + Google 로그인만 필요
- `--provider gemini` — gemini CLI OAuth (oauth-personal 로그인 필요)
- `--provider anthropic|openai` — `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 환경변수

## 검증

```powershell
cd backend
uv run ruff check . ; uv run mypy headmaster ; uv run pytest   # strict + 75 tests
cd ../frontend && npm run build                                 # tsc strict + vite
```

## 저장소 구조

```
plan/        설계 문서 (PVE: 계획·스키마·검증기준)
backend/     headmaster 패키지 (제어/실행/보증 평면, API, CLI, 테스트)
frontend/    React 제어 대시보드 (Vite + TS strict)
소스자료/     리서치 보고서 1st~3rd + v8 테스트설계 (이 시스템의 근거 자료)
```

## 진행 현황

- ✅ Phase 0 스펙 고정 — 6대 스키마, 상태머신, v8 하네스 10종 YAML 이식
- ✅ Phase 1 코어 MVP — ModelGateway, 이벤트소싱+replay, I-B-F Critic 게이트, CLI
- ✅ Phase 2 지식 순환 — Memory Fabric(격리/승격), KnowledgeManager, 정책 도구 게이트
- ✅ Phase 3 보증 평면 — HITL 승인, 예산 관리, 오케스트라 fan-out, golden eval, 감사 추적
- ✅ Phase 4a-c — 제어 API + HTTP 승인 큐, React 대시보드, 자기개선 루프, CI
- ✅ **실 LLM 파일럿 (agy/Gemini OAuth)** — 실모델이 공급 자산을 모방 베이스로 인용, I-B-F 게이트 1회 통과, KO 카피 + EN SEO 스키마 산출
- ✅ Phase 4d — 에이전트 도구 호출 루프(정책 거부 피드백, rag_search 내장), RECOVERING 장애 복구
- ✅ **실모델 풀 오케스트라 (7페이즈 × 9에이전트, agy/Gemini)** — 120KB 통합 산출물, 99 이벤트. dev_fe_be가 zero-shot으로 1회 거부된 후 수리되어 통과 — Red Team 게이트가 실모델 환각 패턴을 실전에서 차단·복구
- ⏭️ 다음 — rejection taxonomy 축적 → improve 루프 실가동, MCP transport, A2A, PostgreSQL/Temporal 검토
