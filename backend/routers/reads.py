"""Read a chat agent's recorded conversations, and feed back on them.

The page this serves does two jobs. It renders a read the way the
generated page does -- which is why the payload comes from
`agents7.eval.chat_review.read_payload` rather than being rebuilt
here -- and it lets the operator attach a correction to a turn,
which is the job no static page can do.

Feedback is written back to the same `feedback.yml` the framework's
`chat-feedback` command reads, beside the recordings. The page is an
editor for that file, never a second store: a read half in a
database and half in git would be worse than the text editor it
replaces.
"""

import logging
import os
from pathlib import Path

from agents7.eval.chat_feedback import (
    VERDICTS,
    Feedback,
    FeedbackEntry,
    load_feedback,
    merge_entries,
    render_feedback,
    save_feedback,
)
from agents7.eval.chat_review import load_recording, read_payload
from agents7.exceptions import Agents7Exception
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/reads", tags=["reads"])
logger = logging.getLogger(__name__)

# Same default as `routers.catalog`: the repository's `catalog/` folder.
_default = str(Path(__file__).parents[2] / "catalog")
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", _default))

#: Where a read folder lives relative to an agent package. Reads are
#: authored by hand, so this is a convention rather than a schema --
#: a folder is a read when it holds at least one recording.
_READS_DIR = ("docs", "reads")

_SKIP_DIRS = {
    "build",
    "dist",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "site-packages",
}


def _resolve(rel: str) -> Path:
    """Resolve a caller-supplied read path inside the catalog.

    The path arrives from the browser, so it is untrusted. Mirrors
    `routers.utils._resolve_agent_path`: relative only, resolved,
    and required to stay under the catalog root.

    :param rel: Path relative to the catalog root.
    :return: The resolved directory.
    :raises HTTPException: If it escapes, or is not a read folder.
    """
    candidate = Path(rel)
    if candidate.is_absolute():
        raise HTTPException(400, "Read path must be relative.")
    resolved = (CATALOG_PATH / candidate).resolve()
    try:
        resolved.relative_to(CATALOG_PATH.resolve())
    except ValueError:
        raise HTTPException(400, "Read path escapes the catalog.") from None
    if not resolved.is_dir():
        raise HTTPException(404, f"No read at {rel}.")
    return resolved


def _recordings(folder: Path) -> list[Path]:
    """The recording files in a read folder, in name order.

    A read folder also holds `read.yml` and `feedback.yml`, and may
    hold a generated `read.html`; only the JSON is a recording.

    :param folder: The read directory.
    :return: Recording paths.
    """
    return sorted(p for p in folder.glob("*.json") if p.is_file())


def _discover() -> list[Path]:
    """Every read folder under the catalog.

    Walked on each call rather than cached, for the same reason the
    catalog router walks: a read recorded five minutes ago should
    not need a backend restart to appear.

    :return: Sorted read folders.
    """
    found: list[Path] = []
    for dirpath, dirnames, _ in os.walk(CATALOG_PATH):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _SKIP_DIRS and not d.endswith(".egg-info")
        ]
        here = Path(dirpath)
        if here.parts[-2:] != _READS_DIR:
            continue
        for child in sorted(here.iterdir()):
            if child.is_dir() and _recordings(child):
                found.append(child)
    return found


def _feedback_path(folder: Path) -> Path:
    return folder / "feedback.yml"


def _read_spec(folder: Path) -> Path:
    return folder / "read.yml"


def _blank_feedback(folder: Path, agent: str, version: str) -> Feedback:
    """The feedback a folder starts with before anyone writes any.

    :param folder: The read directory, whose name is the read id.
    :param agent: The agent's name, from a recording.
    :param version: The version it ran at.
    :return: An empty `Feedback` for this read.
    """
    return Feedback(
        read_id=folder.name,
        agent=agent,
        agent_version=version,
    )


def _load_or_blank(folder: Path, agent: str, version: str) -> Feedback:
    path = _feedback_path(folder)
    if not path.exists():
        return _blank_feedback(folder, agent, version)
    try:
        return load_feedback(path)
    except Agents7Exception as exc:
        raise HTTPException(400, f"{path.name}: {exc}") from exc


class EntryIn(BaseModel):
    """One feedback entry as the page sends it."""

    conversation: str
    verdict: str
    turn: int | None = None
    he_said: str = ""
    should_say: str = ""
    why: str = ""
    rule: str = ""
    lands_in: str = ""
    shipped: str = ""


class TurnRef(BaseModel):
    """One turn to empty before merging."""

    conversation: str
    turn: int | None = None


class FeedbackIn(BaseModel):
    """What the page sends when the operator saves.

    Entries are merged rather than replacing the file: every entry
    on a turn the operator touched is replaced, and turns nobody
    touched keep whatever is there, including anything hand-written
    outside the UI.

    `clear` is what makes deleting the *last* entry on a turn
    possible. Merging keys on the turns the incoming entries name,
    so an empty list names no turn and would leave the entry
    standing. Naming the turn here empties it first.
    """

    entries: list[EntryIn] = Field(default_factory=list)
    clear: list[TurnRef] = Field(default_factory=list)
    golden: list[str] | None = None


