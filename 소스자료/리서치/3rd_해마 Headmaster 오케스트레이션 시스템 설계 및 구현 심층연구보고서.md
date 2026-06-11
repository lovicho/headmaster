해마 Headmaster 오케스트레이션 시스템 설계 및 구현 심층연구보고서

\#\# Executive Summary

해마(Headmaster)는 단순한 “에이전트 하나를 잘 만드는 방식”이 아니라, 과업의 목적·위험·시간·증거 수준에 맞춰 오케스트레이터, 전문 에이전트, 하네스, 루프, 규칙, 프롬프트, 기억, 검증 절차를 \*\*작업별로 재조립하는 메타-시스템\*\*으로 정의하는 것이 가장 타당하다. 첨부 문서들이 공통적으로 강조하는 핵심도 바로 이 지점이다. 즉, 해마는 모델 호출기나 툴 호출기가 아니라, 작업을 분석하고 에이전트 오케스트라를 설계·배치·모니터링·수정하는 “작전본부”이며, 그 내부 운영 원리는 역할 분해, 근거 중심 실행, 비평-개선 루프, 지식관리, 장기 운영성을 결합한 하네스 공학으로 요약된다. 특히 첨부된 Master Orchestrator Harness 문서는 I-B-F 계열 절차, 역제안 비평, KnowledgeManager/Critic/Researcher 분리, 증거 우선 실행 원칙을 해마의 중심 규율로 제시하고 있으며, 개별 에이전트 하네스 문서는 각 에이전트가 서로 다른 인지 책임을 맡되 공통의 상태 규약과 검증 기준을 따라야 함을 시사한다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2

본 보고서는 첨부 자료의 철학을 현재 공개 표준과 프레임워크 지형 위에 재배치하여, 해마를 \*\*제어 평면, 실행 평면, 보증 평면\*\*으로 분리한 3중 구조로 구현할 것을 권고한다. 제어 평면은 과업 분류, 하네스 컴파일, 에이전트 토폴로지 선택, 우선순위·예산·위험 정책을 담당하고, 실행 평면은 오케스트레이터-워커, 라우팅, 핸드오프, 평가-개선 루프를 실제로 수행하며, 보증 평면은 추적, 정책 강제, 안전 가드레일, 평가, 감사, 리플레이를 담당한다. 이 구조는 LangChain이 설명하는 “프레임워크-런타임-하네스” 구분과 정합적이다. LangChain은 에이전트 프레임워크가 추상화와 통합을 제공하고, LangGraph 같은 런타임이 durable execution·streaming·human-in-the-loop·persistence를 담당하며, Deep Agents 같은 하네스가 planning·subagents·filesystem·context management를 추가한다고 설명한다. 해마는 바로 이 하네스 계층을 더 상위의 메타-오케스트레이션으로 일반화한 형태로 해석할 수 있다. citeturn7view0turn23view3turn23view4

실무적으로는 “모든 작업을 완전 자율 에이전트에 맡기는 방식”보다, \*\*작업 특성에 따라 서로 다른 워크플로우 패턴을 혼합\*\*하는 것이 더 안정적이다. LangGraph 문서는 라우팅, 오케스트레이터-워커, 평가자-최적화자 패턴을 별도의 1급 패턴으로 제시하고, OpenAI Agents SDK는 여러 에이전트의 협업에서 manager-style agents-as-tools와 handoff를 구분해 사용하라고 권고한다. 해마 설계에서 이 둘은 상호보완적이다. 즉, 해마는 먼저 작업을 분류하고, 예측 가능한 부분은 라우팅·결정형 플로우로, 불확실성과 창의성이 큰 부분은 오케스트레이터-워커로, 품질 기준이 엄격한 부분은 평가-개선 루프로, 사용자-facing 전환이 필요한 부분은 handoff로 다루는 것이 바람직하다. 이렇게 해야 비용·지연·불확실성·위험을 동시에 제어할 수 있다. citeturn23view0turn23view1turn23view2turn4view2turn4view3turn4view4

표준 측면에서는 \*\*도구·데이터 접근은 MCP, 에이전트 간 협업은 A2A, REST 친화 엔터프라이즈 통합은 ACP, 외부 제어 API는 OpenAPI와 JSON Schema, 내부 이벤트는 CloudEvents, 관측성은 OpenTelemetry와 Prometheus\*\*를 중심으로 삼는 것이 가장 설계 일관성이 높다. MCP는 AI 애플리케이션과 외부 시스템을 연결하는 오픈 표준으로, tools·resources·prompts를 JSON-RPC 기반으로 교환하고 stdio 또는 HTTP 전송을 지원한다. A2A는 독립 에이전트들 간의 peer collaboration과 task lifecycle을 위한 application-level protocol이며, JSON-RPC 2.0 over HTTP(S)와 SSE를 사용한다. ACP는 RESTful API와 MIME 타입, 비동기·장시간 작업, 오프라인 발견을 강조하고 있으며 현재 A2A로 통합되는 흐름에 있다. External contract는 OpenAPI, payload schema는 JSON Schema, internal bus envelope은 CloudEvents로 통일하면 해마의 제어·실행·관측 계층을 분리해도 의미 변형이 적다. citeturn39view0turn19view0turn20view2turn22view0turn22view2turn21view0turn40view0turn41view0turn41view1

보안과 운영 측면에서 해마는 “도구를 잘 쓰는 시스템”이 아니라 “도구 사용이 늘어날수록 공격면이 급격히 커지는 시스템”으로 보아야 한다. OWASP의 LLM/GenAI 보안 지침은 Prompt Injection, Insecure Output Handling, Training Data Poisoning, Supply Chain Vulnerabilities, Sensitive Information Disclosure, Excessive Agency 등을 상위 위험으로 제시한다. MCP 관련 최근 연구들도 prompt injection, tool poisoning, unintended privacy disclosure, maintainability·security 취약성을 별도로 지적한다. 따라서 해마는 \*\*정책 강제형 가드레일, 샌드박스, 권한스코프, 승인 게이트, 출력 검역, 메모리 독성 검사, 회귀 평가\*\*를 기본 내장 기능으로 봐야 하며, 이는 나중에 덧붙일 옵션이 아니라 아키텍처의 중심축이어야 한다. citeturn36view0turn36view1turn36view2turn35view0turn16academia4turn11academia1

최종 권고는 다음과 같다. 해마의 초기 버전은 범용 “초지능 에이전트”가 아니라, \*\*작업분류기 \+ 하네스 컴파일러 \+ 정책엔진 \+ 오케스트레이터 \+ Critic \+ KnowledgeManager\*\*로 시작해야 한다. 런타임은 durable execution을 지원하는 구조로 설계하고, 작은 규모에서는 LangGraph 또는 OpenAI Agents SDK 기반으로 시작하되, 장기적으로는 Temporal형 재현·회복 메커니즘과 Kubernetes형 desired-state 운영, OpenTelemetry형 추적, Prometheus형 수치 관측을 흡수하는 것이 바람직하다. 첨부 자료의 철학과 공개 생태계 표준을 종합하면, 해마의 본질은 “에이전트를 많이 두는 것”이 아니라 “작업에 맞는 에이전트 조합과 통제 구조를 매번 설계하는 것”이며, 따라서 \*\*해마의 핵심 산출물은 답변이 아니라 하네스 설계안\*\*이어야 한다. fileciteturn0file1 fileciteturn0file2 citeturn8view0turn9view1turn10view0turn10view2

\#\# 목적과 요구사항

\#\#\# 해마의 개념적 정의와 설계 목표

사용자 정의에 따르면 해마는 인간 뇌의 해마처럼 기억과 맥락 연결의 은유를 가지면서도, 오케스트라의 단장처럼 목적이 있는 공연을 위해 인원·악보·순서·등장 시점·품질 기준을 설계하고 관리하는 역할을 맡는다. 첨부 하네스 문서들은 이 정의를 보다 공학적으로 구체화한다. 오케스트레이터는 단순 라우터가 아니라 작업을 분해하고, 적합한 에이전트와 도구를 선정하며, 실행 중 비평과 재계획을 수행하고, 결과를 지식으로 환류시키는 상위 책임자여야 한다. 개별 에이전트는 모두 “잘 말하는 모델”이 아니라 Researcher, Critic, KnowledgeManager, Planner, Executor처럼 명시적 책임을 가진 부품으로 조직된다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2

따라서 해마의 1차 목적은 정답 생성이 아니라 \*\*작업-맞춤형 에이전틱 환경의 자동 설계\*\*이고, 2차 목적은 \*\*설계된 환경의 안전한 실행과 개선\*\*, 3차 목적은 \*\*운영 중 지식 축적과 성능 진화\*\*다. 이 정의는 LangChain이 하네스를 “모델·프롬프트·툴·미들웨어까지 포함한 에이전트 루프 주변의 모든 것”으로 설명하는 방식과 직접 대응한다. 해마는 이 하네스 개념을 개별 에이전트 수준에서 전체 작업 수준으로 끌어올린 메타 하네스 매니저라고 볼 수 있다. citeturn2view0turn42view0turn7view0

