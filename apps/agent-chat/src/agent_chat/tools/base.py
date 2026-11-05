"""Tool contract and registry helpers.

A tool is a plain typed function whose docstring pydantic-ai turns into the
model-facing schema (the same convention project 09 proves in-repo). The
:class:`Tool` protocol states that contract; :func:`as_toolset` validates a
group of tools before handing them to the agent, so a tool that slips in
without a docstring or typed signature fails at import time, not mid-run.
"""

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic_ai.toolsets import FunctionToolset

F = TypeVar("F", bound=Callable[..., Any])


@runtime_checkable
class Tool(Protocol):
    """What every tool function must provide.

    ``__name__`` becomes the model-facing tool name; the docstring's prose and
    ``Args:``/``Returns:`` sections become the description and schema; the
    signature's typed parameters become the tool's arguments.
    """

    __name__: str
    __doc__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def validate_tool(fn: Callable[..., Any]) -> None:
    """Fail fast when ``fn`` cannot serve as a pydantic-ai tool."""
    doc = getattr(fn, "__doc__", None)
    if not doc or not doc.strip():
        raise ValueError(f"tool {fn.__name__!r} needs a docstring (it is the model-facing schema)")
    if fn.__name__.startswith("_"):
        raise ValueError(f"tool {fn.__name__!r} must not be private (it becomes the tool name)")


def as_toolset(tools: list[Callable[..., Any]], *, toolset_id: str) -> FunctionToolset[Any]:
    """Validate ``tools`` and wrap them as a named ``FunctionToolset``."""
    for fn in tools:
        validate_tool(fn)
    return FunctionToolset(tools, id=toolset_id)
