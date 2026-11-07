"""Tests for the reads endpoint.

The page it serves renders a read and writes feedback back to the
same `feedback.yml` the framework's `chat-feedback` command reads.
These lock in three things: the payload comes from the framework
rather than being rebuilt, a folder with no `read.yml` still serves
its recordings, and saving merges rather than replacing.
"""

import json

import pytest
import routers.reads as reads_mod
from agents7.eval.chat_feedback import load_feedback
from agents7.eval.chat_review import (
    Recording,
    TurnRecord,
    save_recording,
)
from fastapi import HTTPException
from routers.reads import (
    FeedbackIn,
    list_reads,
    read_detail,
    read_report,
    save_read_feedback,
)


def metrics() -> dict:
    return {
        "tokens": 10,
        "prompt_tokens": 100,
        "cached_prompt_tokens": 90,
        "total_duration": 1.0,
        "cost_cents": 0.01,
        "cached": False,
        "model": "openai_compat::demo-1",
        "retries": 0,
        "retry_duration": 0.0,
    }


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    """A catalog with one agent holding one read of two conversations."""
    folder = tmp_path / "demo_agent" / "docs" / "reads" / "2026-09-20"
    folder.mkdir(parents=True)
    for name, opener in (("warm", "buenas"), ("cold", "hola")):
        save_recording(
            Recording(
                conversation_id=name,
                agent="demo",
                agent_version="1.2.3",
                recorded="2026-09-20T10:00:00+00:00",
                context={"nick": "Marta_87"},
                facts=("Le gusta llegar el último.",),
                turns=(
                    TurnRecord(0, None, opener, metrics()),
                    TurnRecord(1, "ya", "vale", metrics()),
                ),
            ),
            folder / f"{name}.json",
        )
    monkeypatch.setattr(reads_mod, "CATALOG_PATH", tmp_path)
    return tmp_path, folder


@pytest.fixture
def read_path() -> str:
    return "demo_agent/docs/reads/2026-09-20"


# ── Discovery ──────────────────────────────────────────────────────


def test_a_read_folder_is_discovered(catalog, read_path):
    reads = list_reads()["reads"]
    assert len(reads) == 1
    assert reads[0]["path"] == read_path
    assert reads[0]["agent"] == "demo"
    assert reads[0]["conversations"] == 2


def test_a_folder_with_no_recordings_is_not_a_read(catalog):
    _, folder = catalog
    (folder.parent / "empty").mkdir()
    assert len(list_reads()["reads"]) == 1


def test_discovery_reports_whether_a_spec_exists(catalog, read_path):
    _, folder = catalog
    assert list_reads()["reads"][0]["has_read_spec"] is False
    (folder / "read.yml").write_text(
        "title: A read\nconversations:\n  - recording: warm.json\n",
        encoding="utf-8",
    )
    assert list_reads()["reads"][0]["has_read_spec"] is True


# ── Path safety ────────────────────────────────────────────────────


def test_a_path_escaping_the_catalog_is_refused(catalog):
    with pytest.raises(HTTPException) as exc:
        read_detail("../../etc")
    assert exc.value.status_code == 400


def test_an_absolute_path_is_refused(catalog):
    with pytest.raises(HTTPException) as exc:
        read_detail("/etc")
    assert exc.value.status_code == 400


def test_a_missing_read_is_a_404(catalog):
    with pytest.raises(HTTPException) as exc:
        read_detail("demo_agent/docs/reads/nope")
    assert exc.value.status_code == 404


# ── Detail ─────────────────────────────────────────────────────────


def test_recordings_are_served_without_a_spec(catalog, read_path):
    """The expensive half stands on its own."""
    payload = read_detail(read_path)
    assert payload["has_read_spec"] is False
    assert [c["id"] for c in payload["conversations"]] == ["cold", "warm"]


def test_the_payload_carries_the_conversation_context(catalog, read_path):
    payload = read_detail(read_path)
    labels = {
        row["label"]: row["value"]
        for row in payload["conversations"][0]["context"]
    }
    assert labels["nick"] == "Marta_87"
    assert "20 September 2026" in labels["When"]


def test_a_spec_supplies_the_verdicts(catalog, read_path):
    _, folder = catalog
    (folder / "read.yml").write_text(
        "title: A read\n"
        "verdicts:\n"
        "  - claim: He stays\n"
        "    stamp: pass\n"
        "    detail: He did.\n"
        "conversations:\n"
        "  - recording: warm.json\n",
        encoding="utf-8",
    )
    payload = read_detail(read_path)
    assert payload["title"] == "A read"
    assert payload["verdicts"][0]["claim"] == "He stays"


def test_the_payload_carries_the_labels_a_renderer_needs(catalog, read_path):
    payload = read_detail(read_path)
    assert set(payload["verdict_kinds"]) == {"right", "weak", "wrong"}
    assert "worked" in payload["note_kinds"]


