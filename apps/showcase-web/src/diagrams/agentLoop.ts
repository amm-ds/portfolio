import type { DiagramSpec } from "./types";

// Facts: projects/09-agentic-workflows/{README.md,params.yaml,reports/metrics.json}.
export const AGENT_LOOP_SPEC = {
  id: "09-agent-loop",
  title: "Plan → act → check: the bounded agent loop",
  direction: "LR",
  canvasHeight: 520,
  nodes: [
    {
      id: "task",
      label: "Task + expected tools",
      kind: "source",
      facts: [
        "15/15 fixed tuning tasks passed; 13/13 unseen answer tasks passed with exact tool sets.",
        "5/6 should-fail probes produced a graded refusal.",
        "Per-task budgets: 8 steps, 60 seconds, and $0.25 cloud-equivalent cost.",
      ],
    },
    {
      id: "plan",
      label: "Plan · typed steps + calls",
      kind: "agent",
      facts: [
        "The planner emits typed steps and intended calls from the whitelisted toolset.",
        "Hosted usage limits: 400 requests and 4,000,000 total tokens per suite.",
      ],
    },
    {
      id: "checkpoint",
      label: "Human checkpoint",
      kind: "gate",
      facts: [
        "Consequential runs pause for approve, reject-with-feedback, or park/resume.",
        "data/checkpoint.json records pause, rejection feedback, and re-planning.",
      ],
    },
    {
      id: "execute",
      label: "Execute · bounded retries",
      kind: "agent",
      facts: [
        "Only Execute invokes tools; one repair retry and one critique revision are allowed.",
        "The tuning run captured 30/30 planned calls: 100% call precision and tool recall.",
      ],
    },
    {
      id: "search-documents",
      label: "search_documents · Wikipedia",
      kind: "tool",
      facts: [
        "Read-only FAISS + MiniLM retrieval over 3,589 Wikipedia chunks from project 01.",
        "Task t15 used two search_documents lookups, then calculator; zero retries.",
      ],
    },
    {
      id: "search-handbook",
      label: "search_handbook · handbook",
      kind: "tool",
      facts: [
        "Keyword search over the fixed synthetic 12-document Atlas Valley handbook.",
        "The tuning run captured 13 search_handbook calls, all planned.",
      ],
    },
    {
      id: "calculator",
      label: "calculator · locked-down AST",
      kind: "tool",
      facts: [
        "The locked-down AST evaluator accepts arithmetic only; unsupported work fails loudly.",
        "The tuning run captured 11 calculator calls, all planned.",
      ],
    },
    {
      id: "critique",
      label: "Critique · tools vs plan",
      kind: "agent",
      facts: [
        "Critique audits tools used against the plan and can request one revision through Execute.",
        "Every transition is serialized in the StepTrace ledger for deterministic offline grading.",
      ],
    },
    {
      id: "ledger",
      label: "StepTrace ledger",
      kind: "data",
      facts: [
        "Every node transition, tool call, approval, token count, and latency is recorded for replay.",
        "Offline grading re-checks the captured record without another provider call or additional spend.",
      ],
    },
    {
      id: "result",
      label: "WorkflowResult",
      kind: "output",
      facts: [
        "Record suite: 15/15 fixed tasks and 13/13 unseen answers passed.",
        "Approximately $0.13 cloud-equivalent cost against the $2.00 suite cap (~85k input / ~12k output tokens).",
      ],
    },
    {
      id: "failure",
      label: "Failure End · typed message",
      kind: "output",
      facts: [
        "Retries end in a typed failure rather than an unbounded loop or invented answer.",
        "Held-out should-fail probes: 5/6 passed; the miss was a failure-message wording gap, not a fabricated number.",
      ],
    },
  ],
  edges: [
    { id: "task-plan", source: "task", target: "plan", kind: "task", label: "task" },
    { id: "plan-checkpoint", source: "plan", target: "checkpoint", kind: "task", label: "consequential run" },
    { id: "plan-execute", source: "plan", target: "execute", kind: "task", label: "routine" },
    { id: "checkpoint-execute", source: "checkpoint", target: "execute", kind: "task", label: "approve" },
    { id: "checkpoint-plan", source: "checkpoint", target: "plan", kind: "error", label: "reject + feedback" },
    { id: "checkpoint-park", source: "checkpoint", target: "checkpoint", kind: "task", label: "park / resume" },
    { id: "execute-documents", source: "execute", target: "search-documents", kind: "task", label: "call" },
    { id: "execute-handbook", source: "execute", target: "search-handbook", kind: "task", label: "call" },
    { id: "execute-calculator", source: "execute", target: "calculator", kind: "task", label: "call" },
    { id: "documents-critique", source: "search-documents", target: "critique", kind: "result", label: "result" },
    { id: "handbook-critique", source: "search-handbook", target: "critique", kind: "result", label: "result" },
    { id: "calculator-critique", source: "calculator", target: "critique", kind: "result", label: "result" },
    { id: "execute-critique", source: "execute", target: "critique", kind: "result", label: "trace" },
    { id: "execute-ledger", source: "execute", target: "ledger", kind: "result", label: "record" },
    { id: "execute-repair", source: "execute", target: "execute", kind: "error", label: "repair within cap" },
    { id: "critique-execute", source: "critique", target: "execute", kind: "error", label: "revise once" },
    { id: "critique-result", source: "critique", target: "result", kind: "result", label: "pass" },
    { id: "execute-failure", source: "execute", target: "failure", kind: "error", label: "retries exhausted" },
  ],
} as const satisfies DiagramSpec;
