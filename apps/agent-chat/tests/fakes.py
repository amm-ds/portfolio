"""The fake model API tests script their chats with.

``app_model()`` returns a model that pops the live module-level queue, so
tests enqueue steps right before making requests. Deterministic — no network,
no Ollama, no API keys.
"""

from collections import deque

from pydantic_ai.models.function import FunctionModel

from agent_chat.testing import FakeStep, scripted_model_from_queue

#: Tests append the steps they want played, in order.
queue: deque[FakeStep] = deque()


def app_model() -> FunctionModel:
    """A scripted model bound to the live ``queue``."""
    return scripted_model_from_queue(queue, model_name="scripted-api")
