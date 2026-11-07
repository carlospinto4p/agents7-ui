import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
import routers.catalog as catalog_mod
from routers.catalog import (
    _context_params,
    _demonstrates,
    _description,
    _discover_configs,
    _first_sentences,
    _guard_data,
    find_config_file,
)


def _write_config(path: Path, name: str) -> Path:
    """Create a minimal agent config at *path* and return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"name: {name}\nagent_type: chatter\n", encoding="utf-8")
    return path


@pytest.fixture
def installed(monkeypatch):
    """The entry points the backend's environment reports.

    Starts empty, so packages really installed in the test venv do not
    leak into the expected lists; a test appends to it.
    """
    eps: list[EntryPoint] = []
    monkeypatch.setattr(
        catalog_mod,
        "entry_points",
        lambda group: [e for e in eps if e.group == group],
    )
    return eps


@pytest.fixture
def catalog(tmp_path, monkeypatch, installed):
    """A throwaway catalog root the discovery walk points at."""
    root = tmp_path / "catalog"
    root.mkdir()
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", root)
    return root


def _install_agent(
    tmp_path: Path, monkeypatch, installed: list, name: str
) -> Path:
    """Make an importable agent package and register its entry point.

    The package is a real module on `sys.path` exposing `CONFIG_PATH`,
    so the entry point is loaded the way an installed one is.
    """
    site = tmp_path / "site-packages"
    config = _write_config(site / name / "config.yml", name)
    (site / name / "__init__.py").write_text(
        "from pathlib import Path\n"
        "CONFIG_PATH = Path(__file__).parent / 'config.yml'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(site))
    # Another test's copy of the module would otherwise be reused.
    monkeypatch.delitem(sys.modules, name, raising=False)
    installed.append(
        EntryPoint(name, f"{name}:CONFIG_PATH", catalog_mod.ENTRY_POINT_GROUP)
    )
    return config


# ── _discover_configs Tests ────────────────────────────────────────


def test_real_and_example_configs_are_found(catalog):
    _write_config(catalog / "my_tagger/src/my_tagger/config.yml", "mt")
    _write_config(catalog / "examples/bio_generator/config.yml", "bio")
    assert _discover_configs() == [
        catalog / "examples/bio_generator/config.yml",
        catalog / "my_tagger/src/my_tagger/config.yml",
    ]


def test_build_artifact_config_is_skipped(catalog):
    # The duplicate copy left by building a packaged catalog agent.
    _write_config(catalog / "my_tagger/src/my_tagger/config.yml", "mt")
    _write_config(catalog / "my_tagger/build/lib/my_tagger/config.yml", "mt")
    assert _discover_configs() == [
        catalog / "my_tagger/src/my_tagger/config.yml"
    ]


def test_venv_site_packages_config_is_skipped(catalog):
    _write_config(
        catalog / ".venv/lib/python3.12/site-packages/mt/config.yml", "mt"
    )
    assert _discover_configs() == []


def test_egg_info_config_is_skipped(catalog):
    _write_config(catalog / "src/foo.egg-info/config.yml", "foo")
    assert _discover_configs() == []


def test_missing_catalog_root_yields_no_configs(catalog):
    assert _discover_configs() == []


def test_agent_added_after_first_scan_is_found(catalog):
    _write_config(catalog / "examples/first/config.yml", "first")
    assert find_config_file("second") is None

    # The failure this replaces: a cached path list meant a folder
    # added while the backend ran stayed invisible until a restart.
    _write_config(catalog / "examples/second/config.yml", "second")
    assert (
        find_config_file("second") == catalog / "examples/second/config.yml"
    )


def test_find_config_file_matches_case_insensitively(catalog):
    _write_config(catalog / "examples/mt/config.yml", "My_Tagger")
    assert find_config_file("my_tagger") == catalog / "examples/mt/config.yml"


# ── Installed agent packages ───────────────────────────────────────


def test_installed_agent_is_listed_after_the_catalog_folder(
    catalog, tmp_path, monkeypatch, installed
):
    local = _write_config(catalog / "examples/local/config.yml", "local")
    pkg = _install_agent(tmp_path, monkeypatch, installed, "pkg_agent")
    assert _discover_configs() == [local, pkg]
    assert find_config_file("pkg_agent") == pkg


def test_installed_agent_is_listed_with_an_empty_catalog_folder(
    catalog, tmp_path, monkeypatch, installed
):
    pkg = _install_agent(tmp_path, monkeypatch, installed, "pkg_agent")
    assert catalog_mod.list_agents()[0]["name"] == "pkg_agent"
    assert _discover_configs() == [pkg]


def test_agent_in_both_places_is_listed_once(catalog, installed):
    # An agent installed editable from inside the catalog folder.
    config = _write_config(catalog / "mt/src/mt/config.yml", "mt")
    installed.append(_StubEntryPoint("mt", config))
    assert _discover_configs() == [config]


def test_broken_entry_point_is_skipped(
    catalog, tmp_path, monkeypatch, installed
):
    installed.append(
        EntryPoint(
            "gone", "no_such_agent:CONFIG_PATH", catalog_mod.ENTRY_POINT_GROUP
        )
    )
    pkg = _install_agent(tmp_path, monkeypatch, installed, "pkg_agent")
    assert _discover_configs() == [pkg]


def test_entry_point_naming_a_missing_file_is_skipped(catalog, installed):
    installed.append(_StubEntryPoint("ghost", Path("/nowhere/config.yml")))
    assert _discover_configs() == []


class _StubEntryPoint:
    """An entry point whose `load()` returns a fixed path."""

    group = catalog_mod.ENTRY_POINT_GROUP

    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self._path = path

    def load(self) -> Path:
        return self._path


# ── _description Tests ─────────────────────────────────────────────


def test_explicit_description_is_preferred():
    cfg = {
        "description": "  Does a thing.  ",
        "system_prompt": "You are an assistant.",
    }
    assert _description(cfg) == "Does a thing."


def test_description_falls_back_to_persona_backstory():
    cfg = {"persona": {"backstory": "Born in Madrid.\n  A journalist."}}
    assert _description(cfg) == "Born in Madrid. A journalist."


def test_description_falls_back_to_system_prompt():
    cfg = {"system_prompt": "Classify the\n   sentiment of text."}
    assert _description(cfg) == "Classify the sentiment of text."


def test_description_skips_auto_generated_prompt():
    cfg = {"system_prompt": "(auto-generated)"}
    assert _description(cfg) is None


def test_description_none_when_nothing_available():
    assert _description({"name": "Foo"}) is None


# ── _demonstrates Tests ─────────────────────────────────────────────


def test_demonstrates_class_and_feature():
    cfg = {"demonstrates": {"class": "  Labeler  ", "feature": "  prose  "}}
    assert _demonstrates(cfg) == {"class": "Labeler", "feature": "prose"}


def test_demonstrates_class_only():
    cfg = {"demonstrates": {"class": "Classifier"}}
    assert _demonstrates(cfg) == {"class": "Classifier"}


def test_demonstrates_none_when_absent():
    assert _demonstrates({"name": "Foo"}) is None


def test_demonstrates_none_when_not_a_mapping():
    assert _demonstrates({"demonstrates": "A Labeler writing prose."}) is None


def test_demonstrates_none_when_class_missing():
    assert _demonstrates({"demonstrates": {"feature": "prose"}}) is None


# ── _first_sentences Tests ─────────────────────────────────────────


def test_first_sentences_collapses_whitespace():
    assert _first_sentences("a\n\t b   c") == "a b c"


def test_first_sentences_truncates_on_word_boundary():
    text = "word " * 60  # 300 chars, exceeds the 220 limit
    out = _first_sentences(text)
    assert out.endswith("…")
    assert len(out) <= 221
    assert "wor…" not in out  # truncated on a space, not mid-word


# ── _guard_data Tests ──────────────────────────────────────────────


def test_guard_data_none_for_unguarded_agent():
    cfg = {"agent_type": "chatter", "engine": {"model": "qwen3:4b"}}
    assert _guard_data(cfg) is None


def test_guard_data_reads_its_own_engine():
    cfg = {
        "agent_type": "guarded_chatter",
        "engine": {"provider": "ollama", "model": "qwen3:4b"},
        "guard": {
            "engine": {"provider": "ollama", "model": "gemma4:e4b"},
            "think": True,
        },
    }
    guard = _guard_data(cfg)
    assert guard["model"] == "gemma4:e4b"
    assert guard["engine_inherited"] is False
    assert guard["think"] is True


def test_guard_data_inherits_the_agent_engine():
    cfg = {
        "agent_type": "guarded_scene_chatter",
        "engine": {"provider": "ollama", "model": "qwen3:4b"},
    }
    guard = _guard_data(cfg)
    assert guard["model"] == "qwen3:4b"
    assert guard["provider"] == "ollama"
    assert guard["engine_inherited"] is True


def test_guard_data_collects_top_level_settings():
    cfg = {
        "agent_type": "guarded_chatter",
        "engine": {"model": "qwen3:4b"},
        "max_guard_retries": 2,
        "guard_context_turns": 3,
        "temperature": 0.7,
    }
    guard = _guard_data(cfg)
    assert guard["settings"] == {
        "max_guard_retries": 2,
        "guard_context_turns": 3,
    }


def test_guard_data_found_via_settings_without_guarded_type():
    cfg = {"agent_type": "chatter", "engine": {}, "max_guard_retries": 1}
    assert _guard_data(cfg)["settings"] == {"max_guard_retries": 1}


def test_guard_data_carries_forbidden_terms_and_summary():
    cfg = {
        "agent_type": "guarded_chatter",
        "engine": {},
        "guard": {
            "forbidden_terms": ["as an AI"],
            "persona_summary": "A Spanish journalist.",
        },
    }
    guard = _guard_data(cfg)
    assert guard["forbidden_terms"] == ["as an AI"]
    assert guard["persona_summary"] == "A Spanish journalist."


def test_guard_data_tolerates_non_mapping_guard_block():
    cfg = {"agent_type": "guarded_chatter", "engine": {}, "guard": "yes"}
    guard = _guard_data(cfg)
    assert guard["engine_inherited"] is True
    assert guard["think"] is None


# ── _context_params Tests ──────────────────────────────────────────


def test_context_params_absent_gives_empty_list(tmp_path):
    assert _context_params({"name": "a"}, tmp_path / "config.yml") == []


def test_context_params_reports_declaration(tmp_path):
    cfg = {
        "context_params": {
            "nick": {"default": "ella", "description": "Her nick"},
        }
    }
    assert _context_params(cfg, tmp_path / "config.yml") == [
        {
            "name": "nick",
            "default": "ella",
            "description": "Her nick",
            "supplied_by_caller": True,
            "derived_from": "",
        }
    ]


def test_context_params_names_what_a_value_is_derived_from(tmp_path):
    """A derived value gets no field, and says what it reads."""
    cfg = {
        "context_params": {
            "nick": {"default": "ella"},
            "hint": {"callable": "html.escape", "from": "nick"},
        }
    }
    by_name = {
        p["name"]: p for p in _context_params(cfg, tmp_path / "config.yml")
    }
    assert by_name["hint"]["supplied_by_caller"] is False
    assert by_name["hint"]["derived_from"] == "nick"
    assert by_name["nick"]["derived_from"] == ""


def test_context_params_marks_resolver_backed_as_not_supplied(tmp_path):
    cfg = {
        "context_params": {
            "moment": {
                "callable": "agents7.agents.context.spanish_time_of_day"
            },
        }
    }
    param = _context_params(cfg, tmp_path / "config.yml")[0]
    assert param["supplied_by_caller"] is False


def test_context_params_scalar_entry_is_the_default(tmp_path):
    cfg = {"context_params": {"nick": "ella"}}
    param = _context_params(cfg, tmp_path / "config.yml")[0]
    assert param["default"] == "ella"


def test_context_params_malformed_section_is_ignored(tmp_path):
    """A bad declaration must not break the whole detail page."""
    cfg = {"context_params": {"nick": {"callable": "nope.missing"}}}
    assert _context_params(cfg, tmp_path / "config.yml") == []
