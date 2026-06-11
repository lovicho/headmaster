\# 해마 시스템 심층 연구 보고서

\#\# 요약

이 보고서는 사용자가 정의한 해마를 “뇌의 해마처럼 맥락과 기억을 다루면서도, 오케스트라의 단장처럼 다중 에이전트를 설계·지휘·검증하여 목적 지향 작업을 완수하는 시스템”으로 규정하고, 첨부파일 세 종을 핵심 설계 원전으로 삼아 구현 가능한 참조 아키텍처와 운영 모델을 제안한다. 첨부자료는 해마를 단순한 챗봇이나 단일 거대 에이전트가 아니라, 증거-우선 실행, 단계 게이트, 비평·검증 루프, 유지 단계까지 포함한 “하네스 중심 시스템”으로 서술한다. 특히 \`No Zero-Shot Invention\`, I-B-F 루프, \`English-Core / Korean-Edge\`, 구조화된 증빙 번들, 에이전트별 proof·verification 인터페이스, 오류·재시도·유지보수의 명시적 상태 관리가 해마의 핵심 원칙으로 제시되어 있다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2

문헌과 상용 플랫폼을 종합하면, 해마는 “하나의 초거대 에이전트”가 아니라 “제어면·실행면·기억면·정책면·관측면이 분리된 에이전트 운영체제”에 가깝다. LangGraph는 장수명·상태형 에이전트의 persistence, memory, human-in-the-loop, fault tolerance를 강조하고, OpenAI Agents SDK는 agent, handoff, guardrails, sessions, tracing이라는 최소 원시구성 요소를 제시하며, Temporal은 durable/reliable/scalable workflow와 replay·event history를 제공한다. MCP는 도구·데이터·워크플로 연결 표준, A2A는 에이전트 간 capability discovery·task lifecycle·artifact 교환 표준으로 자리 잡고 있다. 따라서 해마의 현실적 구현은 \*\*오케스트레이션 런타임 \+ 증거형 메모리 \+ 프로토콜 게이트웨이 \+ 관측·평가 \+ 안전정책 엔진\*\*의 결합이어야 한다. citeturn6view2turn6view1turn5view0turn5view1turn12view1

본 보고서의 핵심 결론은 다섯 가지다. 첫째, 해마의 본질은 “계획을 세우는 LLM”이 아니라 \*\*증거와 상태를 보존하면서 다중 에이전트 협업을 안전하게 지속시키는 하네스\*\*다. 둘째, 기억은 단일 벡터DB가 아니라 \*\*단기 작업기억, 에피소드 기억, 의미 기억, 기술 기억, 증빙 기억\*\*으로 계층화되어야 하며, 이는 해마의 빠른 에피소드 부호화와 느린 장기 일반화라는 신경과학적 비유와도 잘 맞는다. 셋째, 프로토콜은 내부 도구 연결에는 MCP, 외부 에이전트 위임에는 A2A, 내부 이벤트 전파에는 JetStream형 메시지 버스, 장기 작업 재실행에는 Temporal형 워크플로 엔진을 조합하는 것이 합리적이다. 넷째, 해마의 성패는 모델 성능보다 \*\*검증·재현 가능성·비용 통제·보안·장기기억 관리\*\*에 더 크게 좌우된다. 다섯째, 최근 연구는 모든 절차형 업무에 외부 오케스트레이션이 항상 이득이 아님을 보여 주므로, 해마는 “항상 다중 에이전트”가 아니라 \*\*조건부 오케스트레이션\*\*을 채택해야 한다. citeturn14academia0turn22view0turn25academia1turn21academia2turn1academia5

따라서 본 보고서는 해마의 권장 구현을 다음과 같이 제안한다. 사용자 요청은 먼저 목표·제약·증거요구 수준으로 정규화된다. 해마는 기억층에서 관련 에피소드와 정책을 불러오고, Registry에서 적절한 agent ensemble을 선택하며, Scheduler가 예산·기한·리스크에 맞춰 작업을 분할·배치한다. 각 에이전트는 도구 호출과 부분 산출물을 생성하지만, 모든 산출물은 Critic·Verifier·Policy Gate를 통과해야만 다음 단계로 승격된다. 완료된 결과는 Artifact와 Evidence Bundle로 저장되고, 이후 Consolidator가 에피소드 기억을 장기 의미 기억과 기술 라이브러리로 승화한다. 이는 첨부파일의 evidence-first 철학과 최신 agent runtime·memory 연구 모두에 부합한다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 citeturn6view2turn6view1turn5view0turn20academia3turn25academia2

본 보고서는 이 결론을 바탕으로 목적·범위·요구사항, 참조 아키텍처, 에이전트 설계, 기억 구조, 작업 플로우, API·데이터 스키마, 상태 머신, 알고리즘, 검증 지표, 구현 로드맵, 비교 분석, 위험과 한계까지 명세 수준으로 제시한다. 사용자가 실제로 구현 가능한 수준의 문서를 목표로 했기 때문에, 아래 내용은 단순 해설보다는 \*\*설계 사양서와 운영 보고서의 중간 형식\*\*으로 작성되었다. fileciteturn0file0

\#\# 연구 배경과 해마의 개념 정립

사용자 정의의 해마는 이름부터 두 겹의 의미를 갖는다. 하나는 뇌의 해마처럼 경험을 에피소드로 저장하고, 필요할 때 단서 기반으로 재구성하는 기억 장치라는 뜻이다. 다른 하나는 오케스트라의 단장 혹은 지휘자처럼 여러 전문 연주자, 즉 여러 에이전트를 조율하여 하나의 공연, 즉 하나의 목적 지향 작업을 완성하는 조직 원리라는 뜻이다. 이 이중 비유는 임의의 마케팅적 네이밍이 아니라, 실제 시스템 설계에서 \*\*기억 메커니즘과 오케스트레이션 메커니즘을 같은 상위 개념 아래 묶어야 한다\*\*는 요구를 내포한다. 첨부파일들은 바로 이 지점을 하네스, 게이트, 증빙, 검증, 유지 단계라는 실행 규율로 구체화하고 있다. fileciteturn0file0 fileciteturn0file2

첨부자료가 제시하는 해마의 가장 중요한 철학은 “모델이 똑똑하다고 해서 시스템이 신뢰가능해지지는 않는다”는 점이다. 개별 에이전트 하네스 문서는 에이전트가 단순히 답을 내는 존재가 아니라, 자신의 작업 맥락, 증명 산출물, 검증 결과, 오류 상태를 구조화된 형식으로 보고해야 하는 실행 단위임을 강조한다. 마스터 오케스트레이터 하네스 문서는 오케스트레이터가 서브에이전트를 무제한 호출하는 허브가 아니라, 단계별 판단·증빙 수집·검증·통합을 수행하는 상위 제어기임을 전제한다. 즉 해마는 “대화형 AI”보다 “멀티에이전트 운영체계”에 가깝다. fileciteturn0file1 fileciteturn0file2

이 개념은 최근 에이전트 연구와도 맞물린다. ReAct는 reasoning과 acting을 교차시키며 도구 및 환경 상호작용을 통해 환각과 잘못된 계획을 줄일 수 있음을 보였고, Toolformer는 모델이 어떤 도구를 언제 어떤 인자와 함께 호출해야 하는지를 학습할 수 있음을 보였다. CAMEL, AutoGen, MetaGPT, ChatDev는 역할 분리와 대화적 협업이 복잡 작업을 해결하는 유력한 패턴임을 보여 주지만, 동시에 이들 시스템은 역할 오염, 캐스케이딩 hallucination, 종료 조건의 불명확성, 검증 부재라는 문제도 드러냈다. 첨부파일의 \`No Zero-Shot Invention\`과 proof bundle 요구는 바로 이런 실패 양상에 대한 공학적 대응으로 해석할 수 있다. citeturn23academia0turn23academia1turn23academia2turn23academia3turn24academia3turn24academia1

해마를 뇌의 해마와 연결하는 비유도 단순 수사가 아니다. Generative Agents는 observation, planning, reflection이 장기적으로 축적될 때 에이전트 행동이 더 일관되고 설득력 있게 유지된다고 보였고, Reflexion은 언어적 피드백을 에피소드 기억 버퍼로 유지함으로써 다음 시행의 성능을 높일 수 있음을 보였다. MemoryBank는 장기 기억을 시간과 중요도에 따라 강화·망각시키는 메커니즘을 도입했고, MemGPT는 운영체제의 가상 메모리처럼 빠른 메모리와 느린 메모리 사이를 오가며 긴 맥락 제약을 해결하려 했다. 최근 Agentic Memory는 STM과 LTM을 별개 휴리스틱이 아니라 agent policy의 일부로 통합하려고 한다. 이는 해마가 “컨텍스트 창을 늘리는 기술”이 아니라 “무엇을 지금 들고 있고, 무엇을 나중에 불러오며, 무엇을 버릴지 결정하는 기억 정책”이어야 함을 시사한다. citeturn14academia0turn20academia0turn20academia3turn22view0turn25academia2

신경과학 유비를 더 엄밀하게 정리하면 다음과 같다. 해마형 시스템은 첫째, 새로운 사건을 빠르게 에피소드로 부호화해야 한다. 둘째, 유사한 사건끼리 혼동되지 않도록 pattern separation에 해당하는 메커니즘을 가져야 한다. 셋째, 일부 단서만으로도 관련 사건을 복원하는 pattern completion이 가능해야 한다. 넷째, 반복 재생과 반성을 통해 장기 의미 기억과 기술 기억으로 느리게 공고화해야 한다. 텐서 메모리 가설과 해마 계산모형 연구는 에피소드 기억이 의미 기억 형성을 가르치는 구조, 해마의 one-shot 시퀀스 저장, 단일 단서로 인한 회상, DG 기반 pattern separation, “dreaming”에 가까운 self-bootstrapping을 제안한다. 이로부터 해마 시스템의 기억 설계는 \*\*빠른 에피소드 쓰기 \+ 신뢰도·유사도 기반 분리 \+ 단서 기반 재호출 \+ 느린 의미화\*\*라는 네 층 원리 위에 서야 한다. citeturn17academia4turn18academia5turn19academia0

그러나 최신 연구는 오케스트레이션의 가치가 만능은 아니라고 경고한다. 2026년의 비교 연구는 일정한 절차를 따르는 procedural task에서 외부 오케스트레이션 프레임워크가 때로는 단일 모델의 in-context self-orchestration보다 열등할 수 있음을 보고했다. 따라서 해마는 “항상 멀티에이전트”가 아니라, \*\*긴 시간축, 많은 도구, 신뢰성 요구, 다중 역할 분업, 인간 승인 필요성\*\*이 높은 경우에만 오케스트레이션 비용을 지불해야 한다. 절차가 짧고 변이성이 낮은 작업에서는 단일 agent 혹은 even no-agent path가 더 낫다. 이 판단 원리 자체가 해마의 메타정책이어야 한다. citeturn1academia5

이러한 배경을 종합하면, 해마의 정의는 다음처럼 정리된다. \*\*해마는 목적 지향 작업을 위해 다중 에이전트를 동적으로 구성하고, 작업 상태·증거·결정 근거·기억을 계층적으로 관리하며, 검증과 인간 개입을 통해 결과의 정확성과 책임성을 보장하는 상태형 오케스트레이션 시스템\*\*이다. 사용자의 첨부파일은 그 실천적 규약을, 최신 연구와 플랫폼 문서는 그 구현 가능한 수단을 제공한다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 citeturn6view2turn6view1turn5view0turn5view1

\#\#\# 해마의 설계 원칙

해마의 구현 원칙은 다음 여덟 축으로 요약할 수 있다. 첫째, 모든 결과는 증빙을 동반해야 한다. 둘째, 에이전트는 역할·상태·권한이 분리되어야 한다. 셋째, 오케스트레이터는 텍스트 생성기가 아니라 상태 전이 관리자여야 한다. 넷째, 기억은 단일 저장소가 아니라 계층형 정책 시스템이어야 한다. 다섯째, 장기 작업은 재실행 가능해야 한다. 여섯째, 비용과 지연은 예산 관리 대상이어야 한다. 일곱째, 보안은 프롬프트 수준이 아니라 프로토콜·도구·메모리 수준까지 확장되어야 한다. 여덟째, 인간 감독은 예외가 아니라 고위험 단계의 기본 제어장치여야 한다. 이 원칙은 첨부파일의 운영 규율과 최신 agent runtime·security·memory 연구의 공통분모다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 citeturn6view2turn6view1turn30view0turn30view3turn30view4turn21academia2

\#\# 목적 범위 요구사항

해마의 최상위 목적은 “잘 말하는 시스템”이 아니라 \*\*복잡한 목적을 안전하고 검증 가능하게 완수하는 운영체계\*\*를 만드는 것이다. 따라서 목적은 세 수준으로 나뉜다. 첫째는 사용자 목표 달성이다. 둘째는 증거와 추적가능성을 확보하는 것이다. 셋째는 다중 에이전트와 외부 도구를 쓰더라도 시스템이 비용·시간·보안 제약을 넘지 않도록 통제하는 것이다. 첨부자료의 하네스 설계는 특히 이 셋째 차원을 중시하며, 개별 에이전트의 프롬프트 설계보다 상태, 인터페이스, 비평, 복구, 유지의 프로토콜을 더 중요하게 취급한다. fileciteturn0file1 fileciteturn0file2

범위는 넓지만 무한하지 않다. 해마는 문서 조사, 분석 보고서 작성, 소프트웨어 개발 지원, 다단계 업무조율, incident triage, 지식 기반 질의응답, 연구 오케스트레이션에 적합하다. 반면 실시간 초저지연 단순 질의응답, 매우 짧은 절차형 FAQ, 복잡한 물리 제어 루프처럼 외부 오케스트레이션 이득이 제한적인 경우에는 축소 경로가 필요하다. 이 범위 설정은 최근 procedural task 연구의 경고와도 부합한다. citeturn1academia5

\#\#\# 기능 요구사항

기능 요구사항은 최소한 아래 표의 수준에서 정의되어야 한다.

| 요구 범주 | 필수 기능 | 구현 의도 | 근거 |  
|---|---|---|---|  
| 목표 해석 | 사용자 요청을 목표, 제약, 성공조건, 위험수준으로 분해 | 자유 텍스트를 실행 사양으로 변환 | fileciteturn0file0 citeturn23academia0 |  
| 작업 분해 | 작업을 단계·서브태스크·의존관계로 모델링 | 병렬화와 책임 분리 | fileciteturn0file2 citeturn24academia3turn25academia0 |  
| 에이전트 배치 | 역할·비용·도메인 적합성에 따라 에이전트 선택 | ensemble 운영 | fileciteturn0file2 citeturn23academia3turn8view1 |  
| 도구 연결 | 함수도구, 파일, 검색, 코드 실행, 외부 API, MCP 서버 사용 | 환경 행위 능력 확보 | citeturn23academia1turn6view1turn5view1 |  
| 에이전트 간 위임 | handoff, subagent spawning, A2A 통신 | 복합작업 분업 | citeturn6view1turn12view1turn9view1 |  
| 기억 관리 | 단기·장기·에피소드·의미·기술 기억 관리 | 장기 일관성과 재사용성 | citeturn14academia0turn20academia3turn22view0turn25academia2 |  
| 검증 | critic, verifier, evidence bundle, schema validation | 신뢰성과 재현성 | fileciteturn0file1 fileciteturn0file2 citeturn24academia2turn24academia0 |  
| 인간 개입 | 승인·중단·수정·재개 | 고위험 작업 제어 | citeturn6view2turn6view1turn9view1 |  
| 재실행·복구 | 체크포인트, replay, retries, continue-as-new | 장기 작업 안정성 | citeturn5view0turn6view2 |  
| 관측·평가 | trace, span, metrics, eval, audit log | 운영 최적화와 원인 분석 | citeturn6view1turn28view2turn28view3 |

이 기능 요구사항을 더 엄밀히 적으면, 해마는 적어도 다음 능력을 제공해야 한다. 첫째, task object와 evidence object를 중심으로 상태를 추적해야 한다. 둘째, 각 agent run은 입력·중간 결과·도구 호출·검증 결과·최종 산출물을 모두 trace에 남겨야 한다. 셋째, 역할이 다른 에이전트 사이에 “자유 채팅”이 아니라 \*\*명시적 handoff 계약\*\*이 존재해야 한다. 넷째, 장기 메모리는 단순 vector similarity retrieval이 아니라 시점, 출처, 신뢰도, 상충 여부, 재사용 빈도를 포함한 구조화된 검색을 제공해야 한다. 다섯째, 모든 산출물은 “사실 주장”과 “설계 제안”을 기계적으로 구분할 수 있어야 한다. 이 다섯 항목은 첨부자료가 제안하는 증거 중심 운용을 구현 수준으로 번역한 것이다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2

\#\#\# 비기능 요구사항

비기능 요구사항은 오히려 더 중요하다. 해마는 장수명·상태형 시스템이므로, 신뢰성·유지보수성·재현성·비용예측성·확장성·보안성이 기능 못지않게 강해야 한다. LangGraph는 장수명 상태형 workflow를 위한 persistence와 human-in-the-loop를 핵심 가치로 두고, Temporal은 durable execution, replay, event history를 통해 실패 이후에도 최근 상태에서 복구할 수 있어야 한다고 본다. 이 방향은 해마의 비기능 요구와 정확히 맞닿는다. citeturn6view2turn5view0

비기능 요구사항은 다음 표준 형태로 정리할 수 있다.

| 항목 | 목표 수준 | 설계 해석 |  
|---|---|---|  
| 가용성 | 장기 작업 중 프로세스 실패 후 재개 가능 | 체크포인트 \+ durable workflow 필요 |  
| 일관성 | 같은 입력과 같은 증거 아래 유사한 결정 재현 | deterministic policy \+ schema validation 필요 |  
| 확장성 | agent run 수가 늘어도 orchestrator 병목 최소화 | 비동기 버스 \+ stateless control replicas |  
| 관측성 | 각 작업의 step, cost, latency, failure root-cause 추적 가능 | trace/span/metrics/audit 필수 |  
| 비용 통제 | per-task cost budget, model tiering, caching | 예산 스케줄러와 memory compaction 필요 |  
| 보안성 | prompt injection, data poisoning, auth gap, memory leakage 저감 | policy gate \+ signing \+ least privilege 필요 |  
| 국제화 | 한국어 사용자 경험과 영문 내재화 병행 | English-Core / Korean-Edge |  
| 운영성 | 테스트, 롤백, 샌드박스, 다중 환경 배포 가능 | CI/CD, canary, environment isolation |

이 가운데 \`English-Core / Korean-Edge\`는 일반적인 국제화와 다르다. 첨부파일이 제시하는 이 원칙은, 내부 canonical task schema·tool schema·agent contract를 영어 중심의 안정적 기계 표현으로 유지하면서도, 사용자 인터페이스·보고서·설명·승인 절차는 한국어로 제공하는 이중 층 구조를 의미한다. 이는 모델·도구·프로토콜 생태계가 영어 중심으로 발달한 현실과, 최종 사용자의 한국어 작업환경을 동시에 만족시키는 실용적 전략이다. fileciteturn0file0

\#\#\# 성공조건과 실패조건

해마의 성공조건은 “답이 좋다”가 아니다. 더 엄격하게는 다음 조건을 만족해야 한다. 결과물이 요청된 목적에 부합해야 하고, 주요 주장마다 증거를 제시해야 하며, 어떤 에이전트가 어떤 근거로 어떤 결정을 했는지 replay 가능한 형태로 남겨야 하고, 실패 시 재시도와 인간 개입 경로가 명확해야 하며, 장기적으로 같은 실수를 반복하지 않도록 기억 갱신이 이루어져야 한다. 반대로 실패조건은 단일 오답보다 더 넓다. 예를 들어 잘못된 handoff, 출처 없는 중간 가정, 맥락창 오염, 메모리 쓰레기 축적, 도구 권한 과다, 비용 폭주, 종료 조건 상실, reviewer 없는 self-approval 모두 시스템 실패로 간주해야 한다. AgentBench와 Agent-SafetyBench가 각각 장기 추론의 약점과 안전성의 부족을 지적한 것은 이 정의를 정량화해야 함을 보여 준다. citeturn24academia2turn24academia0

\#\# 참조 아키텍처

해마의 권장 참조 아키텍처는 다섯 개의 평면으로 나뉜다. \*\*제어면\*\*, \*\*실행면\*\*, \*\*기억면\*\*, \*\*정책·보안면\*\*, \*\*관측면\*\*이다. 제어면은 목표 해석, 계획, 스케줄링, handoff, 종료 판정을 담당한다. 실행면은 실제 에이전트와 도구 호출을 수행한다. 기억면은 단기·장기·증거 저장을 맡는다. 정책·보안면은 권한, 검열이 아니라 승인 규약, 위험관리, 데이터 경계, 프로토콜 검증을 담당한다. 관측면은 tracing, metrics, logs, evaluations를 통합한다. 이 분리는 LangGraph/Deep Agents의 runtime-memory-human loop, OpenAI Agents SDK의 handoff-guardrail-session-tracing 모델, Temporal의 durable workflow, MCP/A2A의 프로토콜 분업을 해마 문맥에 맞게 일반화한 것이다. citeturn6view2turn6view1turn5view0turn5view1turn12view1

\#\#\# 권장 상위 구조

\`\`\`mermaid  
flowchart TB  
    U\[사용자\] \--\> UI\[해마 UI · 승인 콘솔\]  
    UI \--\> HM\[Headmaster Control Plane\]

    HM \--\> Goal\[Goal Interpreter\]  
    HM \--\> Plan\[Planner\]  
    HM \--\> Sch\[Scheduler\]  
    HM \--\> Reg\[Agent Registry\]  
    HM \--\> Pol\[Policy · Guardrail Engine\]

    Sch \--\> Run\[Agent Runtime\]  
    Run \--\> A1\[Research Agent\]  
    Run \--\> A2\[Builder Agent\]  
    Run \--\> A3\[Critic Agent\]  
    Run \--\> A4\[Verifier Agent\]  
    Run \--\> A5\[Ops Agent\]

    A1 \--\> GW1\[MCP Gateway\]  
    A2 \--\> GW1  
    A3 \--\> GW2\[A2A Gateway\]  
    A4 \--\> GW1  
    A5 \--\> GW1

    GW1 \--\> Tools\[도구 · 데이터 · 검색 · 코드실행\]  
    GW2 \--\> Ext\[외부 에이전트\]

    Run \--\> Mem\[Memory Fabric\]  
    Mem \--\> STM\[Working Memory\]  
    Mem \--\> EPI\[Episodic Store\]  
    Mem \--\> SEM\[Semantic Store\]  
    Mem \--\> SKILL\[Skill · SOP Store\]  
    Mem \--\> EVID\[Evidence Store\]

    HM \--\> Obs\[Observability\]  
    Run \--\> Obs  
    Pol \--\> Obs  
    Obs \--\> Trace\[Trace · Span\]  
    Obs \--\> Metric\[Metrics · SLO\]  
    Obs \--\> Eval\[Evals · Audit\]  
\`\`\`

이 구조에서 핵심은 Headmaster가 모든 세부 추론을 직접 수행하지 않는다는 점이다. Headmaster는 \*\*작업 그래프를 관리하는 운영자\*\*이고, 실제 도메인 작업은 전문 에이전트에게 위임된다. 이는 OpenAI Agents SDK의 handoff, LangGraph/Deep Agents의 subagents, ADK의 graph workflows 및 collaborative workflows, A2A의 remote agent 개념과 구조적으로 같다. 곧, 해마는 “지휘자”이지 “모든 악기를 동시에 연주하는 솔리스트”가 아니다. citeturn6view1turn7view0turn9view1turn12view1

\#\#\# 데이터 흐름

\`\`\`mermaid  
sequenceDiagram  
    participant User as 사용자  
    participant HM as Headmaster  
    participant Mem as Memory  
    participant Reg as Registry  
    participant Sch as Scheduler  
    participant Ag as Agent Ensemble  
    participant Ver as Critic · Verifier  
    participant Tool as MCP · Tools · A2A  
    participant Obs as Trace · Audit

    User-\>\>HM: 목표 · 제약 · 자료 제출  
    HM-\>\>Mem: 관련 에피소드 · 정책 조회  
    HM-\>\>Reg: 후보 에이전트 선택  
    HM-\>\>Sch: 작업그래프 생성  
    Sch-\>\>Ag: 서브태스크 배치  
    Ag-\>\>Tool: 도구 호출 · 외부 위임  
    Tool--\>\>Ag: 결과 · 산출물 · 상태  
    Ag-\>\>Ver: 부분결과 검증 요청  
    Ver--\>\>Ag: pass / revise / fail  
    Ag-\>\>HM: artifact \+ evidence bundle  
    HM-\>\>Mem: 에피소드 저장 · 의미화 큐 적재  
    HM-\>\>Obs: trace, cost, evaluation 기록  
    HM--\>\>User: 최종 결과 · 증거 · 승인요청  
\`\`\`

이 데이터 흐름은 첨부파일에서 강조된 proof bundle, critic path, maintain 단계의 존재와 잘 맞는다. 또 Temporal의 event history·replay 모델은 각 단계가 이벤트 로그로 남아야 함을 뒷받침한다. 해마가 장기적으로 신뢰 가능해지려면, 결과 텍스트보다 \*\*상태 전이 기록\*\*이 더 중요한 1급 객체가 되어야 한다. fileciteturn0file1 fileciteturn0file2 citeturn5view0

\#\#\# 아키텍처 구성요소 비교표

| 구성요소 | 역할 | 권장 구현 | 대안 | 채택 이유 | 주의점 |  
|---|---|---|---|---|---|  
| Workflow Runtime | 장기 작업 상태·재시도·재개 | Temporal | LangGraph-only runtime | replay, event history, durable execution 강점 | 결정적 실행 요구가 엄격함 citeturn5view0 |  
| Agent Orchestration | 서브에이전트·branch·HITL | LangGraph 또는 OpenAI Agents SDK | ADK | 상태형 graph와 handoff primitive가 성숙 | 프레임워크 혼합 시 추적 통합 필요 citeturn6view2turn6view1turn9view1 |  
| Agent Protocol Gateway | 도구·리소스 연결 | MCP Gateway | 직접 함수도구 바인딩 | 표준화·확장성·도구 생태계 | description quality와 auth gap 위험 citeturn5view1turn1academia3turn1academia0 |  
| External Delegation | 외부 agent 협업 | A2A Gateway | 내부 handoff only | capability discovery, long-running task lifecycle | 생태계 성숙도 변동, 보안통합 필요 citeturn12view1 |  
| Message Bus | 비동기 이벤트 전파 | NATS JetStream | Kafka, Redis Streams | pub/sub, request/reply, streaming을 단일 계층에서 제공 | exactly-once 환상에 기대면 안 됨 citeturn28view4 |  
| Memory Fabric | STM/LTM/증빙/스킬 통합 | Postgres \+ Vector DB \+ Object Store | 단일 vector DB | 구조화 질의·감사·대용량 artifact 공존 가능 | 기억 중복과 노이즈 정리 필요 citeturn22view0turn21academia2 |  
| Deployment Substrate | 배포·오토스케일·격리 | Kubernetes | managed serverless | 분리배포, 자원 할당, self-healing | workflow orchestration과 혼동 금지 citeturn28view0turn28view1 |  
| Observability | trace·metric·log | OpenTelemetry \+ Prometheus | 벤더 종속 APM | 표준 telemetry와 백엔드 독립성 | semantic convention 설계가 중요 citeturn28view2turn28view3 |

위 표의 핵심 메시지는 간단하다. \*\*Kubernetes는 인프라 오케스트레이터이지 업무 오케스트레이터가 아니며, Temporal/Graph runtime과 역할을 분리해야 한다\*\*는 점이다. Kubernetes 문서는 원하는 상태를 향해 독립적 제어 프로세스가 수렴하도록 만든 플랫폼이지, “A 다음 B 다음 C”의 워크플로 엔진이 아니라고 명시한다. 따라서 해마는 Kubernetes 위에서 배포될 수 있으나, 해마의 작업 상태와 handoff는 별도 workflow/runtime 계층에서 다뤄야 한다. citeturn28view0turn28view1

\#\#\# 통신과 프로토콜

해마의 통신층은 최소 세 종류의 상호작용을 구분해야 한다. 첫째, \*\*내부 control message\*\*다. 이것은 task dispatch, state change, retry request, approval request, completion event 등으로 구성되고, 낮은 지연과 높은 fan-out이 필요하므로 NATS 계열이 적합하다. 둘째, \*\*도구·데이터 access\*\*다. 이는 MCP처럼 tool/resource/prompt를 구조화해 연결하는 것이 확장성과 유지보수성에 유리하다. 셋째, \*\*external agent collaboration\*\*이다. 이는 A2A의 Agent Card, task lifecycle, artifact, parts 개념을 활용하는 편이 좋다. 내부 handoff와 외부 delegation을 동일하게 다루지 않는 것이 중요하다. 외부 에이전트는 신뢰 경계 밖에 있기 때문이다. citeturn28view4turn5view1turn12view1

\#\#\# 보안과 확장성

해마의 보안은 단순 프롬프트 필터로 끝나지 않는다. OWASP는 2025 LLM Top 10에서 prompt injection, sensitive information disclosure, supply chain, data/model poisoning 등을 독립 위험으로 제시하고 있으며, agentic security initiative는 자율 에이전트와 multi-step workflow의 공격면을 별도로 다룬다. MCP 관련 2025\~2026 연구는 tool poisoning, shadowing, descriptor alteration 위험을 지적하고, 대규모 도구 생태계에서 자연어 설명 품질이 task success와 비용에 실질적으로 영향을 준다고 보고했다. 따라서 해마는 \*\*도구 설명 스캐닝, capability signing, least-privilege token, outbound policy, memory write quarantine\*\*를 기본요소로 채택해야 한다. citeturn29view0turn30view3turn30view4turn1academia0turn1academia3

확장성 측면에서는 제어면을 세밀하게 분리해야 한다. Headmaster는 stateless replica로 수평 확장 가능해야 하고, 실제 장기 상태는 workflow store와 memory store에 externalized되어야 한다. 에이전트 실행은 queue 기반으로 격리하며, 모델 tier와 도구 종류에 따라 다르게 스케줄링해야 한다. Google ADK와 Google Agent Platform은 graph workflow, multi-agent orchestration, context management, tracing, runtime deployment를 조합해 이러한 구조를 실무 수준으로 지원하고 있으며, Azure Foundry Agent Service와 Bedrock Agents도 각각 managed runtime, tools, observability, memory, security를 서비스로 묶어 제공한다. 해마는 이들 managed platform을 부분 활용하거나, 동일 패턴을 자체 구현할 수 있다. citeturn9view1turn9view0turn8view2turn31view0

\#\#\# 권장 API 명세

해마는 최소한 다음 API 세트를 제공해야 한다. 여기서 중요한 것은 모든 엔드포인트가 단순 request-response가 아니라 \*\*stateful task contract\*\*를 공유해야 한다는 점이다.

\`\`\`http  
POST /v1/tasks  
GET  /v1/tasks/{task\_id}  
POST /v1/tasks/{task\_id}/approve  
POST /v1/tasks/{task\_id}/cancel  
POST /v1/tasks/{task\_id}/retry  
GET  /v1/tasks/{task\_id}/artifacts  
GET  /v1/tasks/{task\_id}/evidence  
GET  /v1/tasks/{task\_id}/trace

POST /v1/agents/{agent\_id}/dispatch  
GET  /v1/agents/{agent\_id}/status  
POST /v1/agents/{agent\_id}/handoff

POST /v1/memory/query  
POST /v1/memory/commit  
POST /v1/memory/consolidate

POST /v1/evals/run  
GET  /v1/evals/{eval\_id}  
\`\`\`

이 스펙은 OpenAI Agents SDK의 run/session/tracing primitives, LangGraph의 stateful invocation, Temporal의 workflow identity 및 event history 개념을 구현 지향적으로 합성한 것이다. 즉 HTTP API는 외피일 뿐이고, 실질적 핵심은 \`task\_id\`, \`workflow\_id\`, \`thread\_id\`, \`agent\_run\_id\`, \`memory\_record\_id\`가 서로 연결되는 상태 그래프다. citeturn6view1turn7view0turn5view0

\#\#\# 핵심 데이터 스키마

\`\`\`json  
{  
  "TaskSpec": {  
    "task\_id": "tsk\_01J...",  
    "goal": "해마 시스템 심층 연구 보고서 작성",  
    "constraints": {  
      "language": "ko",  
      "min\_length\_chars": 50000,  
      "citation\_required": true,  
      "deadline": null,  
      "budget": {  
        "max\_model\_cost\_usd": 25.0,  
        "max\_tool\_calls": 400  
      }  
    },  
    "risk\_profile": {  
      "data\_sensitivity": "internal",  
      "action\_risk": "medium",  
      "needs\_human\_approval": true  
    },  
    "inputs": \[  
      {  
        "type": "file",  
        "ref": "turn0file0",  
        "trust": "user\_provided"  
      }  
    \],  
    "success\_criteria": \[  
      "명세 포함",  
      "API 포함",  
      "상태머신 포함",  
      "비교와 위험 분석 포함"  
    \]  
  }  
}  
\`\`\`

\`\`\`json  
{  
  "AgentManifest": {  
    "agent\_id": "critic\_v1",  
    "role": "critic",  
    "capabilities": \["claim\_check", "schema\_validation", "consistency\_review"\],  
    "input\_schema": "EvidenceBundle",  
    "output\_schema": "Verdict",  
    "cost\_tier": "mini",  
    "max\_concurrency": 8,  
    "requires\_tools": \[\],  
    "requires\_memory\_scopes": \["episodic", "evidence"\],  
    "policy\_tags": \["no\_final\_publish", "must\_explain\_failure"\]  
  }  
}  
\`\`\`

\`\`\`json  
{  
  "EvidenceBundle": {  
    "bundle\_id": "evb\_01J...",  
    "task\_id": "tsk\_01J...",  
    "claims": \[  
      {  
        "claim\_id": "c1",  
        "text": "해마는 agentic runtime이어야 한다",  
        "claim\_type": "design\_inference",  
        "supports": \[  
          {"source": "turn0file2", "kind": "file"},  
          {"source": "turn6view2", "kind": "web"},  
          {"source": "turn5view0", "kind": "web"}  
        \],  
        "confidence": 0.84  
      }  
    \],  
    "counterevidence": \[\],  
    "verifier\_status": "pending"  
  }  
}  
\`\`\`

\`\`\`json  
{  
  "MemoryRecord": {  
    "memory\_id": "mem\_01J...",  
    "scope": "episodic",  
    "task\_id": "tsk\_01J...",  
    "timestamp": "2026-06-10T10:22:31+09:00",  
    "summary": "MCP tool description quality issue caused tool misselection",  
    "embedding\_ref": "vec\_...",  
    "salience": 0.77,  
    "confidence": 0.72,  
    "decay\_policy": "reinforce\_on\_reuse",  
    "source\_refs": \["turn1academia3"\],  
    "quarantine": false  
  }  
}  
\`\`\`

이 스키마의 특징은 첨부파일의 proof/verification 중심 철학을 \`claim\_type\`, \`supports\`, \`confidence\`, \`verifier\_status\`, \`quarantine\` 같은 기계적 필드로 끌어내렸다는 데 있다. 단순 문장 생성 대신 \*\*주장 객체와 증거 객체의 결합\*\*이 해마의 1급 산출물이어야 한다. fileciteturn0file1 fileciteturn0file2

\#\# 에이전트 설계와 기억 메커니즘

해마의 에이전트 설계는 “지휘자-연주자” 비유를 그대로 따르되, 실제 구현에서는 훨씬 더 엄격해야 한다. 오케스트레이터 역할이 너무 많은 지적 작업을 직접 수행하면 병목과 불투명성이 생기고, 반대로 각 전문 에이전트가 자유롭게 대화하면 종료 조건 상실과 책임 확산이 생긴다. 따라서 해마는 \*\*지휘자, 악장, 전문 연주자, 비평가, 무대감독\*\*에 해당하는 역할을 분리해야 한다. MetaGPT와 ChatDev가 역할 분업과 SOP 내재화를 통해 협업 일관성을 높였고, AutoGen과 ADK가 대화행동과 라우팅을 프로그래머가 제어할 수 있도록 한 것은 이 설계를 뒷받침한다. citeturn24academia3turn24academia1turn23academia3turn9view1

\#\#\# 에이전트 유형 역할 인터페이스 표

| 에이전트 유형 | 핵심 역할 | 입력 | 출력 | 상태 | 학습 및 기억 | 대표 인터페이스 |  
|---|---|---|---|---|---|---|  
| Headmaster | 목표 해석, 작업그래프 생성, 종료 판정 | TaskSpec, Memory Recall | TaskGraph, Final Decision | planning, waiting, merging | 메타정책 기억, 실패 패턴 기억 | \`/tasks\`, \`/handoff\`, \`/approve\` |  
| Planner | 문제 분해, dependency 설계 | Goal, constraints | Subtasks, dependency map | drafting, revising | decomposition templates | \`plan(task)\` |  
| Router | 적합 agent 선택, model tiering | task node, budget | assignment | scoring, assigned | agent performance stats | \`route(node)\` |  
| Research Agent | 자료검색, 근거수집, 비교분석 | question, search scope | notes, citations, claims | investigating, summarizing | source reliability memory | \`research(query)\` |  
| Builder Agent | 문서·코드·아티팩트 생성 | design brief | artifact draft | building, blocked | reusable patterns, skills | \`build(spec)\` |  
| Critic Agent | 논리일관성·누락·반례 점검 | draft, evidence | critique | reviewing, escalated | failure mode memory | \`criticize(bundle)\` |  
| Verifier Agent | 사실검증·스키마검사·테스트 실행 | artifact, evidence | verdict | checking, pass, fail | benchmark and rule memory | \`verify(bundle)\` |  
| Policy Agent | 보안·윤리·권한 검사 | planned action | allow/deny/review | gated | policy memory | \`authorize(action)\` |  
| Ops Agent | 배포·모니터링·복구 | deployment plan | runbooks, deployment events | deploying, recovering | infra incident memory | \`operate(job)\` |  
| Consolidator | 장기기억 정리·스킬 추출 | episodic logs | semantic memory, skill cards | consolidating | long-term memory update | \`consolidate(session)\` |

이 표는 첨부파일의 개별 agent harness와 master orchestrator harness를 바탕으로 role contract를 체계화한 것이다. 특히 Critic과 Verifier의 분리는 매우 중요하다. Critic은 주로 질적 검토와 반례 탐색을, Verifier는 스키마·테스트·사실 검사를 담당하는 편이 좋다. 최근 에이전트 벤치마크가 long-term reasoning, instruction following, safety robustness 부족을 지적한 만큼, 자기검열이 아니라 \*\*분리된 평가 역할\*\*을 두는 것이 안전하다. fileciteturn0file1 fileciteturn0file2 citeturn24academia2turn24academia0

\#\#\# 지휘자와 오케스트레이터 역할

Headmaster의 책임은 크게 일곱 가지다. 작업 스코핑, 자원 예산 편성, 작업 그래프 생성, 에이전트 배치, 검증 게이트 관리, 인간 승인 요청, 결과 승격이다. 여기서 중요한 것은 Headmaster가 곧바로 본문을 쓰거나 코드를 많이 생성하지 않는다는 점이다. 만약 Headmaster가 직접 생성까지 장악하면, trace는 하나로 줄어들지만 에러 원인 분리가 어려워지고, memory contamination도 커진다. 반대로 creation을 전문 agent에 위임하면 비용과 오류가 증가할 수 있지만, 비평과 재사용은 쉬워진다. 해마는 후자를 택하되, Headmaster가 최소한의 canonical summary와 decision rationale만 직접 보관하는 방식이 바람직하다. fileciteturn0file2 citeturn6view1turn6view2

오케스트레이터의 구체 역할은 첨부파일의 I-B-F 루프와도 연결된다. 파일들은 이 루프를 통해 근거 기반 반복 개선을 수행하도록 설계되어 있다. 비록 첨부자료만으로 그 약어의 세부 확장을 일반화하는 것은 조심스러우나, 공학적으로는 \*\*Intent 정규화 → Build/Breakdown → Feedback/Fact-check\*\*에 가까운 제어 사이클로 이해할 수 있다. 해마 구현에서는 이를 \`plan \-\> execute \-\> critique \-\> verify \-\> repair \-\> consolidate\`로 명시적 상태 전이로 표현하는 것이 좋다. fileciteturn0file2

\#\#\# 에이전트 상태 모델

다중 에이전트 시스템에서 상태를 언어로만 표현하면 운영이 불가능해진다. 해마는 각 agent run에 대해 명시적 상태 머신을 가져야 한다.

\`\`\`mermaid  
stateDiagram-v2  
    \[\*\] \--\> Idle  
    Idle \--\> Prepared: task assigned  
    Prepared \--\> Running: context hydrated  
    Running \--\> WaitingTool: tool call  
    WaitingTool \--\> Running: tool result  
    Running \--\> WaitingHuman: approval needed  
    WaitingHuman \--\> Running: approved  
    Running \--\> Verifying: draft emitted  
    Verifying \--\> Committed: pass  
    Verifying \--\> Recovering: fail but repairable  
    Recovering \--\> Running: retry or revise  
    Running \--\> Failed: unrecoverable error  
    Failed \--\> Aborted: cancel  
    Committed \--\> Archived: task closed  
\`\`\`

Temporal은 workflow execution이 open/closed 상태와 event history를 갖고, replay로 최근 기록 지점부터 재개된다고 설명한다. LangGraph 역시 persistence와 interrupts를 제공한다. 그러므로 해마의 상태 머신은 단순 로컬 enum이 아니라 \*\*이벤트 로그 기반 상태 전이\*\*로 구현되어야 한다. 특히 \`WaitingHuman\`, \`Verifying\`, \`Recovering\`을 명시 상태로 두는 것은 첨부파일의 운영 철학과 최신 runtime의 공통점을 반영한다. citeturn5view0turn6view2turn6view1

\#\#\# 맥락 유지와 해마 유사 기억 구조

해마의 기억 구조는 최소 다섯 계층이어야 한다.

첫째, \*\*작업기억 STM\*\*이다. 현재 task graph, 최근 메시지, 활성 tool result, 예산 잔량, 승인 상태 같은 고휘발성 정보를 담는다. 이 계층은 LangGraph의 short-term working memory, Agents SDK의 sessions, ADK의 structured context 관리와 대응한다. 둘째, \*\*에피소드 기억 EPI\*\*다. 어떤 작업에서 어떤 전략이 어떤 결과를 냈는지, 실패 원인은 무엇이었는지, 어떤 검증이 통과·실패했는지를 저장한다. Reflexion의 reflective memory, Generative Agents의 observation+reflection log, Voyager의 skill acquisition history가 여기에 가깝다. 셋째, \*\*의미 기억 SEM\*\*이다. 반복적으로 재사용되는 사실, 도메인 개념, 정책 요약, 문서 지식이 들어간다. 넷째, \*\*기술 기억 SKILL\*\*이다. SOP, prompt template, code pattern, reusable workflow recipe를 저장한다. 다섯째, \*\*증빙 기억 EVID\*\*다. 인용, artifact, 테스트 결과, 검증 verdict를 저장한다. 증빙 기억은 다른 기억과 달리 감사를 위해 retention이 길어야 한다. citeturn6view2turn6view1turn14academia0turn20academia0turn21academia1turn22view0

이 계층화는 신경과학적 비유와도 잘 맞는다. 해마는 새로운 사건을 빠르게 저장하고, 시간이 지나며 더 일반화된 지식이 피질적 저장으로 옮겨가는 구조로 자주 설명된다. 텐서 메모리 가설은 에피소드 기억이 의미 기억 형성에 가르침을 준다고 보고, 해마 계산모형은 correlated sequence에서도 pattern separation과 cue-based recall이 중요하다고 본다. 해마 시스템에서도 마찬가지로, 한 번의 작업 로그를 곧바로 전사해 장기 규칙으로 삼으면 안 되며, 반복 검증된 패턴만 의미·기술 기억으로 승격해야 한다. citeturn17academia4turn18academia5turn19academia0

최근 LongMemEval과 Agentic Memory 연구는 장기 기억이 단순히 더 많이 저장한다고 좋아지지 않음을 보여 준다. LongMemEval은 장기 대화·다세션 기억에서 기존 시스템이 크게 성능 저하를 겪으며, index granularity·query expansion·time-aware retrieval 설계가 중요하다고 보고했다. 경험추종 행동 연구는 memory addition/deletion 정책이 에이전트의 미래 행동을 크게 바꾸고, 잘못된 기억이 error propagation을 일으킬 수 있음을 밝혔다. 그러므로 해마는 \*\*무조건 저장\*\* 대신 \`selective write\`, \`quarantine\`, \`reinforcement on reuse\`, \`retire on contradiction\` 정책을 가져야 한다. citeturn25academia1turn21academia2turn25academia2

\#\#\# 기억 알고리즘 설계

해마의 기억 쓰기 알고리즘은 다음처럼 설계할 수 있다.

\`\`\`python  
def commit\_episode(task\_result, evidence\_bundle, verifier\_verdict):  
    if verifier\_verdict \== "fail":  
        write\_quarantine\_memory(task\_result, evidence\_bundle)  
        return "quarantined"

    salience \= score\_salience(task\_result)  
    confidence \= score\_confidence(evidence\_bundle)

    episode\_id \= write\_episode\_memory(  
        summary=task\_result.summary,  
        artifact\_ref=task\_result.artifact\_ref,  
        source\_refs=evidence\_bundle.source\_refs,  
        salience=salience,  
        confidence=confidence,  
        decay\_policy="reinforce\_on\_reuse"  
    )

    if salience \>= 0.75 and confidence \>= 0.80:  
        enqueue\_consolidation(episode\_id)

    return episode\_id  
\`\`\`

\`\`\`python  
def consolidate\_episode(episode):  
    if episode.reuse\_count \< 2 and episode.confidence \< 0.85:  
        return "defer"

    semantic\_facts \= extract\_stable\_facts(episode)  
    skill\_card \= extract\_reusable\_procedure(episode)

    for fact in semantic\_facts:  
        if not contradicts\_existing\_fact(fact):  
            upsert\_semantic\_memory(fact)

    if skill\_card and skill\_card.test\_pass\_rate \>= 0.9:  
        publish\_skill(skill\_card)

    archive\_episode(episode.id)  
    return "consolidated"  
\`\`\`

이 알고리즘의 핵심은 세 가지다. 첫째, 검증 실패 기록도 버리지 말고 quarantine 영역에 저장한다. 실패 기억은 보안과 운영에서 중요하기 때문이다. 둘째, 에피소드와 의미 기억 사이에 승격 게이트를 둔다. 셋째, skill은 추출만으로 끝내지 말고 테스트를 통과해야 게시한다. 이는 첨부파일의 proof·verification 철학, MemoryBank의 중요도/시간 기반 기억정책, Agentic Memory의 memory operation 통합, 경험추종 연구의 selective addition/deletion 제안을 함께 반영한 것이다. fileciteturn0file1 citeturn20academia3turn25academia2turn21academia2

\#\#\# 협업과 조정 메커니즘

다중 에이전트 협업은 세 수준에서 일어난다. 가장 단순한 수준은 \*\*star topology\*\*다. Headmaster가 모든 agent와 직접 통신한다. 이해는 쉽지만 병목이 크다. 둘째는 \*\*hierarchical topology\*\*다. 섹션 리드나 domain lead를 두어 전문 집단을 묶는다. 셋째는 \*\*graph topology\*\*다. 필요에 따라 agent 간 직접 의존을 허용한다. MultiAgentBench는 star, chain, tree, graph 토폴로지를 비교하며, 연구 시나리오에서 graph 구조가 우수했고 cognitive planning이 milestone 달성을 개선한다고 보고했다. 따라서 해마의 기본 토폴로지는 계층형 star로 출발하되, 복잡 연구·개발 워크로드에서는 부분 graph mode를 활성화하는 쪽이 적절하다. citeturn25academia0

조정 메커니즘은 단순 turn-taking이 아니라 contract-based여야 한다. 각 handoff에는 목표, 입력요약, 허용행동, 금지행동, 기대출력스키마, 완료조건, 증빙 요구가 포함되어야 한다. 이는 OpenAI Agents SDK의 handoff, A2A의 task/artifact/parts, 첨부파일의 structured proof 인터페이스와 정합적이다. 곧, agent-to-agent communication은 자연어 대화가 아니라 \*\*구조화된 위임 계약\*\*이어야 한다. citeturn6view1turn12view1turn12view4turn0file1

\#\#\# 오케스트레이션 의사코드

\`\`\`python  
def headmaster\_run(task\_spec):  
    state \= initialize\_state(task\_spec)

    recalled \= memory\_recall(task\_spec.goal, task\_spec.inputs, task\_spec.constraints)  
    state.attach(recalled)

    if should\_use\_simple\_path(task\_spec, recalled):  
        return single\_agent\_path(state)

    task\_graph \= planner\_create\_graph(state)  
    assignments \= router\_assign(task\_graph, budget=state.budget)

    for node in topological\_ready\_nodes(task\_graph):  
        run\_id \= scheduler\_dispatch(node, assignments\[node\])  
        node.bind\_run(run\_id)

    while not task\_graph.is\_terminal():  
        event \= wait\_next\_event()

        if event.type \== "artifact\_submitted":  
            critic \= run\_critic(event.artifact)  
            verdict \= run\_verifier(event.artifact, critic)

            if verdict.pass\_:  
                task\_graph.mark\_done(event.node\_id)  
                memory\_commit\_episode(event.artifact, verdict.evidence)  
            elif verdict.repairable:  
                scheduler\_retry(event.node\_id, patch=verdict.patch)  
            else:  
                escalate\_to\_human(event, verdict)

        elif event.type \== "budget\_threshold":  
            downgrade\_models\_or\_pause(state)

        elif event.type \== "approval\_required":  
            request\_human\_approval(event)

    final \= merge\_artifacts(task\_graph)  
    final\_verdict \= run\_final\_verifier(final)  
    if not final\_verdict.pass\_:  
        raise FinalPublishBlocked()

    memory\_consolidate\_async(task\_graph.session\_id)  
    return final  
\`\`\`

이 의사코드가 보여 주는 해마의 본질은 세 문장으로 요약된다. 첫째, 실행 전 기억 회수가 있고, 둘째, 실행 중 critic/verifier gate가 있고, 셋째, 실행 후 memory consolidation이 있다. 첨부파일의 evidence-first 설계와 현대 agent runtime 문헌을 함께 만족시키려면 이 세 단계는 생략될 수 없다. fileciteturn0file0 fileciteturn0file2 citeturn6view2turn6view1turn5view0

\#\# 작업 플로우와 운영 체계

해마의 워크플로는 단발성 “질문-답변” 흐름이 아니라, \*\*준비·실행·검증·승격·유지\*\*가 순환하는 운영 루프다. 첨부자료는 특히 discover/problem-decompose/design/verification/deploy/maintain에 해당하는 다단계 흐름과, 유지 단계에서 재측정·경미수정·지식갱신을 강조한다. 이 설계는 한 번 만들어 끝나는 응답이 아니라, 시간이 지남에 따라 계속 배우고, 수정되고, 감시받는 작업 시스템을 지향한다. fileciteturn0file0 fileciteturn0file2

\#\#\# 권장 작업 플로우

해마의 기본 작업 플로우는 다음 여섯 국면으로 정리할 수 있다.

첫째, \*\*scoping\*\*이다. 사용자 요청을 그대로 수행하지 않고, 목적·제약·출력물 형식·증거 수준·위험 수준으로 구조화한다. 둘째, \*\*decomposition\*\*이다. 목표를 task graph로 바꾸고, 병렬 가능한 부분과 순차 의존을 나눈다. 셋째, \*\*execution\*\*이다. 에이전트가 도구와 외부 시스템을 호출하며 중간 산출물을 만든다. 넷째, \*\*verification\*\*이다. critic/verifier/policy가 각 산출물을 검사한다. 다섯째, \*\*publication\*\*이다. pass된 artifact만 최종 산출물로 승격한다. 여섯째, \*\*maintenance\*\*다. 이후 관측 지표, 사용자 피드백, 오류 재발 패턴을 바탕으로 skill과 memory를 갱신한다. 이 여섯 국면은 첨부자료의 단계형 운영 원칙을 실제 구현 흐름으로 압축한 것이다. fileciteturn0file0 fileciteturn0file2

\#\#\# 스케줄링 정책

스케줄링은 모델 선택만이 아니다. 해마는 최소 네 종류의 자원을 스케줄해야 한다. 모델 토큰 예산, 도구 호출 예산, 대기시간 예산, 인간 승인 예산이다. 연구 에이전트에는 검색 및 문서처리 예산이 중요하고, 코드 생성 에이전트에는 sandbox와 test 실행 예산이 중요하며, policy review에는 인적 승인 슬롯이 중요하다. OpenAI API는 모델별 가격·도구 호출 비용·컨테이너 비용을 분리해 제시하고 있어, 태스크 수준 비용 예산기를 두는 것이 실무적으로 의미가 있다. 또 LangGraph/Agents SDK/ADK는 중간 progress와 tracing을 제공하므로, 해마는 budget threshold 이벤트를 기반으로 동적 model tiering을 실행할 수 있다. citeturn33view0turn6view2turn6view1turn9view1

권장 스케줄링 알고리즘은 다음 우선순위를 따른다. 고위험 검증 노드는 저비용 생성 노드보다 우선한다. 동일 중요도에서는 critical path 길이가 긴 노드를 우선 실행한다. 동일 경로에서는 high-information-gain, 즉 분기 불확실성을 많이 줄일 노드를 먼저 수행한다. 예산 과소 상태에서는 고비용 대형 모델을 줄이고 검증 경로만 유지한다. 이런 정책은 MultiAgentBench의 topology·planning 지표, AgentBench의 장기추론 병목 진단, 실제 상용 플랫폼의 trace 중심 운영 방식과 일치한다. citeturn25academia0turn24academia2turn31view0turn8view2

\#\#\# 자원 관리

자원 관리는 세 층으로 분리하는 것이 좋다. \*\*orchestration quota\*\*, \*\*agent quota\*\*, \*\*tool quota\*\*다. orchestration quota는 전체 태스크의 최대 비용·시간·동시성 상한을 의미한다. agent quota는 역할별 동시 실행 수와 model tier 예산이다. tool quota는 특정 외부 도구나 검색·코드 실행의 최대 호출량이다. 이 분리를 하지 않으면, 하나의 탐색적 리서치 에이전트가 전체 태스크 예산을 잠식할 수 있다. OpenAI Agents SDK의 sandbox/session, Bedrock Agents의 action group·knowledge base·trace, Foundry의 managed tools·observability는 이런 분리가 실무적으로 얼마나 중요한지 보여 준다. citeturn6view1turn31view0turn8view2

권장 구현은 각 task에 대해 \`budget ledger\`를 두는 것이다. ledger는 사용 토큰, 호출 횟수, 경과시간, 승인 소모량, 실패율을 누적 기록한다. Scheduler는 매 이벤트마다 ledger를 업데이트하고 \`soft limit\`, \`hard limit\`를 검사한다. soft limit를 넘기면 모델 tier를 낮추거나 요약 압축을 촉발하고, hard limit를 넘기면 인간 승인 없이는 다음 단계를 멈춘다. 이는 비용폭주와 endless loop를 막는 가장 실용적 제어 방법이다. citeturn33view0turn5view0

\#\#\# 예시 UI와 대시보드

\`\`\`mermaid  
flowchart LR  
    A\[작업 개요 카드\<br/\>목표 · 제약 · 예산\] \--\> B\[진행 타임라인\<br/\>상태 전이 · ETA 아님\]  
    A \--\> C\[에이전트 패널\<br/\>역할 · 현재 상태 · 비용\]  
    B \--\> D\[증거 패널\<br/\>주장 · 출처 · 검증상태\]  
    C \--\> E\[승인 큐\<br/\>위험행동 · 보류사유\]  
    D \--\> F\[기억 패널\<br/\>STM · EPI · SEM · SKILL\]  
    E \--\> G\[운영 패널\<br/\>trace · metrics · failures\]  
\`\`\`

실사용 UI는 대화창 중심이 아니라 \*\*작업판\*\*이어야 한다. 사용자는 단순 텍스트 답변보다 task graph, 에이전트 상태, 대기중 승인, 비용 누적, 검증 실패 근거를 봐야 한다. 첨부파일의 stepwise evidence와 maintain 단계는 이런 UI를 전제한다. LangGraph, Agents SDK, ADK, Foundry, Bedrock이 공통적으로 tracing·debugging·testability를 강조하는 것도 같은 이유다. fileciteturn0file0 fileciteturn0file1 citeturn6view2turn6view1turn9view1turn8view2turn31view0

\#\#\# 테스트 케이스

해마는 기능 테스트만으로는 충분하지 않다. 아래와 같은 테스트 세트가 필요하다.

| 테스트 유형 | 시나리오 | 기대 결과 |  
|---|---|---|  
| 단위 테스트 | Planner가 긴 요청을 올바른 task graph로 분해하는가 | dependency cycle 없음, output schema valid |  
| 단위 테스트 | Verifier가 출처 없는 claim을 fail 처리하는가 | verifier fail \+ evidence missing |  
| 통합 테스트 | Research Agent → Critic → Verifier → Final merge | pass된 artifact만 승격 |  
| 통합 테스트 | Tool timeout 발생 시 Recovering 상태로 전이하는가 | retry/backoff 후 재개 |  
| 회귀 테스트 | 동일 입력·동일 자료에서 결과 구조가 유지되는가 | section schema 및 주요 claim 안정 |  
| 메모리 테스트 | 잘못된 episode가 재사용을 오염시키는가 | quarantine 또는 contradiction handling |  
| 보안 테스트 | prompt injection 문자열이 tool 호출 권한을 우회하는가 | policy deny |  
| 보안 테스트 | 민감정보가 evidence bundle 밖으로 노출되는가 | redaction |  
| 카오스 테스트 | worker 프로세스 중단 후 workflow가 replay 가능한가 | 최근 이벤트부터 재개 |  
| 운영 테스트 | soft budget 초과 시 model tiering이 동작하는가 | 비용 증가율 감소 |

이 테스트 구조는 AgentBench, Agent-SafetyBench, LongMemEval이 보여 준 장기 추론·안전성·장기기억 문제를 직접 겨냥한다. 해마는 “모델 벤치마크”가 아니라 “시스템 벤치마크”를 가져야 한다. citeturn24academia2turn24academia0turn25academia1

\#\# 평가 검증 사례 비교

해마의 평가 체계는 최소 다섯 축을 포함해야 한다. \*\*성능\*\*, \*\*정확성\*\*, \*\*안전성\*\*, \*\*운영성\*\*, \*\*경제성\*\*이다. 많은 시스템이 첫 두 축만 보고 성공을 판단하지만, 에이전트 시스템에서 실제 실패는 종종 비용폭주, 장기기억 오염, 승인 누락, 재현 불가, 프로토콜 취약성에서 발생한다. AgentBench는 LLM agent의 주된 약점이 장기추론·의사결정·instruction following이라고 보았고, Agent-SafetyBench는 널리 쓰이는 에이전트들이 안전 점수 60을 넘지 못한다고 보고했다. 이는 품질 평가가 응답 문장 품질만으로 끝날 수 없음을 말해 준다. citeturn24academia2turn24academia0

\#\#\# 주요 성능 지표 표

| 지표 | 정의 | 목표값 예시 | 측정 방법 | 의미 |  
|---|---|---|---|---|  
| Task Success Rate | 성공조건 충족 태스크 비율 | 파일럿 70%+, 운영 85%+ | gold rubric \+ human eval | 최상위 효용 |  
| Evidence Coverage | 주요 주장 중 인용·증빙이 연결된 비율 | 95%+ | claim-to-citation matcher | 출처 충실도 |  
| Verification Pass Rate | 초안이 1차 검증을 통과하는 비율 | 60\~75% | verifier logs | 초안 품질 |  
| Repair Efficiency | fail 후 1회 수정으로 통과하는 비율 | 50%+ | retry analytics | self-repair 능력 |  
| Long-Memory Recall | 장기기억 기반 정답률 | baseline 대비 \+10%p | LongMemEval 계열 | 기억 체계 유효성 |  
| Handoff Accuracy | 잘못된 위임 없이 적절 agent로 라우팅된 비율 | 90%+ | routing audit | 협업 효율 |  
| Orchestration Overhead | 단일 agent 대비 추가 지연·비용 | 25% 이내 | A/B 비교 | 오케스트레이션 타당성 |  
| Safety Block Precision | 실제 위험 행동 중 차단 정밀도 | 90%+ | adversarial eval | 과소·과대 차단 균형 |  
| Replay Determinism | 동일 이벤트 히스토리 replay 일치도 | 99%+ | replay diff | 재현성 |  
| Cost per Successful Task | 성공태스크당 평균 비용 | use-case별 상한 | billing ledger | 상용화 가능성 |

LongMemEval은 다세션 장기기억에서 기존 시스템이 크게 성능 저하를 보인다고 보고했고, Agentic Memory와 경험추종 연구는 메모리 관리가 장기 성능을 좌우한다고 보였다. 따라서 해마는 Task Success나 BLEU류 지표보다 \*\*long-memory recall\*\*, \*\*repair efficiency\*\*, \*\*replay determinism\*\*을 더 중요하게 봐야 한다. citeturn25academia1turn25academia2turn21academia2

\#\#\# 평가 프로토콜

평가 프로토콜은 세 계층이어야 한다. 첫째는 \*\*offline benchmark\*\*다. AgentBench, MultiAgentBench, LongMemEval, 자체 task suite를 통해 기초 능력을 본다. 둘째는 \*\*trace-based evaluation\*\*이다. step-level trace를 보고 어디서 실패했는지, 어떤 handoff가 불필요했는지, 어떤 tool description이 혼선을 일으켰는지 분석한다. 셋째는 \*\*live shadow mode\*\*다. 실제 업무와 유사한 입력을 받아 사람만 결과를 쓰고 해마는 뒤에서 병행 실행하며 차이를 측정한다. 상용 플랫폼들이 tracing과 observability를 전면에 두는 이유는, agent 시스템의 품질이 최종 문장보다 중간행동의 품질에 더 크게 좌우되기 때문이다. citeturn6view1turn6view2turn9view1turn8view2

\#\#\# 안전성 윤리 검증

안전성과 윤리는 해마에서 별도 부속물이 아니라 실행 경로를 결정하는 정책층이다. OWASP는 prompt injection, sensitive information disclosure, data/model poisoning, supply chain 등을 주요 위험으로 제시하고 있고, NIST AI RMF는 trustworthiness 고려를 AI 설계·개발·사용·평가 전 과정에 통합하라고 권고한다. 에이전트 시스템에서 이 원칙은 최소 다섯 통제로 번역된다. 입력 정화, 도구 권한 최소화, memory write quarantine, 외부 에이전트 인증, 인간 개입 게이트다. 첨부파일의 proof-first 철학은 윤리 문제를 “좋은 의도”가 아니라 \*\*검증 가능한 운영 규칙\*\*으로 다루기 쉽게 만든다. citeturn30view0turn30view1turn30view3turn30view4turn29view0

윤리 측면에서 특히 중요한 것은 세 가지다. 첫째, 장기기억은 personalization 자산이면서 동시에 공격면이다. 둘째, 에이전트 협업은 책임 분산을 낳는다. 셋째, 자동화는 사람의 설명책임을 약화시킬 수 있다. 따라서 해마는 \`who decided\`, \`based on what\`, \`who approved\`, \`what changed memory\`, \`what was redacted\`를 반드시 남겨야 한다. 이는 기술 윤리의 추상 원칙을 운영 감사 로그로 번역하는 일이다. citeturn29view0turn24academia0turn30view2

\#\#\# 사례 연구

가장 적합한 사례 연구는 “심층 조사형 지식 작업”이다. 이 경우 해마는 사용자 요청을 research brief로 바꾸고, Research Agent가 자료를 수집하며, Critic이 근거 불충분·반례 누락을 점검하고, Builder가 구조화 보고서를 만들고, Verifier가 인용과 요구 섹션 충족 여부를 검사한다. 첨부파일이 이미 이런 하네스 패턴을 제시하고 있어, 해마의 초기 MVP는 문서형 산출물 작업에서 가장 빨리 성과를 낼 가능성이 높다. Research scenario에서 graph topology가 효과적이었다는 MultiAgentBench의 결과도 이 설계를 지지한다. fileciteturn0file0 fileciteturn0file2 citeturn25academia0

두 번째 사례는 “소프트웨어 및 운영 작업”이다. MetaGPT와 ChatDev는 역할 분업을 통해 요구분석-설계-구현-테스트를 연결했고, Voyager는 skill library와 iterative prompting을 통해 open-ended task에서 지속 학습을 보였다. 해마는 이를 소프트웨어/운영 맥락에 맞게 일반화할 수 있다. 예를 들어 incident triage에서 Ops Agent가 로그 수집, Research Agent가 관련 runbook 검색, Builder Agent가 remediation plan 작성, Policy Agent가 위험한 조치를 보류, Human reviewer가 승인하는 구조가 가능하다. 이 use case는 durable workflow, replay, auditability의 가치가 특히 크다. citeturn24academia3turn24academia1turn21academia1turn5view0

\#\#\# 유사 시스템 및 상용 솔루션 비교

| 범주 | 시스템 | 강점 | 약점 | 해마에 주는 시사점 |  
|---|---|---|---|---|  
| 오픈소스 런타임 | LangGraph | 장수명 상태·memory·HITL·graph orchestration | 저수준 설계 부담 | 해마의 core graph runtime 후보 citeturn6view2 |  
| SDK | OpenAI Agents SDK | agents/handoffs/guardrails/sessions/tracing의 균형 | 복잡한 기업 워크플로는 추가 계층 필요 | 해마의 Python-native agent layer 후보 citeturn6view1 |  
| 오픈소스 프레임워크 | Google ADK | graph workflows, multi-agent, evaluation, deployment | 구글 생태계 친화성 강함 | graph+agent 결합 방식 참고 citeturn8view1turn9view1 |  
| Managed Platform | Azure Foundry Agent Service | managed runtime, tools, observability, identity, security | 문서/권한 체계 진입장벽 | 해마의 엔터프라이즈 배포 대안 citeturn8view2 |  
| Managed Platform | Google Agent Platform | framework-hosting, tracing, skills, RAG, auth | 플랫폼 종속 우려 | 해마의 managed runtime 벤치마크 citeturn9view0 |  
| Managed Platform | Amazon Bedrock Agents | action groups, knowledge bases, traces, managed memory/security | 세밀한 agent topology 제어는 제한적 | 빠른 MVP 구축용 참고안 citeturn31view0 |  
| 연구형 MAS | AutoGen | agent conversation 패턴 유연 | 자유대화 오버헤드와 종료 난점 | contract-based handoff 필요성 확인 citeturn23academia3 |  
| 연구형 MAS | MetaGPT/ChatDev | SOP와 역할 분업 | 도메인 일반화 제한 | 해마의 SOP/skill card 구조에 적합 citeturn24academia3turn24academia1 |

여기서 중요한 반론도 함께 봐야 한다. 2026년 연구는 절차형 업무에서는 외부 오케스트레이션이 단일 모델 self-orchestration보다 못할 수 있음을 보였다. 따라서 해마는 “모든 상호작용을 graph workflow로 감싸는 것”이 아니라, 작업 난이도와 위험에 따라 \`single-hop\`, \`single-agent with tools\`, \`multi-agent supervised\`, \`multi-agent with HITL\`의 네 레벨을 선택해야 한다. 이것이 경제성과 성능을 동시에 지키는 현실적 전략이다. citeturn1academia5

\#\# 구현 로드맵과 위험 미래 연구

해마 구현은 한 번에 완성할 수 있는 제품이 아니라, \*\*하네스 규약 → 실행 런타임 → 기억 계층 → 검증 체계 → 운영 자동화\*\*로 점진적으로 성숙해야 하는 프로그램이다. 첨부자료가 이미 하네스와 운영 규율의 핵심을 제시하고 있으므로, 초기 단계는 “새 프레임워크 발명”보다 “기존 원칙의 강제 실행”에 집중해야 한다. 다시 말해 해마 프로젝트의 첫 성공조건은 새로운 agent를 많이 만드는 것이 아니라, 첨부파일이 요구하는 증빙·검증·상태 관리 원칙을 시스템으로 굳히는 것이다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2

\#\#\# 권장 기술스택

권장 기술스택은 다음 조합이 가장 현실적이다. 제어 및 API 계층은 Python/FastAPI, workflow는 Temporal 또는 LangGraph+checkpoint hybrid, agent runtime은 OpenAI Agents SDK 또는 LangGraph/ADK adaptor, 메시지 버스는 NATS JetStream, 구조화 상태는 PostgreSQL, 벡터검색은 pgvector 또는 독립 vector DB, artifact와 evidence는 object storage, observability는 OpenTelemetry \+ Prometheus, 배포는 Kubernetes, protocol gateway는 MCP/A2A adapter, approval console은 웹 UI로 구성한다. 이 스택은 현재 문헌·공식 문서에 비추어 과도하게 실험적이지 않으면서도 해마가 요구하는 상태성·확장성·관측성을 충족한다. citeturn5view0turn6view2turn6view1turn28view4turn28view2turn28view3turn28view0

\#\#\# 구현 로드맵 타임라인

| 단계 | 기간 예시 | 산출물 | 핵심 성공조건 |  
|---|---|---|---|  
| 원칙 고정 | 1\~3주 | Headmaster Spec v1, state schema, evidence schema | 첨부파일 원칙을 코드규약으로 변환 |  
| 하네스 MVP | 4\~8주 | task graph, agent registry, critic/verifier loop | proof bundle과 retry path 동작 |  
| 기억 MVP | 9\~12주 | STM/EPI/SEM/skill store, consolidation worker | episode write와 recall 품질 확보 |  
| 워크플로 내구화 | 13\~16주 | replay, checkpoints, human approval UI | 프로세스 재시작 후 복구 가능 |  
| 보안·정책 강화 | 17\~20주 | policy engine, MCP scan, permission controls | prompt/tool/memory attack surface 축소 |  
| 평가·파일럿 | 21\~28주 | benchmark suite, shadow deployment, KPI dashboard | 실제 업무에서 비용·정확도 기준 충족 |  
| 운영 고도화 | 29주 이후 | skill marketplace, adaptive routing, autoscaling | maintain 단계 자동화 진입 |

\`\`\`mermaid  
timeline  
    title 해마 구현 로드맵  
    section 설계 고정  
      원칙 고정 : 하네스 규약, 상태 스키마, 증빙 규약  
      참조 아키텍처 : 런타임, 메모리, 메시지 버스 결정  
    section MVP  
      하네스 MVP : registry, scheduler, critic, verifier  
      기억 MVP : STM/EPI/SEM/SKILL/EVID 저장소  
      승인 UI : human-in-the-loop 콘솔  
    section 내구화  
      workflow 내구화 : replay, retries, checkpoints  
      보안 강화 : policy gate, auth, redaction, quarantine  
      observability : traces, metrics, audits, evals  
    section 파일럿  
      shadow mode : 실사용 데이터 병행평가  
      파일럿 배포 : 제한된 도메인 운영  
      KPI 보정 : 비용, 지연, 정확도, 안전성 최적화  
    section 운영  
      skill 승격 자동화 : reuse-based consolidation  
      adaptive routing : topology/model tiering  
      멀티프로토콜 연동 : MCP, A2A, managed platforms  
\`\`\`

\#\#\# 위험과 완화책 표

| 위험 | 설명 | 영향 | 완화책 |  
|---|---|---|---|  
| 증거 없는 생성 | 에이전트가 출처 없이 결론을 서술 | 신뢰 붕괴 | \`No Zero-Shot Invention\`, claim-evidence binding, verifier fail-fast fileciteturn0file2 |  
| 메모리 오염 | 잘못된 경험이 장기기억으로 승격 | 오류 전파 | quarantine, contradiction detection, selective consolidation citeturn21academia2turn25academia2 |  
| 도구 설명 불량 | MCP tool description quality 저하 | tool misselection, 비용 증가 | description linter, compact schema, runtime feedback citeturn1academia3 |  
| 프로토콜 공격 | prompt injection, tool poisoning, auth gap | 데이터 유출, 권한 남용 | signed manifests, allowlist, least privilege, human approval citeturn1academia0turn30view3turn30view4 |  
| 오케스트레이션 과사용 | 불필요한 multi-agent 구성 | 지연·비용 증가 | conditional orchestration, simple-path fallback citeturn1academia5 |  
| 종료 조건 상실 | agent 간 끝없는 상호작용 | 비용 폭주 | max depth, max turns, budget ledger, terminal criteria |  
| human bottleneck | 승인 절차가 지나치게 많음 | 처리량 저하 | risk-tier 기반 selective approval |  
| 재현 불가 | 같은 입력에서 상이한 경로 | 디버깅 실패 | event sourcing, replay, deterministic policy windows citeturn5view0 |  
| 플랫폼 종속 | 특정 managed platform 종속 | 이식성 저하 | protocol-first, internal canonical schemas |  
| 보안·윤리 규정 미정 | 조직 정책 부재 | 배포 지연 | NIST AI RMF 기반 governance baseline citeturn30view0turn30view1 |

\#\#\# 미래 연구

미래 연구는 세 갈래로 나뉜다. 첫째는 \*\*adaptive orchestration\*\*이다. 언제 단일 agent로 충분하고 언제 multi-agent가 필요한지, 언제 graph topology가 필요한지 자동으로 판정해야 한다. 최근 연구의 반론을 고려하면 이는 단순 최적화가 아니라 해마의 정체성에 가까운 문제다. 둘째는 \*\*memory governance\*\*다. 무엇을 저장하고 무엇을 버릴지, 어떤 기억을 누가 승인해야 하는지, 기억 중복·모순·노후화를 어떻게 측정할지에 대한 연구가 더 필요하다. 셋째는 \*\*protocol security and interoperability\*\*다. MCP와 A2A가 빠르게 확산되는 만큼, 인증·감사·위임 체인·교차 프로토콜 구성 안전성은 해마의 핵심 연구 주제가 된다. citeturn1academia5turn25academia2turn21academia2turn12view1turn1academia0turn13academia0

\#\#\# 개방 쟁점과 한계

이 보고서는 첨부파일과 공신력 있는 논문·공식 문서를 최대한 통합해 설계안을 제안했지만, 몇 가지는 여전히 조직별 상수로 남는다. 첫째, 해마가 단일 조직 내부 시스템인지, 외부 고객-facing 시스템인지에 따라 보안·승인 설계가 달라진다. 둘째, 어느 모델 공급자를 주력으로 쓸지에 따라 agent runtime의 최적 경로가 달라진다. 셋째, 기억의 retention 기간과 법적 보존정책은 실제 기업 규정과 연결되어야 한다. 넷째, A2A/MCP 채택 범위는 생태계 성숙도와 신뢰경계에 따라 달라진다. 다섯째, 첨부파일의 I-B-F 루프와 일부 운영 규칙은 실구현 전에 조직 내부 용어 사전으로 더 엄밀히 표준화할 필요가 있다. 이 한계는 본 보고서의 약점이라기보다, 해마가 실제로 “시스템”이기 때문에 불가피하게 필요한 마지막 맞춤화 단계다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2

종합하면, 해마는 새로운 유행어가 아니라 충분히 실현 가능한 \*\*에이전트 운영 아키텍처\*\*다. 다만 성공하려면 모델 성능 경쟁보다 하네스 규율, 상태 관리, 기억 계층화, 검증 게이트, 관측 가능성, 비용·보안 제어를 더 우선해야 한다. 첨부자료가 이미 그 방향을 제시하고 있으며, 현대 agent runtime·memory 연구와 상용 플랫폼은 이를 구현할 수 있는 도구를 제공한다. 해마의 구현은 결국 “더 똑똑한 모델”을 만드는 일이 아니라, \*\*여러 모델과 도구와 기억과 사람을 책임 있게 연주시키는 지휘 체계\*\*를 만드는 일이다. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 citeturn6view2turn6view1turn5view0turn12view1turn30view0  
