"""Tests for routers.utils schema helpers.

Dotted-path import resolution moved to the framework's
`agents7.agents.utils.import_from_path` (covered by the framework
suite); the local `import_class` duplicate was removed.
"""

import pytest
from fastapi import HTTPException

from routers.utils import _load_output_schema, reject_tool_agent

# ── _load_output_schema ────────────────────────────────────────────────────


def test_load_output_schema_absent_returns_empty():
    assert _load_output_schema({}) == (None, set())


def test_load_output_schema_empty_path_returns_empty():
    assert _load_output_schema({"output_model": ""}) == (None, set())


def test_load_output_schema_missing_module_suppressed():
    result = _load_output_schema(
        {"output_model": "agents7_no_such_module.Model"}
    )
    assert result == (None, set())


def test_load_output_schema_missing_attribute_suppressed():
    result = _load_output_schema({"output_model": "agents7.models.NoSuch"})
    assert result == (None, set())


def test_load_output_schema_valid_model_returns_schema():
    schema, fields = _load_output_schema(
        {"output_model": "agents7.models.ChatResponse"}
    )
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert fields == set(schema["properties"].keys())


# ── reject_tool_agent ──────────────────────────────────────────────────────


def test_reject_tool_agent_rejects_tool():
    """A tool agent is refused, not served an empty output."""
    with pytest.raises(HTTPException) as exc:
        reject_tool_agent("tool")
    assert exc.value.status_code == 422
    assert "trajectory" in exc.value.detail


def test_reject_tool_agent_allows_structured_types():
    """Every structured-output type passes through untouched."""
    for agent_type in ("labeler", "detector", "classifier", "regressor"):
        assert reject_tool_agent(agent_type) is None
