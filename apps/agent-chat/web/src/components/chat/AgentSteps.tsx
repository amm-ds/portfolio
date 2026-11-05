import type { Part } from "../../lib/chat/parts";
import { deriveSteps } from "../../lib/chat/parts";

const KIND_LABEL: Record<string, string> = {
  plan: "plan",
  tool: "tool",
  critique: "critique",
  answer: "answer",
};

/** The run's step timeline (plan → tool calls → critique → answer). */
export function AgentSteps({ parts, running }: { parts: Part[]; running: boolean }) {
  const steps = deriveSteps(parts);
  if (steps.length === 0) return null;
  return (
    <ol className="agent-steps" aria-label="agent steps">
      {steps.map((step, i) => {
        const last = i === steps.length - 1;
        const status = step.status === "done" && running && last ? "running" : step.status;
        return (
          <li key={i} className={`agent-step agent-step--${status}`}>
            <span className="agent-step-glyph" aria-hidden="true">
              {status === "running" ? "▸" : status === "pending" ? "○" : status === "error" ? "✗" : "●"}
            </span>
            <span className="agent-step-kind">{KIND_LABEL[step.kind]}</span>
            <span className="agent-step-label">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
