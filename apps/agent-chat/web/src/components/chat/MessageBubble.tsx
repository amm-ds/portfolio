import type { Citation } from "../../lib/chat/events";
import type { Part } from "../../lib/chat/parts";
import type { DisplayMessage } from "../../lib/chat/useChat";
import { Markdown } from "../../lib/markdown";
import { ApprovalCard } from "./ApprovalCard";
import { ToolCallCard } from "./ToolCallCard";

interface Props {
  from: "user" | "assistant";
  content: string;
  parts?: Part[];
  citations?: Citation[];
  uncertainty?: string;
  locked?: boolean;
  onRespondApproval?: (id: string, approved: boolean) => void;
}

export function MessageBubble({
  from,
  content,
  parts,
  citations,
  uncertainty,
  locked = false,
  onRespondApproval,
}: Props) {
  return (
    <div className={`bubble bubble--${from}`}>
      <div className="bubble-role">{from === "user" ? "you" : "agent"}</div>
      <div className="bubble-body">
        {parts
          ? parts.map((part, i) => {
              if (part.kind === "text") return <Markdown key={i} text={part.text} />;
              if (part.kind === "tool_call") return <ToolCallCard key={part.call.id} call={part.call} />;
              return (
                <ApprovalCard
                  key={part.approval.id}
                  approval={part.approval}
                  locked={locked || part.approval.status !== "pending"}
                  onRespond={onRespondApproval ?? (() => undefined)}
                />
              );
            })
          : content !== "" && <Markdown text={content} />}
        {citations && citations.length > 0 && (
          <div className="citations">
            <span className="citations-label">sources</span>
            {citations.map((c, i) => (
              <span key={i} className="citation" title={c.snippet}>
                {c.source}
                {c.locator ? ` · ${c.locator}` : ""}
              </span>
            ))}
          </div>
        )}
        {uncertainty && <p className="uncertainty">⚠ {uncertainty}</p>}
      </div>
    </div>
  );
}

export type { DisplayMessage };
