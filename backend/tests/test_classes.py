from routers.classes import list_classes

# ── list_classes Tests ─────────────────────────────────────────────


def _by_name() -> dict[str, dict]:
    return {c["name"]: c for c in list_classes()["classes"]}


def test_returns_the_full_agent_hierarchy():
    nodes = _by_name()
    # Every agent class introspected from BaseAgent must be present.
    expected = {
        "BaseAgent",
        "Labeler",
        "Detector",
        "Classifier",
        "Regressor",
        "ContextGuard",
        "Chatter",
        "GuardedChatter",
        "GuardedSceneChatter",
        "ToolAgent",
    }
    assert expected <= set(nodes)


def test_root_has_no_parent_and_is_abstract():
    root = _by_name()["BaseAgent"]
    assert root["parent"] is None
    assert root["abstract"] is True
    assert root["module"] == "base"


def test_parent_pointers_match_inheritance():
    nodes = _by_name()
    assert nodes["Labeler"]["parent"] == "BaseAgent"
    assert nodes["Detector"]["parent"] == "Labeler"
    assert nodes["Classifier"]["parent"] == "Detector"
    assert nodes["GuardedSceneChatter"]["parent"] == "GuardedChatter"


def test_concrete_classes_are_not_abstract():
    nodes = _by_name()
    assert nodes["Classifier"]["abstract"] is False
    assert nodes["Chatter"]["abstract"] is False


def test_every_node_carries_a_summary_and_doc():
    for node in list_classes()["classes"]:
        assert node["summary"], f"{node['name']} missing summary"
        assert node["doc"], f"{node['name']} missing doc"
        # Summary is the first line of the docstring.
        assert node["summary"] == node["doc"].splitlines()[0].strip()


def test_every_parent_is_itself_a_node():
    nodes = _by_name()
    for node in nodes.values():
        if node["parent"] is not None:
            assert node["parent"] in nodes


def test_description_and_fields_are_populated():
    nodes = _by_name()
    base = nodes["BaseAgent"]
    assert base["description"]
    # Attribute/parameter lists are exposed as owner-attributed fields.
    assert any(
        f["name"] == "engine" and f["owner"] == "BaseAgent"
        for f in base["fields"]
    )


def test_fields_carry_inheritance_attribution():
    nodes = _by_name()
    detector = {f["name"]: f for f in nodes["Detector"]["fields"]}
    assert detector["name"]["owner"] == "BaseAgent"
    assert detector["output_model"]["owner"] == "Labeler"
    assert detector["output_model"]["inherited"] is True


def test_note_sections_are_retained_but_params_are_not():
    nodes = _by_name()
    # Detector's docstring "Note" survives as a text section...
    titles = {s["title"] for s in nodes["Detector"]["sections"]}
    assert "Note" in titles
    # ...while attribute/parameter blocks are no longer sections.
    assert all(s["kind"] == "text" for s in nodes["Detector"]["sections"])