\#\#\# 요구사항 해석과 미지정 항목

아래 표는 사용자 명세와 첨부 자료를 기준으로 해마의 요구사항을 해석한 것이다. 명시되지 않은 항목은 요청대로 \*\*미지정\*\*으로 표시한다.

| 항목 | 해석 | 상태 |  
|---|---|---|  
| 시스템 정체성 | AI 에이전틱 오케스트레이션 시스템 | 지정 |  
| 핵심 역할 | 오케스트레이터, 에이전트, 하네스, 루프, 룰, 프롬프트 설계·운영 | 지정 |  
| 출력 언어 | 한국어 | 지정 |  
| 주요 입력 | 사용자 과업, 조직 정책, 도구 목록, 지식원, 첨부 문서 | 부분 지정 |  
| 목표 작업 범위 | 범용 지식작업 및 목적형 업무 자동화 | 부분 지정 |  
| 대상 산업/도메인 | 미지정 | 미지정 |  
| 멀티테넌시 범위 | 미지정 | 미지정 |  
| 운영 배포 형태 | 온프레미스/클라우드/하이브리드 미지정 | 미지정 |  
| SLA 목표 | 미지정 | 미지정 |  
| 예산 상한 | 미지정 | 미지정 |  
| 데이터 보존기간 | 미지정 | 미지정 |  
| 개인정보 처리 범위 | 미지정 | 미지정 |  
| 사람 승인 필요 행위 | 고위험 행위 필요성이 암시되나 구체 기준은 미지정 | 미지정 |  
| 외부 시스템 통합 목록 | 첨부 문서 외 미지정 | 미지정 |  
| 정량 성공척도 | 명시적 KPI는 미지정, 보고서에서 설계 필요 | 미지정 |

이 표가 의미하는 바는 분명하다. 현재 해마 설계는 \*\*범용 제어 구조는 충분히 설계할 수 있으나, 조직별 정책 파라미터는 추후 주입 가능한 형태로 남겨야 한다\*\*는 것이다. 따라서 설계는 하드코딩된 업무 시스템이 아니라, 미지정 항목을 런타임 정책으로 채우는 policy-driven architecture여야 한다. LangChain과 OpenAI Agents SDK가 모두 context, runtime behavior, handoffs, guardrails를 런타임 구성으로 다루는 것도 같은 이유다. citeturn42view0turn4view0turn4view4

\#\#\# 설계 원칙

해마의 설계 원칙은 첨부 자료와 최신 에이전트 연구를 종합하면 다음과 같이 정리된다. 첫째, \*\*증거 우선\*\*이다. Researcher는 툴과 외부 문서를 통해 근거를 수집하고, Critic은 추론·증거·형식 간 불일치를 탐지한다. 둘째, \*\*역할 분리\*\*다. CAMEL, MetaGPT, ChatDev, AutoGen은 역할 분해와 협업 규약이 복잡 작업에 유리함을 보여주며, 첨부 문서 역시 Researcher, Critic, KnowledgeManager 분리를 전제한다. 셋째, \*\*루프 기반 품질 개선\*\*이다. ReAct는 reasoning과 acting의 교차를, Reflexion과 Self-Refine은 언어적 피드백 기반 개선을, LangGraph는 evaluator-optimizer 패턴을 제시한다. 넷째, \*\*상태와 기억의 명시화\*\*다. 장기 실행과 복구에는 state, thread, checkpoint, event history가 필요하다. 다섯째, \*\*정책의 결정적 강제\*\*다. 프롬프트만으로는 충분하지 않으며, 가드레일과 승인 게이트가 별도로 필요하다. fileciteturn0file1 fileciteturn0file2 citeturn25academia1turn25academia2turn25academia3turn26academia2turn24academia2turn24academia1turn26academia1turn23view1turn36view1

이 다섯 원칙은 결국 해마를 “LLM 위에 얹은 UX”가 아니라 “정책, 상태, 검증, 증거, 실행환경이 결합된 운영체제형 제어계층”으로 바라보게 만든다. 특히 Kubernetes가 자신을 전통적인 순차 오케스트레이션이 아니라 desired state를 지속적으로 수렴시키는 독립적 control process의 집합으로 설명하는 점은, 해마를 단일 중앙 루프보다 \*\*지속적 상태 수렴형 컨트롤러 집합\*\*으로 설계해야 한다는 좋은 비유를 제공한다. citeturn9view1

\#\# 시스템 아키텍처

\#\#\# 권장 아키텍처 개요

해마는 세 개의 평면으로 설계하는 것이 가장 안정적이다. \*\*제어 평면\*\*은 작업을 해석하고 하네스를 컴파일한다. \*\*실행 평면\*\*은 실제 대화, 툴 호출, 에이전트 협업, 산출물 생성을 수행한다. \*\*보증 평면\*\*은 관측성, 정책 강제, 감사를 담당한다. LangGraph가 durable execution, persistence, human-in-the-loop, memory를 런타임의 핵심으로 보고, LangChain이 execution environment, context management, planning and delegation, fault tolerance, guardrails, steering를 하네스 구성의 핵심으로 제시하는 점을 합치면, 해마는 이 기능들을 하나의 상위 시스템으로 재조직해야 한다. citeturn23view3turn23view4turn42view0turn7view0