def test_feedback_starts_empty(catalog, read_path):
    payload = read_detail(read_path)
    assert payload["feedback"]["entries"] == []
    assert payload["feedback"]["read_id"] == "2026-09-20"


# ── Saving feedback ────────────────────────────────────────────────


def _entry(**over) -> dict:
    base = {
        "conversation": "warm",
        "turn": 1,
        "verdict": "wrong",
        "he_said": "vale",
        "should_say": "vale, lo que tú digas",
        "why": "too flat",
        "rule": "no bare acknowledgements",
        "lands_in": "david.yml",
    }
    base.update(over)
    return base


def test_saving_writes_the_feedback_file(catalog, read_path):
    _, folder = catalog
    save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    saved = load_feedback(folder / "feedback.yml")
    assert len(saved.entries) == 1
    assert saved.entries[0].rule == "no bare acknowledgements"


def test_saving_merges_and_keeps_untouched_turns(catalog, read_path):
    save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    save_read_feedback(
        read_path,
        FeedbackIn(entries=[_entry(turn=0, rule="a second rule")]),
    )
    _, folder = catalog
    saved = load_feedback(folder / "feedback.yml")
    assert len(saved.entries) == 2


def test_saving_replaces_every_entry_on_a_touched_turn(catalog, read_path):
    save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    save_read_feedback(
        read_path, FeedbackIn(entries=[_entry(rule="replaced")])
    )
    _, folder = catalog
    saved = load_feedback(folder / "feedback.yml")
    assert len(saved.entries) == 1
    assert saved.entries[0].rule == "replaced"


def test_saving_returns_the_derived_outputs(catalog, read_path):
    body = save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    assert body["eval_rows"] == 1
    assert body["rule_changes"][0]["lands_in"] == "david.yml"
    assert body["rule_changes"][0]["outstanding"] == 1
    assert "no bare acknowledgements" in body["report"]


def test_clearing_a_turn_removes_its_last_entry(catalog, read_path):
    """Merging alone cannot: an empty list names no turn."""
    save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    body = save_read_feedback(
        read_path,
        FeedbackIn(
            entries=[],
            clear=[{"conversation": "warm", "turn": 1}],
        ),
    )
    assert body["feedback"]["entries"] == []


def test_clearing_keeps_the_survivors_it_is_sent(catalog, read_path):
    save_read_feedback(
        read_path,
        FeedbackIn(entries=[_entry(), _entry(rule="second")]),
    )
    body = save_read_feedback(
        read_path,
        FeedbackIn(
            entries=[_entry(rule="second")],
            clear=[{"conversation": "warm", "turn": 1}],
        ),
    )
    rules = [e["rule"] for e in body["feedback"]["entries"]]
    assert rules == ["second"]


def test_clearing_leaves_other_turns_alone(catalog, read_path):
    save_read_feedback(
        read_path,
        FeedbackIn(entries=[_entry(), _entry(turn=0, rule="other")]),
    )
    body = save_read_feedback(
        read_path,
        FeedbackIn(
            entries=[],
            clear=[{"conversation": "warm", "turn": 1}],
        ),
    )
    assert [e["turn"] for e in body["feedback"]["entries"]] == [0]


def test_golden_is_only_changed_when_sent(catalog, read_path):
    save_read_feedback(
        read_path, FeedbackIn(entries=[_entry()], golden=["warm"])
    )
    body = save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    assert body["feedback"]["golden"] == ["warm"]


def test_an_entry_saying_nothing_is_refused(catalog, read_path):
    with pytest.raises(HTTPException) as exc:
        save_read_feedback(
            read_path,
            FeedbackIn(entries=[_entry(should_say="", why="", rule="")]),
        )
    assert exc.value.status_code == 400


def test_saved_feedback_comes_back_with_the_read(catalog, read_path):
    save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    payload = read_detail(read_path)
    assert len(payload["feedback"]["entries"]) == 1


# ── Report ─────────────────────────────────────────────────────────


def test_the_report_reads_without_writing(catalog, read_path):
    save_read_feedback(read_path, FeedbackIn(entries=[_entry()]))
    body = read_report(read_path)
    assert "no bare acknowledgements" in body["report"]
    assert body["eval_rows"] == 1


def test_a_read_with_no_feedback_still_reports(catalog, read_path):
    body = read_report(read_path)
    assert "No rule changes." in body["report"]


def test_a_broken_feedback_file_explains_itself(catalog, read_path):
    _, folder = catalog
    (folder / "feedback.yml").write_text(
        json.dumps({"entries": []}), encoding="utf-8"
    )
    with pytest.raises(HTTPException) as exc:
        read_report(read_path)
    assert exc.value.status_code == 400
