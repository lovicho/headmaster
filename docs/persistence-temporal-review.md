# PostgreSQL / Temporal 검토

이 문서는 Headmaster의 현재 SQLite 이벤트 소싱 구조를 PostgreSQL과 Temporal로 확장할 때의 판단 기준을 정리합니다.

## 현재 구조

현재 Headmaster는 로컬 운영과 검증을 우선해 다음 저장소를 SQLite로 둡니다.

| 저장소 | 현재 구현 | 역할 |
| --- | --- | --- |
| Event store | `backend/headmaster/storage/event_store.py` | 모든 task/event trace의 source of truth |
| Memory store | `backend/headmaster/execution_plane/memory/fabric.py` | 승인/격리된 지식 자산 저장 |
| Artifact store | filesystem | 발행 산출물 Markdown 저장 |

현재 replay 원칙은 명확합니다.

- 모델을 다시 호출하지 않습니다.
- 저장된 이벤트만 읽어서 상태를 복원합니다.
- 재시작 후 완료된 작업, 승인 ticket, artifact metadata를 조회할 수 있습니다.
- 일부 중간 승인 재개는 자동화하지 않고 conflict로 처리합니다.

## PostgreSQL 도입 판단

PostgreSQL은 Headmaster가 팀 단위 또는 장기 운영으로 넘어갈 때 우선순위가 높습니다.

### 장점

- SQLite보다 동시 writer와 긴 실행 작업에 강합니다.
- event query, projection, dashboard filter를 확장하기 쉽습니다.
- JSONB index로 `event.data` 검색을 최적화할 수 있습니다.
- backup, migration, monitoring 체계가 성숙합니다.
- Memory Fabric의 salience/confidence 검색과 metadata query를 구조화하기 좋습니다.

### 권장 스키마 초안

```sql
create table task_events (
  seq bigserial primary key,
  task_id text not null,
  event_id text not null unique,
  event_type text not null,
  source text not null,
  subject text,
  occurred_at timestamptz not null,
  data jsonb not null
);

create index idx_task_events_task_seq on task_events (task_id, seq);
create index idx_task_events_type_time on task_events (event_type, occurred_at);
create index idx_task_events_data_gin on task_events using gin (data);

create table memory_records (
  seq bigserial primary key,
  memory_id text not null unique,
  scope text not null,
  summary text not null,
  content text,
  tags text[] not null default '{}',
  salience double precision not null,
  confidence double precision not null,
  source_refs jsonb not null default '[]',
  quarantined boolean not null default false,
  created_at timestamptz not null
);

create index idx_memory_active_score
  on memory_records (quarantined, scope, salience, confidence);
create index idx_memory_tags on memory_records using gin (tags);
```

### 마이그레이션 순서

1. `EventStore` protocol/interface를 정의합니다.
2. 현재 SQLite 구현을 `SQLiteEventStore`로 명시합니다.
3. 동일 contract의 `PostgresEventStore`를 추가합니다.
4. `HEADMASTER_EVENT_STORE_URL` 또는 설정 파일로 backend를 선택합니다.
5. replay/projection 테스트를 SQLite와 PostgreSQL 공통 테스트로 분리합니다.
6. Memory Fabric도 같은 방식으로 `SQLiteMemoryStore`와 `PostgresMemoryStore`를 분리합니다.
7. artifact는 filesystem 유지 후 object storage abstraction을 별도 단계로 둡니다.

### 도입 기준

PostgreSQL은 다음 조건 중 하나가 생기면 도입합니다.

- 동시에 여러 작업을 장시간 실행합니다.
- dashboard에서 event trace 검색/필터가 중요해집니다.
- 운영 환경에서 backup/restore와 migration이 필요합니다.
- 여러 사용자 또는 여러 Headmaster process가 같은 event store를 공유합니다.

## Temporal 도입 판단

Temporal은 Headmaster가 “장기 실행, 승인 대기, 재시작 재개, 재시도 정책”을 더 강하게 보장해야 할 때 유력합니다.

### 장점

- workflow replay와 activity retry가 플랫폼 레벨에서 제공됩니다.
- 승인 대기 같은 long-running state를 안정적으로 유지할 수 있습니다.
- 모델 호출, tool call, artifact publish를 activity로 분리하기 좋습니다.
- 실패한 activity만 재시도하고 workflow history를 보존할 수 있습니다.

### 주의할 점

- Temporal workflow code는 deterministic해야 합니다.
- 모델 호출, clock, random ID, 파일 IO 같은 side effect는 workflow 안이 아니라 activity 안에 둬야 합니다.
- 현재 Headmaster의 event store가 이미 source of truth 역할을 하므로, Temporal event history와 Headmaster event log의 책임을 분리해야 합니다.
- 도입 초기에는 모든 오케스트레이션을 Temporal로 옮기기보다, 승인 대기와 장기 phase run만 감싸는 방식이 안전합니다.

### 권장 매핑

| Headmaster 개념 | Temporal 개념 |
| --- | --- |
| `run_task` | Workflow |
| `run_orchestra` | Workflow with phase loop |
| model call | Activity |
| tool call | Activity |
| critic review | Activity |
| human approval | Signal 또는 Update |
| event emission | Activity 또는 workflow-side deterministic command wrapper |
| artifact publish | Activity |

### 단계적 도입안

1. 현재 Orchestrator는 유지합니다.
2. `TemporalTaskRunner`를 추가해 `Orchestrator.run_task`를 activity 단위로 호출하는 thin wrapper를 만듭니다.
3. 승인 대기는 Temporal Signal로 받고, Headmaster event log에는 기존 approval event를 그대로 씁니다.
4. event log는 여전히 Headmaster의 audit source로 유지합니다.
5. Temporal history는 durable execution source로만 사용합니다.
6. PostgreSQL event store가 안정화된 뒤 Temporal을 붙입니다.

## 결론

권장 순서는 다음과 같습니다.

1. PostgreSQL event store abstraction
2. PostgreSQL memory store abstraction
3. artifact storage abstraction
4. Temporal thin workflow wrapper
5. phase-level Temporal orchestration
6. full workflow migration 검토

즉, 지금 당장 Temporal부터 도입하기보다 PostgreSQL persistence boundary를 먼저 분리하는 것이 안전합니다. 현재 Headmaster의 이벤트 소싱 모델은 PostgreSQL로 자연스럽게 확장되며, Temporal은 그 위에서 long-running execution reliability를 보강하는 계층으로 두는 편이 좋습니다.
