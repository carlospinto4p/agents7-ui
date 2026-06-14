"""Tests for routers.utils import/schema helpers."""

import pytest

from routers.utils import _load_output_schema, import_class

# ── import_class ───────────────────────────────────────────────────────────


def test_import_class_resolves_valid_dotted_path():
    from pathlib import Path

    assert import_class("pathlib.Path") is Path


def test_import_class_missing_module_raises():
    with pytest.raises(ModuleNotFoundError):
        import_class("agents7_no_such_module.Thing")


def test_import_class_missing_attribute_raises():
    with pytest.raises(AttributeError):
        import_class("pathlib.NoSuchClass")


def test_import_class_malformed_path_raises():
    # No dot to split on -> unpacking the rsplit result fails.
    with pytest.raises(ValueError):
        import_class("nodotpath")


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
