from pathlib import Path

from routers.catalog import _is_catalog_config

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
