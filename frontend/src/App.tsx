import { useState } from "react";

import { getMetrics, listApprovals, listTasks } from "./api";
import { ApprovalQueue } from "./components/ApprovalQueue";
import { MetricsPanel } from "./components/MetricsPanel";
import { TaskDetail } from "./components/TaskDetail";
import { TaskForm } from "./components/TaskForm";
import { TaskList } from "./components/TaskList";
import { usePolling } from "./hooks";

export function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const tasks = usePolling(listTasks, 2000);
  const approvals = usePolling(listApprovals, 1500);
  const metrics = usePolling(getMetrics, 3000);

  const taskList = tasks.data ?? [];
  const selectedTask = taskList.find((task) => task.task_id === selectedId) ?? null;

  const refreshAll = () => {
    tasks.refresh();
    approvals.refresh();
    metrics.refresh();
  };

  return (
    <div className="layout">
      <header>
        <h1>
          해마 <span className="en">Headmaster</span> Control Dashboard
        </h1>
        <p className="muted">
          No Zero-Shot Invention / I-B-F Loop / Evidence-Based Orchestration
        </p>
      </header>

      <MetricsPanel metrics={metrics.data} />

      <div className="columns">
        <div className="column">
          <TaskForm
            onCreated={(taskId) => {
              setSelectedId(taskId);
              refreshAll();
            }}
          />
          <ApprovalQueue tickets={approvals.data ?? []} onResolved={refreshAll} />
        </div>
        <div className="column wide">
          <TaskList tasks={taskList} selectedId={selectedId} onSelect={setSelectedId} />
          {selectedTask && <TaskDetail task={selectedTask} />}
        </div>
      </div>
    </div>
  );
}
