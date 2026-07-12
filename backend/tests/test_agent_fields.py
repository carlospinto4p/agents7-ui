from agents7.agents.detector import Detector
from agents7.agents.guarded import GuardedChatter
from agents7.agents.tool_agent import ToolAgent

from routers.agent_fields import build_fields

# ── build_fields Tests ─────────────────────────────────────────────


def _owner_of(fields: list[dict], name: str) -> str:
    return next(f for f in fields if f["name"] == name)["owner"]


def test_fields_are_attributed_to_the_introducing_class():
    fields = build_fields(Detector)
    # Core fields come from BaseAgent; the labeling fields from Labeler.
    assert _owner_of(fields, "name") == "BaseAgent"
    assert _owner_of(fields, "engine") == "BaseAgent"
    assert _owner_of(fields, "output_model") == "Labeler"
    assert _owner_of(fields, "examples") == "Labeler"


def test_detector_introduces_no_fields_of_its_own():
    # Detector specializes behaviour/type, not the field set.
    owners = {f["owner"] for f in build_fields(Detector)}
    assert owners == {"BaseAgent", "Labeler"}
    assert all(f["inherited"] for f in build_fields(Detector))


def test_own_fields_are_not_inherited():
    fields = build_fields(ToolAgent)
    tools = next(f for f in fields if f["name"] == "tools")
    assert tools["owner"] == "ToolAgent"
    assert tools["inherited"] is False
    # Inherited base fields are flagged inherited.
    name = next(f for f in fields if f["name"] == "name")
    assert name["inherited"] is True


def test_fields_are_ordered_base_first():
    # dataclass field order puts inherited base fields ahead of own ones.
    owners = [f["owner"] for f in build_fields(GuardedChatter)]
    assert owners[0] == "BaseAgent"
    assert owners[-1] == "GuardedChatter"
    # Once a subclass's fields start, base fields never reappear.
    first_own = owners.index("GuardedChatter")
    assert all(o == "GuardedChatter" for o in owners[first_own:])


def test_fields_carry_type_and_description():
    fields = build_fields(ToolAgent)
    tools = next(f for f in fields if f["name"] == "tools")
    assert tools["type"]  # non-empty (from docstring or annotation)
    assert "Tool" in tools["text"]


def test_most_specific_description_wins():
    # Chatter re-documents system_prompt with a personality-focused note;
    # its description must win over BaseAgent's generic one.
    from agents7.agents.chatter import Chatter

    sp = next(
        f for f in build_fields(Chatter) if f["name"] == "system_prompt"
    )
    assert "personality" in sp["text"].lower()
