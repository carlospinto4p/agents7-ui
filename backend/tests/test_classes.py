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


def test_docstrings_are_parsed_into_sections():
    nodes = _by_name()
    # BaseAgent documents its fields under a Google "Attributes" block.
    base = nodes["BaseAgent"]
    assert base["description"]
    attrs = next(s for s in base["sections"] if s["title"] == "Attributes")
    assert attrs["kind"] == "params"
    assert any(i["name"] == "engine" for i in attrs["items"])

    # ToolAgent documents its constructor with Sphinx :param: fields.
    tool = nodes["ToolAgent"]
    params = next(s for s in tool["sections"] if s["title"] == "Parameters")
    assert {i["name"] for i in params["items"]} >= {"tools", "max_iterations"}
