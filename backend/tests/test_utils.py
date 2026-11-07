"""Tests for routers.utils schema helpers.

Dotted-path import resolution moved to the framework's
`agents7.agents.utils.import_from_path` (covered by the framework
suite); the local `import_class` duplicate was removed.
"""

from routers.utils import _load_output_schema, agent_unavailable

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


# ── agent_unavailable ──────────────────────────────────────────────────────


def test_agent_unavailable_names_the_missing_module():
    exc = agent_unavailable(
        ModuleNotFoundError("No module named 'my_tagger'", name="my_tagger")
    )
    assert exc.status_code == 422
    assert "`my_tagger`" in exc.detail
    assert "not installed" in exc.detail


def test_agent_unavailable_without_a_module_name_still_reads():
    """A bare ImportError carries no `name`; the message must hold."""
    exc = agent_unavailable(ImportError("circular import"))
    assert exc.status_code == 422
    assert "a module it declares" in exc.detail
