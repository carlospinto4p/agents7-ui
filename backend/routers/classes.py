import inspect

import agents7.agents  # noqa: F401  (import registers all agent subclasses)
from agents7.agents.base import BaseAgent
from fastapi import APIRouter

from routers.docstrings import parse_docstring

router = APIRouter(prefix="/api/classes", tags=["classes"])


def _describe(cls: type, parent: str | None) -> dict:
    """Build a node record for one agent class.

    :param cls: The agent class to describe.
    :param parent: Name of the immediate base agent class, or ``None``
        for the root.
    :return: A dict with the class name, parent, defining module, an
        abstract flag, and its docstring parsed into a one-line
        summary, description prose, and structured sections (plus the
        raw ``doc`` as a fallback).
    """
    doc = inspect.getdoc(cls) or ""
    parsed = parse_docstring(doc)
    return {
        "name": cls.__name__,
        "parent": parent,
        "module": cls.__module__.rsplit(".", 1)[-1],
        "abstract": inspect.isabstract(cls),
        "summary": parsed["summary"],
        "description": parsed["description"],
        "sections": parsed["sections"],
        "doc": doc,
    }


def _walk(cls: type, parent: str | None, out: list[dict]) -> None:
    """Recursively collect ``cls`` and its subclasses into ``out``."""
    out.append(_describe(cls, parent))
    for sub in cls.__subclasses__():
        _walk(sub, cls.__name__, out)


@router.get("")
def list_classes() -> dict:
    """Return the agent class hierarchy via runtime introspection.

    Walks ``BaseAgent.__subclasses__()`` recursively so newly added
    agent classes appear automatically — there is no hardcoded list to
    keep in sync. Each node carries its parent name (``None`` for the
    root), defining module, abstract flag, one-line summary, and full
    docstring.

    :return: ``{"classes": [<node>, ...]}`` in pre-order (root first).
    """
    nodes: list[dict] = []
    _walk(BaseAgent, None, nodes)
    return {"classes": nodes}
