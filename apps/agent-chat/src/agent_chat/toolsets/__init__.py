"""Named toolsets: groups of tools the agent assembles by name.

Adopters add a tool in ``tools/`` and register it in one of these groups —
the agent never lists tools one by one. ``core`` is always on; ``web`` is
only attached when the deployment enables network access; ``messaging``
carries the consequential tool behind the approval gate.
"""

from collections.abc import Callable

from pydantic_ai.toolsets import FunctionToolset

from agent_chat.deps import ChatDeps
from agent_chat.tools import as_toolset, calculator, clock, fetch_url, send_message


def core_toolset() -> FunctionToolset[ChatDeps]:
    """Always-on utilities: arithmetic and the clock."""
    return as_toolset([calculator, clock], toolset_id="core")


def web_toolset() -> FunctionToolset[ChatDeps]:
    """Network tools. Only attached when ``fetch_url_enabled`` is true."""
    return as_toolset([fetch_url], toolset_id="web")


def messaging_toolset() -> FunctionToolset[ChatDeps]:
    """Consequential tools that route through the approval gate."""
    return as_toolset([send_message], toolset_id="messaging")


#: The registry adopters extend: name -> builder. ``build_agent`` consumes this.
TOOLSETS: dict[str, Callable[[], FunctionToolset[ChatDeps]]] = {
    "core": core_toolset,
    "web": web_toolset,
    "messaging": messaging_toolset,
}
