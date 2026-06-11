import type { Metrics } from "../types";

interface Props {
  metrics: Metrics | null;
}

export function MetricsPanel({ metrics }: Props) {
  const cards: Array<{ label: string; value: string }> = metrics
    ? [
        { label: "작업", value: `${metrics.completed}/${metrics.total_tasks} 완료` },
        { label: "성공률", value: `${(metrics.task_success_rate * 100).toFixed(0)}%` },
        { label: "증거 커버리지", value: `${(metrics.evidence_coverage * 100).toFixed(0)}%` },
        {
          label: "Critic",
          value: `승인 ${metrics.critiques_approved} / 반려 ${metrics.critiques_rejected}`,
        },
        { label: "Zero-shot 탐지", value: `${metrics.zero_shot_detections}건` },
        { label: "모델 호출", value: `${metrics.model_calls}회` },
        { label: "추정 비용", value: `$${metrics.est_cost_usd.toFixed(4)}` },
      ]
    : [];

  return (
    <section className="panel metrics">
      <h2>운영 지표</h2>
      {metrics === null ? (
        <p className="muted">불러오는 중…</p>
      ) : (
        <div className="metric-grid">
          {cards.map((card) => (
            <div key={card.label} className="metric-card">
              <span className="metric-label">{card.label}</span>
              <span className="metric-value">{card.value}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
