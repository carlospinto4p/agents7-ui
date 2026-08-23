from pathlib import Path

from routers.catalog import (
    _demonstrates,
    _description,
    _first_sentences,
    _is_catalog_config,
)

# ── _is_catalog_config Tests ───────────────────────────────────────


def test_real_agent_config_is_kept():
    p = Path("/app/agents_catalog/tagger_agent/src/tagger_agent/config.yml")
    assert _is_catalog_config(p) is True


def test_example_config_is_kept():
    p = Path("/app/agents_catalog/examples/bio_generator/config.yml")
    assert _is_catalog_config(p) is True


def test_build_artifact_config_is_skipped():
    # The duplicate copy left by building a packaged catalog agent.
    p = Path(
        "/app/agents_catalog/tagger_agent/build/lib/tagger_agent/config.yml"
    )
    assert _is_catalog_config(p) is False


def test_venv_site_packages_config_is_skipped():
    p = Path(
        "/app/agents_catalog/tagger_agent/.venv/lib/python3.12/"
        "site-packages/tagger_agent/config.yml"
    )
    assert _is_catalog_config(p) is False


def test_egg_info_config_is_skipped():
    p = Path("/app/agents_catalog/tagger_agent/src/foo.egg-info/config.yml")
    assert _is_catalog_config(p) is False


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
