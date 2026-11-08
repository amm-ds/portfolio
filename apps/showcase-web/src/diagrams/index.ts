import { AGENT_CHAT_ARCHITECTURE_SPEC } from "./agentChatArchitecture";
import { AGENT_LOOP_SPEC } from "./agentLoop";
import { CHURN_CYCLE_SPEC } from "./churnCycle";
import { DETECTION_PIPELINE_SPEC } from "./detectionPipeline";
import { DOCUMENT_INTELLIGENCE_ARCHITECTURE_SPEC } from "./documentIntelligenceArchitecture";
import { ENGINE_BENCHMARK_SPEC } from "./engineBenchmark";
import { LIFECYCLE_PIPELINE_SPEC } from "./lifecyclePipeline";
import { M5_PIPELINE_SPEC } from "./m5Pipeline";
import { MOBILITY_PIPELINE_SPEC } from "./mobilityPipeline";
import { RAG_PIPELINE_SPEC } from "./ragPipeline";
import { ROUTING_SPEC } from "./routing";
import { SERVING_BENCHMARK_SPEC } from "./servingBenchmark";
import { SERVING_PIPELINE_SPEC } from "./servingPipeline";
import { SOLVER_LADDER_SPEC } from "./solverLadder";
import type { DiagramSpec } from "./types";
import { UPLIFT_JUDGING_SPEC } from "./upliftJudging";

export const DIAGRAM_SPECS = {
  "09-agent-loop": AGENT_LOOP_SPEC,
  "04-routing": ROUTING_SPEC,
  "01-rag-pipeline": RAG_PIPELINE_SPEC,
  "02-m5-pipeline": M5_PIPELINE_SPEC,
  "03-detection-pipeline": DETECTION_PIPELINE_SPEC,
  "05-churn-cycle": CHURN_CYCLE_SPEC,
  "06-solver-ladder": SOLVER_LADDER_SPEC,
  "07-mobility-pipeline": MOBILITY_PIPELINE_SPEC,
  "08-serving-benchmark": SERVING_BENCHMARK_SPEC,
  "10-uplift-judging": UPLIFT_JUDGING_SPEC,
  "11-engine-benchmark": ENGINE_BENCHMARK_SPEC,
  "12-lifecycle-pipeline": LIFECYCLE_PIPELINE_SPEC,
  "13-serving-pipeline": SERVING_PIPELINE_SPEC,
  "app-agent-chat-architecture": AGENT_CHAT_ARCHITECTURE_SPEC,
  "app-document-intelligence-architecture": DOCUMENT_INTELLIGENCE_ARCHITECTURE_SPEC,
} as const satisfies Record<string, DiagramSpec>;

export type DiagramSpecId = keyof typeof DIAGRAM_SPECS;

export function getDiagramSpec(specId: string): DiagramSpec | undefined {
  if (!Object.prototype.hasOwnProperty.call(DIAGRAM_SPECS, specId)) return undefined;
  return DIAGRAM_SPECS[specId as DiagramSpecId];
}

export {
  AGENT_CHAT_ARCHITECTURE_SPEC,
  AGENT_LOOP_SPEC,
  CHURN_CYCLE_SPEC,
  DETECTION_PIPELINE_SPEC,
  DOCUMENT_INTELLIGENCE_ARCHITECTURE_SPEC,
  ENGINE_BENCHMARK_SPEC,
  LIFECYCLE_PIPELINE_SPEC,
  M5_PIPELINE_SPEC,
  MOBILITY_PIPELINE_SPEC,
  RAG_PIPELINE_SPEC,
  ROUTING_SPEC,
  SERVING_BENCHMARK_SPEC,
  SERVING_PIPELINE_SPEC,
  SOLVER_LADDER_SPEC,
  UPLIFT_JUDGING_SPEC,
};
export type { DiagramSpec } from "./types";
