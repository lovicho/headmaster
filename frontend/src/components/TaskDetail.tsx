import { useEffect, useState } from "react";

import { getArtifact, getEvents } from "../api";
import type { ArtifactResponse, EventRecord, TaskStatus } from "../types";

interface Props {
  task: TaskStatus;
}

export function TaskDetail({ task }: Props) {
  const [artifact, setArtifact] = useState<ArtifactResponse | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);

  useEffect(() => {
    setArtifact(null);
    if (task.artifact_id) {
      getArtifact(task.task_id)
        .then(setArtifact)
        .catch(() => setArtifact(null));
    }
    getEvents(task.task_id)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [task.task_id, task.artifact_id, task.state]);

  return (
    <section className="panel detail">
      <h2>
        작업 상세 <code>{task.task_id}</code>
      </h2>
      <p>
        상태: <strong>{task.state}</strong>
        {task.failure_reason && <span className="error"> ({task.failure_reason})</span>}
      </p>
      {task.supplied_asset_ids.length > 0 && (
        <p className="muted">
          공급 자산 {task.supplied_asset_ids.length}개 / 재사용{" "}
          {task.reused_asset_ids.length}개
        </p>
      )}

      <h3>Critic 판정</h3>
      <ul className="critique-list">
        {task.critiques.map((critique, index) => (
          <li
            key={`${critique.target_agent}-${index}`}
            className={critique.status === "APPROVED" ? "ok" : "fail"}
          >
            {critique.target_agent}: {critique.status}
            {critique.zero_shot_detected && <span className="badge warn">zero-shot</span>}
            {critique.rejection_codes.map((code) => (
              <span key={code} className="badge fail">
                {code}
              </span>
            ))}
            {critique.rejection_categories.map((category) => (
              <span key={category} className="badge muted-badge">
                {category}
              </span>
            ))}
          </li>
        ))}
      </ul>

      {artifact && (
        <>
          <h3>
            산출물 <code className="muted">{artifact.content_hash.slice(0, 16)}</code>
          </h3>
          <pre className="artifact">{artifact.content}</pre>
        </>
      )}

      <h3>이벤트 트레이스 ({events.length})</h3>
      <ol className="event-list">
        {events.map((event) => (
          <li key={event.id}>
            <code>{event.type}</code>
            {event.type === "state.changed" && (
              <span className="muted">
                {" "}
                {String(event.data["from"])} -&gt; {String(event.data["to"])}
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
