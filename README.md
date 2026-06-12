# 해마 (Headmaster)

Headmaster는 사용자가 작업을 주면 적절한 에이전트 하네스를 선택하고, 실행, 검증, 승인, 기억 순환까지 관리하는 LLM-agnostic 오케스트레이션 컨트롤 플레인입니다.

해마는 하나의 에이전트가 아니라 에이전트들을 만들고 부리는 제어 화면입니다.

![Dashboard E2E](dashboard-e2e-approved.png)

## 핵심 원칙

| 원칙 | 구현 |
| --- | --- |
| No Zero-Shot Invention | 모든 산출물은 I-B-F Proof를 포함해야 하며, Critic이 증거 존재와 참조 무결성을 기계적으로 검증합니다. |
| I-B-F Loop | Imitate, Benchmark, Fusion, Maintain 흐름으로 내부 자산과 외부 기준을 결합합니다. |
| English-Core / Korean-Edge | 내부 스키마와 판단 로직은 영어를 기준으로 유지하고, 사용자-facing 산출물은 한국어로 제공합니다. |
| LLM-agnostic | 하네스는 cost tier만 선언하고 실제 provider/model은 `backend/headmaster/config/models.yaml`에서 결정합니다. |
| Event-sourced state | 작업 상태와 감사 추적은 이벤트 로그에서 replay할 수 있도록 기록합니다. |
| Safety-by-default | 승인 게이트가 없으면 고위험 작업은 기본 거절되며, 검증 실패 산출물은 격리됩니다. |

## 아키텍처

```text
Control Plane    Task Compiler / Harness Registry / Policy Engine
                 Topology Selector / Budget Ledger

Execution Plane  Orchestrator / Agent Runtime / ModelGateway / ToolGateway
                 Memory Fabric / KnowledgeManager

Assurance Plane  Critic / Approval Gateway / Eval Runner
                 Metrics / Audit Trail / Self-Improvement
```

상세 설계 문서:

- `plan/01_해마_구현계획.md`
- `plan/02_스키마_명세.md`
- `plan/03_검증기준.md`
- `docs/recovery-runbook.md`

## 운영 복구와 안전 경계

Headmaster는 이벤트 로그를 기준으로 작업 상태를 복원합니다. API 서버가 재시작되어도 완료된 작업의 상태, Critic 판정, 산출물 메타데이터를 `/v1/tasks/{task_id}`와 `/v1/tasks/{task_id}/artifact`에서 다시 조회할 수 있습니다.

승인 게이트도 이벤트에서 복원됩니다.

- final publish 승인은 재시작 후에도 `/v1/approvals`에서 다시 확인하고 grant/deny할 수 있습니다.
- grant된 final publish 승인은 저장된 모델 응답과 proof 이벤트를 바탕으로 산출물을 복구 발행합니다.
- deny된 승인은 작업을 `failed`로 닫고 감사 이벤트를 남깁니다.
- `budget_overrun`과 중간 `phase_gate`의 grant 재개는 아직 자동화하지 않습니다. 실행 컨텍스트를 완전히 재구성해야 하므로, 재시작 후 grant 요청에는 명확한 conflict 응답을 반환합니다. deny는 안전하게 실패 상태로 닫습니다.

백그라운드 작업이 예외로 종료되면 중간 상태에 고착되지 않고 `task.failed` 이벤트가 기록됩니다. 또한 cold start 상황에서도 모델이 존재하지 않는 내부 자산 ID를 `imitated_assets`에 적으면 Critic이 반려합니다.

운영 절차와 재시작 경계는 `docs/recovery-runbook.md`에 정리되어 있습니다.

## 빠른 시작

```powershell
cd backend
uv venv --python 3.12
uv pip install -e ".[dev]"

# 오프라인 단일 작업
uv run headmaster run "B2B 랜딩 카피 초안" --provider fake

# 7 phase x 9 agent 오케스트라 작업
uv run headmaster run "B2B 웹사이트 구축" --orchestra b2b_website_v8 --provider fake --approval grant

# 로컬 OAuth CLI provider 사용
uv run headmaster run "시장 조사 요약" --provider claude
uv run headmaster run "기능 구현 계획" --provider codex
uv run headmaster run "랜딩 페이지 초안" --provider agy

# replay / metrics / golden eval / self-improvement
uv run headmaster replay <task_id>
uv run headmaster metrics
uv run headmaster eval
uv run headmaster improve
```

## 대시보드와 API

```powershell
cd frontend
npm ci
npm run build

cd ../backend
uv run headmaster serve --provider fake
```

기본 API와 대시보드는 `http://127.0.0.1:8400`에서 사용할 수 있습니다.

## 실제 모델 provider

- `--provider claude`: Claude Code CLI OAuth 기반 실행. 먼저 `claude auth login`을 완료해야 합니다.
- `--provider codex`: Codex CLI ChatGPT OAuth 기반 실행. 먼저 `codex login`을 완료해야 합니다.
- `--provider agy`: Google Antigravity CLI OAuth 기반 실행
- `--provider gemini`: Gemini CLI OAuth 기반 실행
- `--provider anthropic`: `ANTHROPIC_API_KEY` 필요
- `--provider openai`: `OPENAI_API_KEY` 필요
- `--provider fake`: 네트워크/API 키 없는 오프라인 데모

## 검증

```powershell
cd backend
uv run ruff check .
uv run mypy headmaster
uv run pytest
uv run headmaster eval

cd ../frontend
npm run build
npm run smoke
npm audit --audit-level=moderate
```

권장 추가 확인:

```powershell
# 사용자-facing 문자열 mojibake 회귀 테스트 포함
cd backend
uv run pytest headmaster/tests/test_user_facing_text.py
```

## 저장소 구조

```text
plan/        구현 계획, 스키마 명세, 검증 기준
backend/     Headmaster Python 패키지, API, CLI, 테스트
frontend/    React/Vite 컨트롤 대시보드
소스자료/    리서치 보고서와 테스트 설계 자료
```

## 현재 상태

- Phase 0-1: 스키마, 상태 머신, 하네스 템플릿, ModelGateway, replay, Critic, CLI
- Phase 2: Memory Fabric, KnowledgeManager, 지식 순환, 격리/승격
- Phase 3: HITL 승인, 예산 관리, fan-out 오케스트라, golden eval, audit
- Phase 4: FastAPI 제어 API, 재시작 복구, React 대시보드, self-improvement 루프, CLI provider adapter
- 다음 후보: rejection taxonomy, MCP transport, A2A, PostgreSQL/Temporal 검토
