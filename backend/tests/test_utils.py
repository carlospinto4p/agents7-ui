"""Tests for routers.utils schema helpers.

Dotted-path import resolution moved to the framework's
`agents7.agents.utils.import_from_path` (covered by the framework
suite); the local `import_class` duplicate was removed.
"""

from routers.utils import _load_output_schema

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