@router.get("")
def list_reads() -> dict:
    """Every read folder in the catalog, newest name first.

    :return: `{"reads": [...]}`, each with enough to choose one.
    """
    root = CATALOG_PATH.resolve()
    reads = []
    for folder in _discover():
        recordings = _recordings(folder)
        agent, version = "unknown", "unknown"
        try:
            first = load_recording(recordings[0])
            agent, version = first.agent, first.agent_version
        except Agents7Exception:
            logger.warning("Unreadable recording in %s", folder)
        reads.append(
            {
                "path": str(folder.resolve().relative_to(root)),
                "id": folder.name,
                "agent": agent,
                "agent_version": version,
                "conversations": len(recordings),
                "has_read_spec": _read_spec(folder).exists(),
                "has_feedback": _feedback_path(folder).exists(),
            }
        )
    reads.sort(key=lambda r: (r["agent"], r["id"]), reverse=True)
    return {"reads": reads}


@router.get("/detail")
def read_detail(path: str) -> dict:
    """One read: its conversations, its judgement, and its feedback.

    A folder with no `read.yml` is still served. Recordings are the
    expensive half and they stand on their own -- refusing to show
    them until somebody writes a spec would make the page useless
    for exactly the case it is best at, which is a conversation
    recorded minutes ago.

    :param path: The read folder, relative to the catalog root.
    :return: The payload the page renders.
    """
    folder = _resolve(path)
    recordings = _recordings(folder)
    if not recordings:
        raise HTTPException(404, f"No recordings in {path}.")

    spec = _read_spec(folder)
    try:
        if spec.exists():
            payload = read_payload(spec)
        else:
            payload = _payload_without_spec(folder, recordings)
    except Agents7Exception as exc:
        raise HTTPException(400, f"{folder.name}: {exc}") from exc

    first = payload["conversations"][0]
    feedback = _load_or_blank(
        folder,
        payload.get("agent") or first.get("agent") or "unknown",
        first.get("agent_version") or "unknown",
    )
    payload["path"] = path
    payload["has_read_spec"] = spec.exists()
    payload["verdict_kinds"] = dict(VERDICTS)
    payload["feedback"] = feedback.to_dict()
    return payload


def _payload_without_spec(folder: Path, recordings: list[Path]) -> dict:
    """Build a read payload from recordings alone.

    :param folder: The read directory.
    :param recordings: Its recording files.
    :return: The same shape `read_payload` returns, with the parts
        that only a spec can supply left empty.
    """
    from agents7.eval.chat_review import (
        Read,
        ReviewedConversation,
    )

    conversations = tuple(
        ReviewedConversation(
            recording=load_recording(path),
            title=path.stem,
        )
        for path in recordings
    )
    return read_payload(
        Read(
            title=folder.name,
            eyebrow="",
            standfirst="",
            caveat="",
            conversations=conversations,
            read_id=folder.name,
        )
    )


@router.post("/feedback")
def save_read_feedback(path: str, body: FeedbackIn) -> dict:
    """Merge entries into a read's feedback file and write it.

    :param path: The read folder, relative to the catalog root.
    :param body: The entries the operator just wrote.
    :return: The feedback as saved, and the rendered report.
    """
    folder = _resolve(path)
    recordings = _recordings(folder)
    if not recordings:
        raise HTTPException(404, f"No recordings in {path}.")
    first = load_recording(recordings[0])
    existing = _load_or_blank(folder, first.agent, first.agent_version)

    try:
        entries = [
            FeedbackEntry(**entry.model_dump()) for entry in body.entries
        ]
    except Agents7Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    if body.clear:
        emptied = {(ref.conversation, ref.turn) for ref in body.clear}
        existing = Feedback(
            read_id=existing.read_id,
            agent=existing.agent,
            agent_version=existing.agent_version,
            reviewed=existing.reviewed,
            golden=existing.golden,
            entries=tuple(
                e
                for e in existing.entries
                if (e.conversation, e.turn) not in emptied
            ),
        )

    merged = merge_entries(existing, entries)
    if body.golden is not None:
        merged = Feedback(
            read_id=merged.read_id,
            agent=merged.agent,
            agent_version=merged.agent_version,
            reviewed=merged.reviewed,
            golden=tuple(body.golden),
            entries=merged.entries,
        )
    save_feedback(merged, _feedback_path(folder))
    return {
        "feedback": merged.to_dict(),
        "report": render_feedback(merged),
        "rule_changes": [
            {
                "lands_in": change.lands_in,
                "rules": list(change.rules),
                "outstanding": len(change.outstanding),
            }
            for change in merged.rule_changes()
        ],
        "eval_rows": len(merged.eval_rows()),
    }


@router.get("/report")
def read_report(path: str) -> dict:
    """The feedback report for a read, without writing anything.

    :param path: The read folder, relative to the catalog root.
    :return: The Markdown report and the derived counts.
    """
    folder = _resolve(path)
    recordings = _recordings(folder)
    if not recordings:
        raise HTTPException(404, f"No recordings in {path}.")
    first = load_recording(recordings[0])
    feedback = _load_or_blank(folder, first.agent, first.agent_version)
    return {
        "report": render_feedback(feedback),
        "rule_changes": [
            {
                "lands_in": change.lands_in,
                "rules": list(change.rules),
                "outstanding": len(change.outstanding),
            }
            for change in feedback.rule_changes()
        ],
        "eval_rows": len(feedback.eval_rows()),
    }
