from routers.docstrings import parse_docstring

# ── Google-style docstrings ────────────────────────────────────────

GOOGLE = """Base class for all agents.
This class should be inherited by all agent classes.

Attributes:
    name (str): The name of the agent.
    prompt_params (dict, optional): Dictionary of parameters to
        substitute into the system_prompt using
        $variable placeholders.

Note:
    A trailing note that spans
    two source lines.
"""


def test_summary_is_first_line():
    parsed = parse_docstring(GOOGLE)
    assert parsed["summary"] == "Base class for all agents."


def test_description_excludes_summary_and_sections():
    parsed = parse_docstring(GOOGLE)
    assert parsed["description"] == (
        "This class should be inherited by all agent classes."
    )


def test_google_attributes_become_a_params_section():
    parsed = parse_docstring(GOOGLE)
    attrs = next(s for s in parsed["sections"] if s["title"] == "Attributes")
    assert attrs["kind"] == "params"
    assert attrs["items"][0] == {
        "name": "name",
        "type": "str",
        "text": "The name of the agent.",
    }


def test_multiline_field_description_is_joined():
    parsed = parse_docstring(GOOGLE)
    attrs = next(s for s in parsed["sections"] if s["title"] == "Attributes")
    pp = next(i for i in attrs["items"] if i["name"] == "prompt_params")
    assert pp["type"] == "dict, optional"
    assert "substitute into the system_prompt using" in pp["text"]
    assert "$variable placeholders." in pp["text"]


def test_google_note_becomes_a_text_section():
    parsed = parse_docstring(GOOGLE)
    note = next(s for s in parsed["sections"] if s["title"] == "Note")
    assert note["kind"] == "text"
    assert note["text"] == "A trailing note that spans two source lines."


# ── Sphinx-style docstrings ────────────────────────────────────────

SPHINX = """An agent that can call Python functions.

Runs a bounded loop until a final answer.

:param tools: Callables the agent may call.
:param max_iterations: Maximum model turns before raising
    an error. Defaults to 10.
"""


def test_sphinx_params_become_a_parameters_section():
    parsed = parse_docstring(SPHINX)
    assert parsed["summary"] == "An agent that can call Python functions."
    assert (
        parsed["description"] == "Runs a bounded loop until a final answer."
    )
    params = next(s for s in parsed["sections"] if s["title"] == "Parameters")
    assert params["kind"] == "params"
    names = [i["name"] for i in params["items"]]
    assert names == ["tools", "max_iterations"]


def test_sphinx_param_continuation_is_joined():
    parsed = parse_docstring(SPHINX)
    params = next(s for s in parsed["sections"] if s["title"] == "Parameters")
    mi = next(i for i in params["items"] if i["name"] == "max_iterations")
    assert mi["type"] is None
    assert (
        mi["text"]
        == "Maximum model turns before raising an error. Defaults to 10."
    )


# ── Edge cases ─────────────────────────────────────────────────────


def test_empty_docstring_is_safe():
    parsed = parse_docstring("")
    assert parsed == {"summary": "", "description": "", "sections": []}


def test_summary_only_docstring():
    parsed = parse_docstring("Just a one-liner.")
    assert parsed["summary"] == "Just a one-liner."
    assert parsed["description"] == ""
    assert parsed["sections"] == []
