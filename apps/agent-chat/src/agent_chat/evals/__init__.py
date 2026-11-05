"""Evals: the case suite, deterministic graders, and run records.

The runner (``agent_chat.evals.runner``) is importable as a module without
pulling pydantic-evals report machinery into ``import agent_chat.evals``.
"""

from agent_chat.evals.cases import CASES, EvalCase
from agent_chat.evals.records import EvalRunRecord

__all__ = ["CASES", "EvalCase", "EvalRunRecord"]
