import { useState } from "react";

import { resolveApproval } from "../api";
import type { ApprovalTicket } from "../types";

interface Props {
  tickets: ApprovalTicket[];
  onResolved: () => void;
}

const KIND_LABEL: Record<ApprovalTicket["kind"], string> = {
  publish: "발행 승인",
  budget_overrun: "예산 초과",
  phase_gate: "단계 게이트",
};

export function ApprovalQueue({ tickets, onResolved }: Props) {
  const [busy, setBusy] = useState<string | null>(null);

  const handleResolve = async (ticketId: string, granted: boolean) => {
    setBusy(ticketId);
    try {
      await resolveApproval(ticketId, granted, "dashboard");
      onResolved();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="panel">
      <h2>
        승인 대기 {tickets.length > 0 && <span className="badge">{tickets.length}</span>}
      </h2>
      {tickets.length === 0 ? (
        <p className="muted">대기 중인 승인이 없습니다.</p>
      ) : (
        <ul className="ticket-list">
          {tickets.map((ticket) => (
            <li key={ticket.ticket_id} className="ticket">
              <div>
                <span className="kind">{KIND_LABEL[ticket.kind]}</span>
                <code className="task-ref">{ticket.task_id}</code>
              </div>
              <p className="reason">{ticket.reason}</p>
              <div className="actions">
                <button
                  className="approve"
                  disabled={busy === ticket.ticket_id}
                  onClick={() => void handleResolve(ticket.ticket_id, true)}
                >
                  승인
                </button>
                <button
                  className="deny"
                  disabled={busy === ticket.ticket_id}
                  onClick={() => void handleResolve(ticket.ticket_id, false)}
                >
                  거절
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
