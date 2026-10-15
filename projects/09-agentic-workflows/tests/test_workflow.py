"""Unit tests for the Plan → Execute → Critique graph (offline, scripted model)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from agentic_workflows.schemas import WorkflowResult, WorkflowState
from agentic_workflows.workflow import build_workflow_graph, run_workflow
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

if TYPE_CHECKING:
    from conftest import ScriptedModelFactory


class TestWorkflowGraph:
    def test_happy_path_produces_structured_result(
        self, make_scripted_model: ScriptedModelFactory
    ) -> None:
        result = run_workflow(
            "How many liters of diesel does the generator burn in one week?",
            model=make_scripted_model(),
        )
        assert isinstance(result, WorkflowResult)
        assert "75.6" in result.answer
        assert result.steps_taken[0].startswith("plan (")
        assert "critique: pass" in result.steps_taken
        assert result.confidence == 0.9  # self-confidence, no critique damping
        assert result.retries == 0
        assert result.critique_loops == 0
        assert result.input_tokens > 0 and result.output_tokens > 0

    def test_execute_repair_path_retries_then_recovers(
        self, make_scripted_model: ScriptedModelFactory
    ) -> None:
        # more failures than the node's inner retry wrapper (3 attempts) absorbs
        result = run_workflow("weekly diesel?", model=make_scripted_model(fail_executions=4))
        assert result.retries == 1
        assert "75.6" in result.answer
        assert result.steps_taken.count("execute (attempt 1)") == 1
        assert result.steps_taken.count("execute (attempt 2)") == 1

    def test_execute_failure_beyond_budget_ends_gracefully(
        self, make_scripted_model: ScriptedModelFactory
    ) -> None:
        result = run_workflow("weekly diesel?", model=make_scripted_model(fail_executions=10))
        assert result.retries == 2  # 1 initial + 1 bounded repair
        assert result.confidence == 0.0
        assert "could not complete" in result.answer

    def test_critique_loop_back_to_execute_once(
        self, make_scripted_model: ScriptedModelFactory
    ) -> None:
        result = run_workflow("weekly diesel?", model=make_scripted_model(verdict="revise"))
        assert result.critique_loops == 1
        assert "critique: revise → re-execute" in result.steps_taken
        # the scripted critique never passes; after the single allowed loop the
        # graph proceeds with the draft and a damped confidence
        assert result.steps_taken[-1] == "critique: revise"
        assert result.confidence == 0.75  # 0.9 - 0.10 loop - 0.05 issue

    def test_state_is_serializable_for_checkpoints(self) -> None:
        state = WorkflowState(task="t", plan=[], max_execute_retries=1)
        restored = WorkflowState.model_validate_json(state.model_dump_json())
        assert restored == state

    def test_graph_builds_at_all_valid_entry_points(self) -> None:
        from agentic_workflows.workflow import CritiqueNode, ExecuteNode, PlanNode

        for entry in (PlanNode, ExecuteNode, CritiqueNode):
            graph = build_workflow_graph(entry)
            assert graph is not None


class TestToolCallTracking:
    def test_tools_used_are_recorded_in_order(self) -> None:
        # Scripted model that forces a real search_handbook call in Execute.
        def responder(messages: list[Any], info: Any) -> ModelResponse:
            from pydantic_ai.messages import ToolCallPart

            role = ""
            saw_response = False
            for message in messages:
                if isinstance(message, ModelResponse):
                    saw_response = True
                for part in getattr(message, "parts", []):
                    content = getattr(part, "content", "")
                    if isinstance(content, str):
                        if "PLANNER" in content:
                            role = "plan"
                        elif "EXECUTOR" in content:
                            role = "exec"
                        elif "CRITIQUE" in content:
                            role = "critique"
            if role == "plan":
                payload: dict[str, Any] = {
                    "steps": [
                        {
                            "id": 1,
                            "description": "Search handbook",
                            "tool": "search_handbook",
                            "expected_output": "spec",
                        }
                    ],
                    "notes": "",
                }
            elif role == "exec":
                if not saw_response:
                    return ModelResponse(
                        parts=[
                            ToolCallPart(
                                tool_name="search_handbook",
                                args={"query": "water"},
                                tool_call_id="c1",
                            )
                        ]
                    )
                payload = {
                    "findings": ["main tank 5,000 L"],
                    "draft": "The main tank holds 5,000 L.",
                    "self_confidence": 0.8,
                }
            else:
                payload = {"verdict": "pass", "issues": [], "suggestion": ""}
            return ModelResponse(parts=[TextPart(content=json.dumps(payload))])

        result = run_workflow("water?", model=FunctionModel(responder))
        assert result.tools_used == ["search_handbook"]
