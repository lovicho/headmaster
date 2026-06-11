import { useState } from "react";

import { createTask } from "../api";

interface Props {
  onCreated: (taskId: string) => void;
}

const HARNESSES = [
  "content",
  "planner",
  "researcher",
  "consultant",
  "design",
  "dev_fe_be",
  "secops_qa",
  "knowledge_manager",
  "critic",
];

export function TaskForm({ onCreated }: Props) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"single" | "orchestra">("single");
  const [harness, setHarness] = useState("content");
  const [needsApproval, setNeedsApproval] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const response = await createTask({
        text,
        needs_human_approval: needsApproval,
        ...(mode === "orchestra" ? { orchestra: "b2b_website_v8" } : { harness }),
      });
      setText("");
      onCreated(response.task_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="panel">
      <h2>새 작업</h2>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="작업 내용을 입력하세요…"
          rows={3}
        />
        <div className="form-row">
          <label>
            <input
              type="radio"
              checked={mode === "single"}
              onChange={() => setMode("single")}
            />
            단일 에이전트
          </label>
          <label>
            <input
              type="radio"
              checked={mode === "orchestra"}
              onChange={() => setMode("orchestra")}
            />
            오케스트라 (b2b_website_v8)
          </label>
        </div>
        {mode === "single" && (
          <select value={harness} onChange={(event) => setHarness(event.target.value)}>
            {HARNESSES.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        )}
        <label className="checkbox">
          <input
            type="checkbox"
            checked={needsApproval}
            onChange={(event) => setNeedsApproval(event.target.checked)}
          />
          인간 승인 필요 (HITL)
        </label>
        <button type="submit" disabled={submitting || !text.trim()}>
          {submitting ? "제출 중…" : "작업 제출"}
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </section>
  );
}