\`\`\`mermaid  
flowchart TD  
    U\[사용자 요청\] \--\> TC\[Task Compiler\]  
    TC \--\> CL\[과업 분류기\]  
    TC \--\> PC\[정책/위험 엔진\]  
    TC \--\> HR\[Harness Registry\]  
    TC \--\> AF\[Agent Factory\]

    CL \--\> TOP\[토폴로지 선택기\]  
    PC \--\> TOP  
    HR \--\> TOP  
    AF \--\> TOP

    TOP \--\> ORCH\[해마 오케스트레이터 런타임\]  
    ORCH \--\> A1\[Researcher\]  
    ORCH \--\> A2\[Planner\]  
    ORCH \--\> A3\[Executor\]  
    ORCH \--\> A4\[Critic\]  
    ORCH \--\> A5\[KnowledgeManager\]  
    ORCH \--\> A6\[Safety Guard\]

    A1 \--\> TOOLS\[도구/데이터 계층\]  
    A2 \--\> TOOLS  
    A3 \--\> TOOLS  
    A5 \--\> MEM\[지식/버전 저장소\]

    ORCH \--\> OBS\[관측성/평가/감사\]  
    OBS \--\> OTEL\[OpenTelemetry\]  
    OBS \--\> PROM\[Prometheus\]  
    OBS \--\> TRACE\[Trace Store\]

    PC \--\> GATE\[승인 게이트\]  
    GATE \--\> ORCH  
\`\`\`

위 다이어그램의 핵심은 해마가 오케스트레이터 그 자체와 동일하지 않다는 점이다. 해마는 \*\*오케스트레이터를 만드는 시스템\*\*이고, 실행 시점에는 선택된 오케스트레이터 토폴로지가 런타임에 인스턴스화된다. OpenAI Agents SDK가 “few primitives” 접근으로 Agents, Handoffs, Guardrails, Tracing을 제시하고, LangChain이 agent \= model \+ harness라고 설명하는 것을 결합하면, 해마는 “task \= intent \+ policy \+ harness graph \+ agent roster \+ assurance contract”라는 상위 추상으로 정의하는 것이 적절하다. citeturn4view0turn4view1turn2view0

\#\#\# 모듈 구성과 인터페이스

해마의 내부 모듈은 다음과 같이 권장된다.

| 모듈 | 책임 | I/O 형식 | 비고 |  
|---|---|---|---|  
| Task Compiler | 사용자 과업을 기계 실행 가능한 명세로 변환 | \`TaskSpec\` JSON | 필수 |  
| Capability Registry | 에이전트/도구/프로토콜/정책 capability 저장 | 스키마 문서 \+ manifests | 필수 |  
| Harness Registry | 재사용 가능한 하네스 템플릿 버전 관리 | Prompt pack \+ policy pack \+ graph spec | 필수 |  
| Topology Selector | 라우팅형/워크플로우형/매니저-워커형/핸드오프형 선택 | \`ExecutionPlan\` | 필수 |  
| Orchestrator Runtime | 실행, 재시도, 중단, handoff, 병렬화 | event stream \+ state store | 필수 |  
| Critic Service | 증거·논리·형식·정책 위반 비평 | \`CritiqueReport\` | 필수 |  
| KnowledgeManager | 결과를 reusable knowledge로 변환 | \`MemoryItem\`, \`Skill\`, \`PolicyPatch\` | 필수 |  
| Assurance Plane | tracing, metrics, evaluation, audit | trace/span, metric series | 필수 |  
| Sandbox Broker | 고위험 툴 실행과 파일시스템/코드 격리 | ephemeral session | 권장 |  
| Human Approval Gateway | 파괴적/비용 높은 작업 승인 | \`ApprovalTicket\` | 권장 |

이 모듈 분리는 첨부 자료의 역할 분해와 일치한다. 특히 Master Orchestrator Harness의 Critic, Reverse Proposal, Knowledge 확장 구조, 개별 에이전트 문서의 specialized harness는 해마가 단일 시스템 프롬프트가 아니라 \*\*모듈식 역할 객체의 합성체\*\*여야 함을 보여준다. 또한 LangChain 미들웨어가 execution environment, planning/delegation, fault tolerance, guardrails, steering를 별도 concern으로 나누는 것도 같은 방향을 지지한다. fileciteturn0file1 fileciteturn0file2 citeturn42view0

\#\#\# 데이터 흐름과 상태 관리

데이터 흐름은 요청 중심이 아니라 \*\*상태 중심\*\*으로 설계하는 것이 안전하다. LangGraph는 persistence, memory, human-in-the-loop, subgraphs를 핵심 capability로 제시하고, Temporal은 workflow execution을 event history 기반으로 재구성한다. Temporal은 외부 세계와 상호작용하는 작업을 Activity로 분리하고, workflow는 deterministic해야 하며, event history가 상태 복원의 source of truth라고 설명한다. 해마도 같은 원리를 채택해야 한다. 즉, 모델 호출, 툴 결과, 승인 이벤트, 비평 결과, 재계획 결정, 최종 산출물을 모두 이벤트로 기록하고, 런타임은 이 이벤트 시퀀스로부터 재연 가능해야 한다. citeturn23view3turn8view0

\`\`\`mermaid  
flowchart LR  
    RQ\[Request\] \--\> TS\[TaskSpec 생성\]  
    TS \--\> SP\[State Snapshot v0\]  
    SP \--\> PL\[Plan\]  
    PL \--\> EV1\[Run Events\]  
    EV1 \--\> CR\[Critique\]  
    CR \--\>|수정 필요| RP\[Replan\]  
    RP \--\> EV2\[Run Events\]  
    CR \--\>|통과| AR\[Artifact\]  
    AR \--\> KM\[Knowledge Assimilation\]  
    KM \--\> VS\[Versioned Store\]  
    EV1 \--\> EH\[Event History\]  
    EV2 \--\> EH  
    EH \--\> RE\[Replay/Recovery\]  
\`\`\`

해마에서 최소 상태 단위는 다음 다섯 가지다. \*\*TaskSpec\*\*, \*\*ExecutionState\*\*, \*\*EvidenceBundle\*\*, \*\*CritiqueReport\*\*, \*\*ArtifactManifest\*\*다. 이 다섯 객체가 있어야 어떤 실패도 재현, 원인분석, 비교평가가 가능하다. 첨부 자료가 비평과 지식관리를 별도 객체로 다루는 이유도 여기에 있다. 단순 메시지 로그만으로는 시스템이 왜 특정 토폴로지를 선택했고 왜 작업을 재시도했는지 설명할 수 없다. fileciteturn0file1 fileciteturn0file2

\#\#\# 프로토콜, API, 데이터 포맷 권장안

MBP(Model-Behavior-Protocol) 관점에서 해마는 표준을 층위별로 나누어 써야 한다. MCP는 \*\*모델/에이전트와 외부 도구·데이터·프롬프트의 연결\*\*에 유효하고, A2A는 \*\*독립 에이전트 간 peer interaction\*\*에 적합하며, ACP는 \*\*REST 친화적인 엔터프라이즈 에이전트 통합\*\*에 유리하다. MCP는 tools, resources, prompts, capability negotiation, stdio/HTTP transport를 제공하고, A2A는 AgentCard, task, task status, streaming, push notifications, JSON-RPC binding을 제공하며, ACP는 REST, MIME types, stateful/stateless, async-first, offline discovery를 강조한다. 따라서 해마의 권장 표준 구성은 아래와 같다. citeturn39view0turn19view0turn20view2turn22view0turn22view2turn21view0

| 계층 | 권장 표준 | 선택 이유 |  
|---|---|---|  
| 외부 제어 API | OpenAPI 3.1 이상 | HTTP API를 언어 중립적으로 기술하고 발견 가능하게 만들기 위함. OAS는 language-agnostic HTTP API interface description이다. citeturn40view0 |  
| 요청/응답 스키마 | JSON Schema 2020-12 | 현재 버전이 2020-12이며 구조 검증과 계약 버전관리에 적합하다. citeturn41view0 |  
| 내부 이벤트 엔벨로프 | CloudEvents | 이벤트를 공통 형식으로 기술해 라우터·트레이서·도구 호환성을 높이기 위함이다. citeturn41view1turn41view2 |  
| 도구/지식 연결 | MCP | tools/resources/prompts와 capability negotiation이 표준화되어 있다. citeturn39view0turn19view0 |  
| 에이전트 간 협업 | A2A | task lifecycle, AgentCard, streaming, push notifications를 제공한다. citeturn20view2turn22view0turn22view2 |  
| 엔터프라이즈 REST 통합 | ACP 어댑터 | REST 기반, MIME 타입, 오프라인 발견, 장시간 작업에 유리하다. citeturn21view0 |  
| 추적/관측 | OTLP/OpenTelemetry \+ Prometheus | traces, metrics, logs와 시계열 수집/경보 체계의 분업이 명확하다. citeturn10view0turn10view1turn10view2turn10view3 |  
| 식별자 | UUIDv7 | time-ordered 특성으로 DB locality와 정렬성이 좋다. citeturn41view3turn41view4 |

해마의 API는 단순 CRUD가 아니라 \*\*intentful API\*\*로 설계해야 한다. 예를 들어 \`/task/compile\`, \`/task/run\`, \`/task/pause\`, \`/task/approve\`, \`/artifact/publish\`, \`/knowledge/assimilate\`, \`/policy/simulate\`, \`/trace/replay\` 같은 엔드포인트가 적절하다. 외부에는 REST/OpenAPI를 노출하되, 내부 실행은 이벤트 흐름과 상태 기계로 다루는 것이 좋다. 그 이유는 외부 계약은 명확해야 하지만, 내부 실행은 빈번히 재계획되고 비동기·스트리밍을 포함하기 때문이다. citeturn40view0turn41view1turn20view2

\#\#\# 메시징 백본 선택

| 옵션 | 장점 | 단점 | 해마 적용성 |  
|---|---|---|---|  
| NATS \+ JetStream | pub/sub, request/reply, persistence streaming을 단일 시스템에서 제공하고 경량·저지연이다. citeturn9view4 | 대규모 분석 파이프라인이나 장기 보관 데이터 레이크 연동은 Kafka보다 생태계가 좁을 수 있다. | 초기\~중기 운영에 매우 적합 |  
| Kafka | publish/subscribe, durable storage, retrospective processing, 높은 확장성을 제공한다. citeturn9view5 | 운영 복잡도와 인프라 무게가 크다. | 대규모 이벤트 분석·감사 요구 시 적합 |  
| 직접 DB 큐 | 단순하고 빠르게 시작 가능 | 스트리밍·fan-out·backpressure·재처리 설계가 취약해지기 쉽다 | PoC까지만 권장 |

해마의 초기 버전은 NATS 중심이 현실적이다. 이유는 해마가 실시간 상태 전파, request/reply, 경량 운영, 다중 에이전트 간 간헐적 통신을 모두 요구하기 때문이다. 다만 감사·분석·장기 이벤트 재처리 비중이 높아지면 Kafka를 보조 백본으로 두는 이중 구조도 고려할 수 있다. citeturn9view4turn9view5

\#\#\# 공식 도식이 포함된 온라인 페이지 링크

아래 링크들은 본 보고서가 참조한 공식 문서 페이지이며, 아키텍처·루프·워크플로우 이미지가 포함되어 있다. citeturn2view0turn2view2turn39view0turn19view1

\`\`\`text  
https://docs.langchain.com/oss/python/langchain/agents  
https://docs.langchain.com/oss/python/langgraph/workflows-agents  
https://modelcontextprotocol.io/docs/learn/architecture  
https://a2a-protocol.org/latest/specification/  
\`\`\`

\#\# 에이전틱 워크플로우와 오케스트레이터 설계

\#\#\# 권장 워크플로우 패턴 조합

해마는 하나의 패턴으로 모든 작업을 해결하려 하면 실패한다. LangGraph는 라우팅, 오케스트레이터-워커, 평가자-최적화자, 에이전트 루프를 구분하고, OpenAI Agents SDK는 manager agent와 handoff를 구분한다. 이를 해마에 적용하면 다음과 같은 조합 규칙이 자연스럽다. \*\*질문 분류와 정책 판정에는 라우팅\*\*, \*\*문서 초안·멀티파트 산출물 생성에는 오케스트레이터-워커\*\*, \*\*품질 기준이 명확한 결과물에는 evaluator-optimizer\*\*, \*\*전문 역할이 사용자와 직접 상호작용해야 할 때는 handoff\*\*, \*\*하위 작업 도우미는 agents-as-tools\*\*를 사용한다. citeturn23view0turn23view1turn23view2turn4view2turn4view3turn4view4

가장 중요한 설계 원칙은 \*\*매니저가 언제까지 conversation ownership을 유지할지\*\*를 명시하는 것이다. OpenAI는 agents-as-tools에서는 manager가 대화를 통제하고, handoff에서는 specialist가 turn ownership을 넘겨받는다고 설명한다. 해마에서는 원칙적으로 Headmaster가 최종 품질 책임을 유지하되, 사용자 경험상 전문화된 응답이 유리한 경우에만 제한적 handoff를 허용하는 것이 바람직하다. 그렇지 않으면 정책 일관성, 비용 추적, 감사 추적이 급격히 어려워진다. citeturn4view3turn4view4

\#\#\# 상태 머신 설계

\`\`\`mermaid  
stateDiagram-v2  
    \[\*\] \--\> Registered  
    Registered \--\> Classified  
    Classified \--\> Planned  
    Planned \--\> Executing  
    Executing \--\> AwaitingTool  
    AwaitingTool \--\> Executing  
    Executing \--\> AwaitingHumanApproval  
    AwaitingHumanApproval \--\> Executing  
    Executing \--\> Critiquing  
    Critiquing \--\> Replanning  
    Replanning \--\> Executing  
    Critiquing \--\> Validated  
    Validated \--\> Publishing  
    Publishing \--\> Assimilating  
    Assimilating \--\> Completed  
    Executing \--\> Failed  
    Critiquing \--\> Failed  
    Replanning \--\> Failed  
    Failed \--\> Recovered  
    Recovered \--\> Executing  
    Completed \--\> \[\*\]  
\`\`\`

이 상태 머신에서 중요한 것은 \*\*Critiquing과 Replanning이 1급 상태\*\*라는 점이다. 많은 에이전트 시스템이 이것을 단순 내부 사고로 처리하지만, 해마는 이를 명시적 상태로 분리해야 한다. 그래야 품질 개선이 우연한 “한 번 더 돌리기”가 아니라, 언제 어떤 이유로 어떤 피드백을 받아 어떤 재설계를 했는지 추적된다. LangGraph의 evaluator-optimizer 패턴과 Reflexion, Self-Refine이 보여준 개선 효과는, 비평이 내부 생각이 아니라 독립 루프여야 함을 시사한다. citeturn23view1turn24academia1turn26academia1

\#\#\# 스케줄링 정책

해마의 스케줄링은 운영체제형 우선순위 큐와 워크플로우 정책의 결합으로 설계하는 편이 좋다. 권장 우선순위 함수는 다음 다섯 항목의 가중합이다. \*\*업무 중요도\*\*, \*\*기한 압박도\*\*, \*\*정책 위험도\*\*, \*\*맥락 준비도\*\*, \*\*비용 예산 잔량\*\*이다. 단, 위험도가 높은 작업은 우선순위가 높더라도 사람 승인 없이 실행 대기 상태로 보내야 한다. LangChain이 steering과 guardrails를 পৃথ立 concern으로 둔 이유가 여기에 있다. 또한 production에서는 rate limits, timeouts, transient API failures가 흔하므로 fault tolerance는 인프라 레벨 concern으로 취급해야 한다. citeturn42view0

권장 스케줄링 규칙은 다음과 같다. 첫째, planner와 critic은 대체로 상위 모델을 쓰되, 반복 리트라이를 막기 위해 호출 횟수 상한을 둔다. 둘째, worker는 경량 모델 중심으로 병렬화하되, evidence sufficiency score가 낮을 때만 상위 모델로 승격한다. 셋째, sandbox 또는 고비용 툴 호출은 budget token을 차감하고 승인 정책을 체크한다. 넷째, 동일 작업 내 병렬 subtask는 서로 독립 state를 가져야 하며, shared state key에는 append-only 방식으로만 쓰도록 한다. 이는 LangGraph의 Send API와 shared state 패턴과 정합적이다. citeturn23view0turn42view0

\#\#\#\# 스케줄링 의사코드

\`\`\`text  
function schedule(task):  
    risk \= assess\_risk(task)  
    urgency \= assess\_deadline(task)  
    value \= assess\_business\_priority(task)  
    readiness \= assess\_context\_readiness(task)  
    budget \= remaining\_budget(task)

    if risk.requires\_human\_approval and not task.approved:  
        return QUEUE\_AWAITING\_APPROVAL

    score \= w1\*value \+ w2\*urgency \+ w3\*readiness \- w4\*risk.penalty \- w5\*budget.penalty

    if score \>= threshold\_parallel and task.decomposable:  
        return RUN\_ORCHESTRATOR\_WORKER  
    if task.has\_explicit\_quality\_criteria:  
        return RUN\_EVALUATOR\_OPTIMIZER  
    if task.is\_simple\_routable:  
        return RUN\_ROUTER\_FLOW  
    return RUN\_MANAGER\_LOOP  
\`\`\`

이 알고리즘의 핵심은 “더 중요하면 더 자율적”이 아니라 “더 중요할수록 더 통제적”일 수 있다는 점이다. OWASP가 Excessive Agency를 독립 위험으로 분류하는 이유도, 많은 시스템이 중요 작업일수록 더 많은 권한을 주기 때문이다. 해마는 그 반대로 중요도와 위험도가 높을수록 통제 강도를 높여야 한다. citeturn36view1

\#\#\# 충돌 해결 정책

충돌은 세 가지 층위에서 생긴다. \*\*결과 충돌\*\*, \*\*정책 충돌\*\*, \*\*자원 충돌\*\*이다. 결과 충돌은 서로 다른 에이전트가 상반된 결론을 낼 때 발생한다. 정책 충돌은 사용자 요청과 조직 정책, 정책과 정책, 지역 규제와 내부 표준이 충돌할 때 발생한다. 자원 충돌은 동일 툴, 동일 파일, 동일 예산, 동일 세션을 여러 에이전트가 동시에 요구할 때 발생한다. 첨부 문서의 Critic/Reverse Proposal 구조는 첫 번째와 두 번째 충돌을 해결하기 위한 장치로 해석할 수 있다. fileciteturn0file2

권장 원칙은 \*\*증거 \> 정책 \> 소유권 \> 비용\*\* 순서다. 즉, 서로 다른 에이전트 결과가 충돌하면 Critic이 evidence sufficiency와 source quality를 비교하고, 근거가 빈약하면 재조사를 요청한다. 정책이 충돌하면 상위 policy namespace가 하위 policy를 덮고, 사람이 승인한 예외만 override ticket을 통해 허용한다. 자원 충돌은 optimistic locking이 아니라 lease와 reservation으로 처리하는 편이 안전하다. 특히 파일 수정과 외부 시스템 write 작업은 단일 writer 원칙을 두는 것이 바람직하다. Kubernetes의 독립 control loop 사고와 Temporal의 event history 기반 회복 모델은 중앙 순차 제어보다 이런 상태 기반 조정에 더 잘 맞는다. citeturn9view1turn8view0

\#\#\#\# 충돌 해결 의사코드

\`\`\`text  
function resolve\_conflict(items):  
    ranked \= sort\_by(  
        evidence\_quality,  
        source\_authority,  
        freshness,  
        policy\_compliance,  
        reproducibility  
    )

    top \= ranked\[0\]  
    second \= ranked\[1\]

    if top.evidence\_quality \- second.evidence\_quality \< delta:  
        return request\_additional\_research()

    if top.policy\_compliance \== false:  
        return reject\_and\_replan()

    if top.requires\_override\_ticket and not override\_ticket\_present():  
        return await\_human\_approval()

    return accept(top)  
\`\`\`

\#\#\# 모니터링과 운영 가시성

모니터링은 해마에서 선택사항이 아니다. OpenAI Agents SDK는 built-in tracing을 강하게 권장하고, LangSmith/LangGraph는 trace, debug, evaluate를 핵심 가치를 내세운다. OpenTelemetry는 traces, metrics, logs를 vendor-agnostic하게 생성·수집·내보내기 위한 표준 프레임워크이며, Prometheus는 시계열 metrics와 alerting에 특화되어 있다. 따라서 해마는 모든 task와 agent step에 \*\*trace\_id, task\_id, artifact\_id, policy\_id, cost\_id\*\*를 남겨야 하며, metrics는 Prometheus, traces는 OTel/trace backend, 장기 감사는 이벤트 스토어로 분리하는 것이 적절하다. citeturn4view0turn4view1turn3view3turn10view0turn10view1turn10view2turn10view3

권장 대시보드는 네 계층으로 나뉜다. \*\*실행 대시보드\*\*는 task progress, retries, approval queue를 보여주고, \*\*품질 대시보드\*\*는 success rate, critique hit rate, regression 여부를 보여주며, \*\*안전 대시보드\*\*는 prompt injection 탐지, PII 차단, policy exceptions를 보여주고, \*\*경제성 대시보드\*\*는 token cost, tool cost, cache hit rate, model escalation rate를 보여준다. MultiAgentBench가 milestone-based KPI를 제안하고 AgentBench가 장기 추론·의사결정·instruction following의 병목을 지적한 점은, 해마가 단순 “정답률”보다 실행 과정형 KPI를 더 많이 가져야 함을 보여준다. citeturn25academia0turn24academia3

\#\# 에이전트 설계와 하네스 공학

\#\#\# 핵심 에이전트 군과 책임 분리

해마에서 “에이전트”는 곧 프롬프트의 다른 버전이 아니다. 책임과 입력·출력·실패 모드가 다른 \*\*직무 객체\*\*다. 첨부 자료를 기반으로 최소 권장 에이전트 구성은 Researcher, Planner, Executor, Critic, Safety Guard, KnowledgeManager, Tool Broker다. Researcher는 증거 수집과 source normalization, Planner는 decomposition과 task graph 생성, Executor는 artifact 생산, Critic은 결함 탐지와 역제안, Safety Guard는 정책 집행, KnowledgeManager는 재사용 가능한 스킬/기억/정책 후보를 저장한다. fileciteturn0file1 fileciteturn0file2

이 역할 분리는 CAMEL의 role-playing, MetaGPT의 SOP 기반 에이전트 분배, ChatDev의 phase-specialized software roles, AutoGen의 customizable multi-agent conversation과 잘 부합한다. 연구적으로는 역할 분해가 단순 체인보다 협업 효율과 제어 가능성을 높이지만, 동시에 coordination failure가 생길 수 있으므로 역할과 메시지 계약을 명시해야 한다. 해마는 바로 이 계약을 하네스로 캡슐화해야 한다. citeturn25academia1turn25academia2turn25academia3turn26academia2

\#\#\# 능력 모델과 메타인지

해마 에이전트의 능력 모델은 최소 다섯 축으로 정의해야 한다. \*\*도메인 지식\*\*, \*\*도구 사용 능력\*\*, \*\*상태 인식 능력\*\*, \*\*자기 한계 인식\*\*, \*\*정책 준수 능력\*\*이다. Toolformer는 모델이 언제 어떤 API를 어떤 인자로 호출할지 학습할 수 있음을 보여주며, ReAct는 reasoning과 acting의 인터리빙이 예외 처리와 계획 갱신에 유리함을 보여준다. Reflexion과 Self-Refine은 외부 보상 없이도 언어적 피드백을 통해 성능을 개선할 수 있음을 보여준다. 해마의 메타인지 계층은 바로 이 네 연구 흐름을 결합해, “생각-행동-비평-개선”을 명시적 루프로 구현해야 한다. citeturn24academia0turn24academia2turn24academia1turn26academia1

메타인지의 실무 구현은 프롬프트 속 비밀 추론을 늘리는 것이 아니다. 오히려 \*\*외재화 가능한 점검 항목\*\*으로 바꾸는 것이다. 예를 들어 Planner는 “이 작업이 분해 가능한가”, “추가 근거가 필요한가”, “정책 승인 대상인가”, “마감 시간 내 가능한가”를 체크리스트로 출력해야 한다. Critic은 “근거 부족”, “정책 위반 가능성”, “과잉 자율성”, “형식 오류”, “재현성 부족” 같은 구조화된 비평 레이블을 남겨야 한다. 이 방식이 LangChain의 structured output, middleware, guardrails와도 정합적이다. citeturn2view0turn42view0

\#\#\# 하네스 구성 요소

LangChain 문서는 하네스를 모델, 도구, 시스템 프롬프트, 미들웨어로 정의하고, execution environment, context management, planning & delegation, fault tolerance, guardrails, steering를 핵심 concern으로 제시한다. 해마의 하네스도 같은 6층 구조를 가져야 한다. 다만 해마는 이를 \*\*작업 단위로 자동 조합\*\*해야 한다는 점이 다르다. 즉, 하네스는 정적 template가 아니라 compiled artifact다. citeturn42view0turn2view0

권장 하네스 구조는 다음과 같다.

| 층 | 내용 | 해마에서의 역할 |  
|---|---|---|  
| 모델 층 | large vs mini, reasoning vs fast | 비용/정확도 균형 |  
| 프롬프트 층 | system, role, constraints, rubric | 역할과 품질 기준 지정 |  
| 도구 층 | MCP tools, local tools, APIs | 실행 능력 제공 |  
| 기억 층 | session memory, long-term memory, skills | 반복 작업 축적 |  
| 정책 층 | risk rules, PII rules, approval rules | 결정적 강제 |  
| 관측 층 | tracing, logging, eval hooks | 운영 가능성 확보 |

해마의 하네스 컴파일러는 첨부 자료의 I-B-F 철학을 반영해, 기존 성공 패턴을 모방하고(imitation), 벤치마크와 근거를 비교하며(benchmark), 여러 결과를 융합하고(fusion), 유효 지식을 유지·갱신(maintain)하는 절차를 산출물로 만들어야 한다. 이 부분은 공개 프레임워크 문서보다 첨부 자료가 더 직접적이다. fileciteturn0file2

\#\#\# 프롬프트 엔지니어링 권장안

해마에서 프롬프트 엔지니어링은 문장 미세조정이 아니라 \*\*역할-상태-규칙-평가 기준의 구조화\*\*다. 권장 프롬프트는 최소 네 블록을 가져야 한다. \*\*정체성 블록\*\*, \*\*작업 목표 블록\*\*, \*\*운영 규칙 블록\*\*, \*\*출력 계약 블록\*\*이다. 도구 사용이 포함되면 여기에 \*\*도구 선택 기준 블록\*\*, 고위험 작업이면 \*\*승인 조건 블록\*\*, 품질 요구가 높으면 \*\*자기 점검 루브릭 블록\*\*을 추가한다. 이 접근은 ReAct의 interleaved action format, Self-Refine의 feedback/refine 루프, LangChain structured output, OpenAI guardrails·handoffs와 실무적으로 맞물린다. citeturn24academia2turn26academia1turn2view0turn4view1

\#\#\#\# 권장 시스템 프롬프트 골격

\`\`\`text  
너는 \[역할명\]이다.  
목표: \[과업 목표\]  
행동규칙:  
\- 근거가 없으면 단정하지 말 것  
\- 외부 도구 사용 전 사용 목적을 내부 계획 항목으로 명시할 것  
\- 정책위험/PII/파괴적 쓰기 작업은 승인 상태를 확인할 것  
\- 최종 출력 전 자기점검 루브릭을 수행할 것

입력 컨텍스트:  
\- TaskSpec  
\- EvidenceBundle  
\- PolicyPack  
\- MemoryPack

출력 계약:  
\- 구조화된 JSON 또는 지정 마크다운  
\- confidence, unresolved\_questions, citations/evidence\_refs 포함  
\`\`\`

이 골격에서 중요한 것은 “잘 답하라”가 아니라 “어떤 상태와 규칙 아래서 어떤 계약을 만족하라”다. LangChain과 OpenAI 모두 structured output, guardrails, runtime context를 강조하는 이유가 여기에 있다. 해마는 프롬프트를 텍스트보다 \*\*계약서\*\*로 보아야 한다. citeturn2view0turn4view4

\#\#\# 핵심 루프 의사코드

\`\`\`text  
function headmaster\_run(user\_request):  
    task \= compile\_task\_spec(user\_request)  
    policy \= load\_policy\_pack(task)  
    harness \= compile\_harness(task, policy)

    while not task.terminal:  
        step \= orchestrator.next(task, harness)

        if step.type \== "research":  
            evidence \= researcher.collect(step)  
            task.attach(evidence)

        if step.type \== "execute":  
            artifact \= executor.produce(step, task.context)  
            task.attach(artifact)

        critique \= critic.review(task)

        if critique.requires\_human\_approval:  
            await\_approval(task, critique)  
            continue

        if critique.requires\_replan:  
            harness \= revise\_harness(harness, critique)  
            task \= replan(task, critique)  
            continue

        if critique.accepted:  
            km.assimilate(task)  
            publish(task)  
            task.terminal \= true  
\`\`\`

이 구조는 OpenAI Agents SDK의 built-in loop 철학, LangGraph의 evaluator-optimizer와 orchestration capabilities, 첨부 자료의 Critic/KnowledgeManager 분리, Reflexion/Self-Refine의 피드백 루프를 절충한 것이다. fileciteturn0file1 fileciteturn0file2 citeturn4view0turn23view1turn24academia1turn26academia1

\#\# 지식관리와 자가발전 메커니즘

\#\#\# 지식 객체 설계

해마의 지식관리는 단순 벡터 검색이 아니다. 첨부 자료의 KnowledgeManager가 시사하듯, 해마는 결과물을 \*\*재사용 가능한 제도화 지식\*\*으로 변환해야 한다. 권장 지식 객체는 다섯 가지다. \*\*MemoryItem\*\*은 과업 중 얻은 사실·결정·선호를 담고, \*\*Skill\*\*은 반복 가능한 절차를 담으며, \*\*PromptPack\*\*은 역할별 지침 묶음이고, \*\*PolicyPatch\*\*는 운영 중 확인된 정책 개선점을 기록하며, \*\*BenchmarkCase\*\*는 회귀평가용 테스트 케이스를 저장한다. fileciteturn0file1 fileciteturn0file2

LangChain은 context management에서 summarization, memory, skills, prompt caching을 하네스 핵심으로 설명하고, Deep Agents는 장기 작업에서 filesystem, summarization, subagents, prompt caching을 기본 제공한다고 설명한다. 해마는 이 기능들을 개별 에이전트에 흩뿌리지 말고, KnowledgeManager가 작업 종료 시 \*\*무엇이 세션 기억으로 남고, 무엇이 장기 스킬로 승격되고, 무엇이 폐기되는지\*\*를 판정하도록 설계해야 한다. citeturn42view0turn7view0

\#\#\# 자가발전 루프

자가발전은 “모델을 알아서 더 똑똑하게 만들기”가 아니라, \*\*운영 경험을 지식과 평가셋으로 전환해 다음 실행을 더 낫게 만드는 것\*\*이다. Reflexion은 reflective text를 episodic memory로 저장해 다음 시도를 개선했고, Self-Refine은 feedback/refinement를 반복했고, OPRO는 언어모델을 최적화자처럼 사용해 프롬프트를 개선했다. 해마의 자가발전 루프는 이 세 가지를 통합해 다음 네 단계로 설계하는 것이 적절하다. \*\*관측\*\*, \*\*진단\*\*, \*\*패치 제안\*\*, \*\*검증 후 승격\*\*이다. citeturn24academia1turn26academia1turn26academia3

권장 승격 규칙은 보수적이어야 한다. 즉, 어떤 PromptPack이나 Skill이 한두 번 잘 동작했다고 바로 기본값이 되면 안 된다. 최소한 benchmark set과 최근 production traces에서 \*\*정확도 개선, 비용 악화 없음, 안전성 저하 없음\*\*을 만족한 뒤 promotion 해야 한다. 첨부 자료의 reverse proposal과 benchmark 지향성은 이 promotion gate를 강하게 지지한다. fileciteturn0file2

\#\#\# 버전관리와 평가 설계

해마는 아래 대상에 대해 모두 버전을 가져야 한다.

| 버전 대상 | 예시 |  
|---|---|  
| PromptPack | \`critic\_pack@2026-06-10-r3\` |  
| PolicyPack | \`privacy\_pack@ko-enterprise-v2\` |  
| Skill | \`citation\_validation\_skill@1.4.2\` |  
| Harness Template | \`research\_report\_harness@v0.9\` |  
| Benchmark Set | \`safety\_regression\_suite@2026Q2\` |  
| Agent Capability Profile | \`researcher\_capability@mini+web+mcp\` |

버전은 단순 git tag가 아니라 \*\*실행적 의미\*\*를 가져야 한다. 즉 이 버전이 어떤 traces에서 학습되었는지, 어떤 벤치마크를 통과했는지, 어느 정책 패키지와 호환되는지 메타데이터를 가져야 한다. OpenAPI, JSON Schema, OpenTelemetry, Temporal-style replay, LangSmith-style tracing을 함께 쓰면 이 호환성 정보를 기계적으로 연결하기 쉬워진다. citeturn40view0turn41view0turn10view0turn8view0turn23view4

\#\#\# 검증 체계와 테스트 케이스

AgentBench는 장기 추론·의사결정·instruction following을, MultiAgentBench는 협업·경쟁·마일스톤 기반 KPI를, Agent-SafetyBench는 다중 환경에서의 안전 실패 모드를 강조한다. 해마의 테스트도 이 세 관점을 모두 가져야 한다. 즉 \*\*기능 테스트\*\*, \*\*협업 테스트\*\*, \*\*안전 테스트\*\*, \*\*운영 회복 테스트\*\*, \*\*경제성 테스트\*\*가 모두 있어야 한다. citeturn24academia3turn25academia0turn26academia0

| 테스트 ID | 목적 | 입력 조건 | 기대 결과 | 비고 |  
|---|---|---|---|---|  
| TC-FUNC-REQ | 과업 분류 정확성 | 단일 질의, 명확한 목적 | 올바른 하네스 템플릿 선택 | 라우팅 테스트 |  
| TC-FUNC-DECOMP | 작업 분해 품질 | 멀티파트 보고서 요청 | 섹션/하위작업 분해 성공 | orchestrator-worker |  
| TC-FUNC-CITE | 근거 결합 품질 | 웹/문서 혼합 작업 | 근거 누락 없이 artifact 생성 | citation completeness |  
| TC-SAFE-PII | PII 차단 | 개인정보 포함 입력 | 마스킹 또는 승인 대기 | guardrail |  
| TC-SAFE-INJ | 프롬프트 인젝션 방어 | 악성 도구 응답 | 실행 중단 또는 격리 | OWASP/MCP 위협 |  
| TC-SAFE-AGENCY | 과도한 권한 요청 | destructive tool 포함 | human approval gate 진입 | high-impact action |  
| TC-OPS-RETRY | 일시적 API 실패 | timeout/rate limit | 재시도 후 복구 | fault tolerance |  
| TC-OPS-REPLAY | 런타임 크래시 | 중간 이벤트 이후 장애 | event history로 재개 | durable execution |  
| TC-COST-ESC | 모델 승격 억제 | 반복적인 critic fail | 상위모델 승격 횟수 한도 준수 | budget control |  
| TC-KNOW-ASSIM | 지식 승격 품질 | 성공/실패 traces | 유효 skill만 장기 저장 | contamination 방지 |

해마의 테스트 자동화는 “답변 비교”보다 “이벤트 시퀀스 비교”를 더 많이 써야 한다. 어떤 과업은 여러 정답이 가능하므로 artifact 자체보다 \*\*정책 준수, 증거 충족, 상태 수렴, 비용 상한 준수\*\*가 더 중요한 판정 기준일 수 있다. 이는 MultiAgentBench의 milestone-based KPIs와 잘 맞는다. citeturn25academia0

\#\#\# 성능 지표 권장안

권장 성능 지표는 다음과 같다.

| 분류 | 지표 | 정의 |  
|---|---|---|  
| 품질 | Task Success Rate | 승인된 완료 비율 |  
| 품질 | Evidence Sufficiency Score | 최종 주장 대비 근거 충족도 |  
| 품질 | Critic Catch Rate | 결함 중 critic이 선제 탐지한 비율 |  
| 운영 | Median Task Latency | 요청\~완료 중앙값 |  
| 운영 | Recovery Success Rate | 장애 후 정상 재개 비율 |  
| 운영 | Handoff Precision | 올바른 specialist 전환 비율 |  
| 경제성 | Cost per Accepted Task | 승인된 작업 1건당 총비용 |  
| 경제성 | Model Escalation Rate | mini→large 승격 비율 |  
| 안전 | Policy Violation Escape Rate | 위반이 최종 산출물까지 통과한 비율 |  
| 안전 | Prompt Injection Containment Rate | 악성 입력이 격리된 비율 |

이 중 Evidence Sufficiency, Critic Catch, Model Escalation은 해마 전용 지표로 특히 중요하다. 첨부 자료가 강조하는 critic과 knowledge 축이 잘 작동하는지 보려면 단순 성공률만으로는 부족하기 때문이다. 또한 Agent-SafetyBench가 agents safety score가 아직 낮다고 지적한 만큼, 안전 지표는 별도 대시보드와 릴리즈 게이트를 가져야 한다. fileciteturn0file2 citeturn26academia0

\#\#\# 성능과 비용 추정

아래 표는 \*\*가정 기반 예시\*\*다. 조직별 토큰 사용 패턴, 평균 산출물 크기, 캐시 비율, 배치 사용 여부가 미지정이므로 실제 예산 총액은 미지정이다. 다만 현재 OpenAI API 가격표 기준으로 GPT-5.4 mini 입력은 1M tokens당 \\$0.75, 출력은 \\$4.50, GPT-5.4 입력은 \\$2.50, 출력은 \\$15.00, 웹 검색은 1,000 calls당 \\$10, containers는 1GB당 20분 세션 \\$0.03 수준이다. Batch API는 입력·출력 비용을 50% 절감할 수 있다. citeturn18view0

가정한 “표준 해마 작업”은 다음과 같다. planner/router/worker에서 mini 입력 100k, 출력 15k, critic/final synthesis에서 large 입력 60k, 출력 11k, web search 2회, 1GB 컨테이너 1세션을 사용한다. 그러면 작업 1건당 대략적인 API 원가는 약 \\$0.51 수준이다. 이 수치는 \*\*예시 계산값\*\*이며 실제 운영과 동일하지 않다. citeturn18view0

| 시나리오 | 월 작업 수 | 예상 월 원가 | 비고 |  
|---|---:|---:|---|  
| PoC | 1,000 | 약 \\$510 | 배치 미사용 |  
| 팀 단위 운영 | 10,000 | 약 \\$5,100 | 배치 미사용 |  
| 조직 단위 운영 | 50,000 | 약 \\$25,500 | 배치 미사용 |  
| 비동기 보고서형 워크로드 | 10,000 | 약 \\$3,000 전후 | Batch 일부 적용 시 절감 가능 |

운영비를 줄이는 최선의 방법은 모델 단가보다 \*\*토폴로지 선택\*\*이다. 즉, 모든 단계에 상위 모델을 쓰지 말고, router/planner 일부와 worker는 mini로, critic/final synthesis만 상위 모델로 쓰는 것이 해마 구조상 가장 효과적이다. LangChain과 OpenAI 문서가 모두 하위 역할과 상위 역할을 분리 가능한 primitive로 제공하는 이유도 비용-품질 분화 때문이다. citeturn42view0turn4view0

\#\# 보안, 프라이버시, 윤리, 배포와 운영

\#\#\# 위협 모델과 완화 전략

OWASP는 LLM 기반 시스템의 대표 위험으로 Prompt Injection, Insecure Output Handling, Training Data Poisoning, Model DoS, Supply Chain Vulnerabilities, Sensitive Information Disclosure, Insecure Plugin Design, Excessive Agency, Overreliance, Model Theft를 제시한다. 해마는 그중에서도 특히 \*\*Prompt Injection, Insecure Output Handling, Excessive Agency, Sensitive Information Disclosure, Supply Chain Vulnerabilities\*\*에 취약하다. 이유는 해마가 외부 도구와 장기 메모리, 다중 에이전트 협업, 파일·코드 실행을 결합하기 때문이다. citeturn36view0turn36view1turn36view2

MCP 관련 연구는 tool poisoning, prompt injection, unintended privacy disclosure, maintainability 문제를 별도 취약점으로 지적한다. 따라서 MCP를 쓰는 경우 “표준이라서 안전하다”는 오해를 버려야 한다. MCP는 연결 표준이지 보안 완성품이 아니다. 해마는 MCP 서버를 직접 신뢰하지 말고, \*\*tool allowlist, argument validation, output quarantine, permission scopes, sandbox transport policy, server health scoring\*\*을 사용해야 한다. citeturn16academia4turn11academia1

권장 완화 전략은 아래와 같다.

| 위험 | 권장 통제 |  
|---|---|  
| Prompt Injection | tool input sanitization, trusted context separation, tool-origin labeling |  
| Insecure Output Handling | 출력 검역, structured output validation, executable content 차단 |  
| Excessive Agency | 승인 게이트, capability scopes, write-action lease |  
| Sensitive Information Disclosure | PII middleware, redaction, retrieval scope control |  
| Supply Chain Risk | MCP/A2A/툴 registry 신뢰등급, 서명 검증, health score |  
| Memory Poisoning | 장기 기억 승격 전 benchmark gate와 human review |  
| Model DoS | 토큰 상한, 단계별 call limit, timeout budget |  
| Model Theft / Leakage | artifact watermarking, credential isolation, workspace scoping |

LangChain이 guardrails와 steering을 prompt 바깥의 deterministic control로 다루고, OpenAI Agents SDK가 guardrails와 human-in-the-loop를 기본 primitive로 두며, OWASP GenAI Security Project가 autonomous agents와 multi-step workflows를 별도 security initiative로 다루는 것은 해마의 안전 제어가 모델 바깥 아키텍처여야 함을 다시 확인시켜 준다. citeturn42view0turn4view1turn35view0

\#\#\# 프라이버시와 윤리

프라이버시는 법률·업종 규제·계약 조건에 강하게 의존하므로, 현 시점에서 조직별 세부 준수 기준은 \*\*미지정\*\*이다. 다만 원칙은 분명하다. 개인정보와 민감정보는 최소수집·목적제한·보존기한·접근통제·감사추적을 가져야 하며, 에이전트가 장기기억에 승격할 수 있는 데이터 범위를 별도 정책으로 제한해야 한다. LangChain의 PII middleware, OpenAI Agents SDK의 guardrails, OWASP의 Sensitive Information Disclosure 위험, 한국 PIPC의 최근 AI 서비스 개인정보 준수 집행 사례는 해마가 프라이버시를 단순 로그 관리 문제가 아니라 제품 설계 문제로 봐야 함을 보여준다. citeturn42view0turn4view1turn36view1turn34news0

윤리적으로는 세 가지가 중요하다. 첫째, \*\*과잉 위임 방지\*\*다. 인간 승인 없는 고위험 행위는 제한해야 한다. 둘째, \*\*설명 가능성\*\*이다. 해마는 왜 어떤 에이전트를 선택했고 왜 어떤 툴을 썼는지 추적할 수 있어야 한다. 셋째, \*\*과신 방지\*\*다. OWASP가 Overreliance를 독립 위험으로 분류한 것처럼, 사용자가 “해마가 말했으니 맞다”고 판단하게 만드는 UX는 피해야 한다. 해마는 confidence, unresolved questions, evidence refs를 항상 노출하는 쪽이 맞다. citeturn36view1

\#\#\# 배포, 운영, 유지보수

운영 인프라는 소규모에서는 LangGraph/OpenAI Agents SDK 기반 앱 서버 \+ event bus \+ trace store \+ vector/document store 조합으로 시작할 수 있고, 중대형 규모에서는 Kubernetes \+ workflow engine \+ observability stack이 유리하다. Kubernetes는 automated rollouts, rollbacks, self-healing, secret/config management를 제공하며, Prometheus는 시계열 metric 수집/alerting에 강하고, OpenTelemetry는 traces/metrics/logs를 vendor-neutral하게 다룰 수 있다. Temporal은 years-long resilient workflows와 event history replay를 제공하므로, 장시간·재시도 많은 해마 작업에 적합하다. citeturn9view0turn9view1turn10view0turn10view2turn10view3turn8view0

권장 운영 형태는 다음과 같다.

\`\`\`mermaid  
flowchart TD  
    LB\[API Gateway\] \--\> APP\[Headmaster API\]  
    APP \--\> CTRL\[Control Plane\]  
    CTRL \--\> BUS\[Event Bus\]  
    CTRL \--\> WF\[Workflow Runtime\]  
    WF \--\> SBOX\[Sandbox Pool\]  
    WF \--\> TOOLS\[MCP / internal tools\]  
    WF \--\> MEM\[Knowledge Store\]  
    WF \--\> DB\[State DB\]

    APP \--\> OBS\[OTel Collector\]  
    OBS \--\> PROM\[Prometheus\]  
    OBS \--\> TRACE\[Trace Backend\]  
    OBS \--\> LOG\[Audit Log\]  
\`\`\`

유지보수는 코드보다 \*\*정책, 프롬프트, 스킬, 벤치마크\*\* 변경이 더 잦을 가능성이 높다. 따라서 해마는 코드 배포 파이프라인뿐 아니라 하네스 배포 파이프라인을 별도로 가져야 한다. PromptPack과 Skill은 semver 유사 규칙을 따르고, 승격 전 replay set과 safety regression set을 통과해야 한다. 이 점에서 CrewAI의 flows/processes/guardrails/observability, AutoGen의 event-driven core, LangChain의 middleware stack은 좋은 참조가 된다. citeturn37view1turn37view0turn42view0

\#\#\# 유사 시스템과 표준 비교

\#\#\#\# 프레임워크 및 런타임 비교

| 옵션 | 강점 | 한계 | 해마 적합성 |  
|---|---|---|---|  
| LangChain \+ LangGraph \+ Deep Agents | framework/runtime/harness 구분이 명확하고, middleware·durable execution·subagents·context management가 잘 분해되어 있다. citeturn7view0turn23view3turn42view0 | 생태계 선택지가 많아 표준 운영 규율이 없으면 구성 분산 위험이 있다. | 매우 높음 |  
| OpenAI Agents SDK | Agents, Handoffs, Guardrails, Tracing 등 핵심 primitive가 단순하고 실무적이다. citeturn4view0turn4view1 | OpenAI 중심 런타임 추상에 상대적으로 가까워 이식성 설계가 필요하다. | 높음 |  
| AutoGen | AgentChat/Core/Extensions 구조와 event-driven multi-agent 설계가 강점이다. citeturn37view0turn26academia2 | 정책 강제와 운영 거버넌스는 별도 설계가 더 필요하다. | 높음 |  
| CrewAI | agents/crews/flows, hierarchical/sequential/hybrid processes, enterprise automations가 강점이다. citeturn37view1 | 대규모 상태 재현·프로토콜 표준화는 추가 판단이 필요하다. | 중\~높음 |  
| Temporal 기반 커스텀 | durable workflow, replay, deterministic recovery가 강력하다. citeturn8view0 | 에이전트 추상은 직접 설계해야 한다. | 대형 운영에 높음 |

이 비교에서 결론은 분명하다. 해마는 특정 프레임워크를 그대로 제품명만 바꾸어 쓰는 방식으로 구현하면 안 된다. 오히려 \*\*LangGraph/Temporal형 런타임 안정성 \+ OpenAI/LangChain형 에이전트 primitives \+ MCP/A2A/ACP형 개방 표준\*\*을 결합하는 쪽이 해마의 정의에 더 가깝다. 해마의 고유 가치는 모델 공급자나 프레임워크 선택이 아니라, 작업 맞춤형 하네스 설계, 정책 집행, 지식 환류에 있기 때문이다. citeturn7view0turn4view0turn8view0turn39view0turn22view0turn21view0

\#\#\#\# 프로토콜 비교

| 프로토콜 | 초점 | 전송/형식 | 해마에서의 역할 |  
|---|---|---|---|  
| MCP | 모델/에이전트와 도구·데이터·프롬프트 연결 | JSON-RPC 2.0, stdio/HTTP, tools/resources/prompts | 툴 계층 표준 |  
| A2A | 독립 에이전트 간 peer collaboration과 task lifecycle | JSON-RPC 2.0 over HTTP(S), SSE, AgentCard | 외부 에이전트 협업 |  
| ACP | REST 친화적 agent interoperability | RESTful API, MIME types, async-first | 기업 내 REST 통합/호환 어댑터 |

A2A 공식 문서는 MCP와 A2A가 complementary라고 명시한다. MCP는 capability/resource use의 “how-to”, A2A는 independent agents가 partner/delegate하는 “collaboration protocol”이라는 설명은 해마 설계에 매우 중요하다. 해마는 이 둘을 경쟁 대안으로 보지 말고, \*\*도구 연결은 MCP, 에이전트 협업은 A2A\*\*로 분리하는 것이 가장 자연스럽다. ACP는 REST 중심 조직에서 bridging layer로 활용할 수 있다. citeturn22view0turn22view2turn21view0

\#\#\# 위험 분석

| 위험 | 영향 | 가능성 | 대응 |  
|---|---|---|---|  
| 하네스 과복잡화 | 운영 불안정, 설명 불가 | 높음 | 템플릿 최소화, capability registry 도입 |  
| 프롬프트 인젝션 | 잘못된 툴 실행, 데이터 유출 | 높음 | 출력 검역, trusted context 분리, sandbox |  
| 메모리 독성 축적 | 잘못된 장기지식 강화 | 중\~높음 | 승격 게이트, benchmark replay |  
| 과잉 자율성 | 무단 쓰기/비용 폭주 | 중\~높음 | approval gate, capability scope |  
| 품질 회귀 | 자동 개선이 성능 악화 | 중간 | canary release, regression suite |  
| 비용 급등 | 운영 중단 | 중간 | escalation cap, budget policy, batch |  
| 툴/표준 종속 | 벤더 락인 | 중간 | MCP/A2A/OpenAPI 채택 |  
| 장시간 작업 실패 | state loss, 중복 실행 | 중간 | event history, replay, idempotency |

이 위험표에서 가장 본질적인 것은 “해마가 성공할수록 위험도 함께 커진다”는 점이다. 자율성이 커질수록 결함의 범위도 커지므로, 해마는 기능 확장보다 통제 확장을 먼저 해야 한다. 특히 OWASP의 Excessive Agency와 MCP 보안 연구는 권한 통제가 후행 과제가 아님을 강하게 보여준다. citeturn36view1turn16academia4turn11academia1

\#\#\# 구현 로드맵

\#\#\#\# 단계별 산출물

| 단계 | 목표 | 핵심 산출물 | 예상기간 | 예산 |  
|---|---|---|---|---|  
| 발견 단계 | 개념 정제와 요구사항 명문화 | TaskSpec, PolicySpec, Capability Registry 초안 | 3\~4주 | 미지정 |  
| 핵심 구현 단계 | 제어 평면과 기본 런타임 구축 | Task Compiler, Topology Selector, Orchestrator Runtime, Critic MVP | 6\~8주 | 미지정 |  
| 확장 단계 | 지식관리·안전·관측성 추가 | KnowledgeManager, Approval Gateway, OTel/Prometheus, replay/eval | 6\~10주 | 미지정 |  
| 운영화 단계 | 프로덕션 내구성 확보 | Kubernetes/Temporal 통합, regression suite, RBAC, SRE runbook | 8\~12주 | 미지정 |

예상기간은 일반적인 소규모 전담팀을 가정한 설계적 추정이며, 실제 인력 수·기술 숙련도·기존 자산에 따라 크게 달라질 수 있다. 인건비 단가와 인프라 조달 방식이 미지정이므로 총 예산은 미지정으로 표기한다. citeturn8view0turn9view0turn10view0

\#\#\#\# 간트형 타임라인

\`\`\`mermaid  
gantt  
    title 해마 구현 권장 타임라인  
    dateFormat  YYYY-MM-DD  
    axisFormat  %m/%d

    section 발견  
    요구사항 정제 및 정책 명세      :a1, 2026-06-15, 21d  
    Capability Registry 초안 작성   :a2, after a1, 10d

    section 핵심 구현  
    Task Compiler / Harness Compiler :b1, 2026-07-10, 28d  
    Orchestrator Runtime MVP         :b2, 2026-07-20, 35d  
    Critic / Approval Gateway        :b3, 2026-08-01, 21d

    section 확장  
    KnowledgeManager / Versioning    :c1, 2026-08-20, 28d  
    OTel / Prometheus / Replay       :c2, 2026-08-25, 28d  
    Safety Regression Suite          :c3, 2026-09-05, 21d

    section 운영화  
    Kubernetes / Workflow Engine     :d1, 2026-09-20, 35d  
    Canary Release / Runbook         :d2, 2026-10-05, 21d  
    Production Readiness Review      :d3, 2026-10-25, 14d  
\`\`\`

\#\# 결론과 오픈 질문

해마를 구현하는 가장 올바른 방법은 “강한 모델 하나 \+ 길어진 프롬프트”가 아니라, \*\*작업을 해석하고, 그 작업에 맞는 에이전트 환경 전체를 설계하는 메타 시스템\*\*으로 접근하는 것이다. 첨부 자료의 오케스트레이터 하네스 철학, 역할 분리, 비평-지식관리 구조는 이 방향을 강하게 지지한다. 공개 생태계에서는 LangGraph가 durable execution과 상태 기반 오케스트레이션, LangChain이 하네스 concern 분해, OpenAI Agents SDK가 단순하면서 실용적인 primitive 설계, MCP/A2A/ACP가 상호운용 표준, Temporal/Kubernetes/OpenTelemetry/Prometheus가 운영 기반을 제공한다. 해마의 설계는 이 요소들을 한데 묶되, 고유 가치를 “작업별 하네스 자동 설계와 운영 규율”에 둬야 한다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 citeturn7view0turn4view0turn39view0turn22view0turn8view0turn10view0

최종적으로 권장하는 구현 원칙은 다섯 가지다. \*\*증거 우선\*\*, \*\*역할 분리\*\*, \*\*상태 명시화\*\*, \*\*정책의 결정적 강제\*\*, \*\*지식의 승격 검증\*\*이다. 이 다섯 가지가 지켜지지 않으면 해마는 “오케스트라를 설계하는 단장”이 아니라 “에이전트를 여러 개 붙인 복잡한 챗봇”으로 전락할 가능성이 높다. 반대로 이 다섯 가지가 지켜지면, 해마는 복잡한 지식작업과 운영 자동화에서 재현성, 설명 가능성, 비용 통제, 안전성을 함께 잡는 실질적 오케스트레이션 시스템이 될 수 있다. citeturn24academia2turn24academia1turn26academia1turn36view1turn26academia0

\#\#\# 오픈 질문과 한계

현재 명세상 다음 항목들은 여전히 \*\*미지정\*\*이며, 실제 구현 전에 조직별 결정이 필요하다. 대상 도메인 범위, 데이터 분류 정책, 멀티테넌시 방식, 승인 대상 작업 목록, 규제 준수 범위, 배포 모델, 예산 상한, SLA, 외부 통합 인벤토리, 장기 기억에 저장 가능한 데이터 범위가 그것이다. 이 항목들은 아키텍처의 골격을 바꾸지는 않지만, 정책 팩과 운영 모델을 크게 바꾼다. 특히 프라이버시와 고위험 승인 기준은 법무·보안·업무 오너가 함께 확정해야 한다. 한국 개인정보·AI 규제 적용의 세부 해석은 조직별 법적 검토가 추가로 필요하다. citeturn34news0turn35view0  
