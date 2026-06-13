import type { TaskStatus } from "../types";

interface Props {
  tasks: TaskStatus[];
  selectedId: string | null;
  onSelect: (taskId: string) => void;
}

const STATE_CLASS: Record<string, string> = {
  completed: "state-ok",
  failed: "state-fail",
  awaiting_human_approval: "state-wait",
};

export function TaskList({ tasks, selectedId, onSelect }: Props) {
  return (
    <section className="panel">
      <h2>작업 목록</h2>
      {tasks.length === 0 ? (
        <p className="muted">아직 작업이 없습니다.</p>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Task</th>
                <th>상태</th>
                <th>Critic</th>
                <th>재사용</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr
                  key={task.task_id}
                  className={task.task_id === selectedId ? "selected" : ""}
                  onClick={() => onSelect(task.task_id)}
                >
                  <td>
                    <code>{task.task_id.slice(0, 12)}...</code>
                  </td>
                  <td>
                    <span className={`state ${STATE_CLASS[task.state] ?? "state-run"}`}>
                      {task.state}
                      {task.running ? " 실행 중" : ""}
                    </span>
                  </td>
                  <td>
                    {task.critiques.filter((critique) => critique.status === "APPROVED").length}/
                    {task.critiques.length}
                  </td>
                  <td>{task.reused_asset_ids.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
