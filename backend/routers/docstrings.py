"""Parse agent docstrings into structured sections for the UI.

The framework's docstrings mix two conventions: Google-style sections
(``Attributes:`` / ``Note:`` with indented ``name (type): text`` items)
and Sphinx field lists (``:param name: text``). This module normalises
both into a single shape the Classes page can render as tables and
prose instead of dumping raw text.
"""

import re

_GOOGLE_HEADER = re.compile(r"^([A-Z][A-Za-z ]+):\s*$")
_SPHINX_FIELD = re.compile(r"^:(\w+)(?:\s+([\w*]+))?:\s*(.*)$")
_ATTR_ITEM = re.compile(r"^([\w*]+)\s*(?:\(([^)]*)\))?:\s*(.*)$")

# Google section titles whose bodies are field lists, not prose.
_PARAM_HEADERS = {
    "attributes",
    "args",
    "arguments",
    "parameters",
    "keyword args",
    "keyword arguments",
}


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _finish_item(parts: list[str]) -> dict:
    """Turn accumulated lines of one field into a name/type/text item."""
    text = " ".join(p.strip() for p in parts).strip()
    m = _ATTR_ITEM.match(text)
    if m:
        return {
            "name": m.group(1),
            "type": m.group(2),
            "text": m.group(3).strip(),
        }
    return {"name": None, "type": None, "text": text}


def _parse_param_block(block: list[str]) -> list[dict]:
    """Parse a Google ``Attributes:``-style indented block into items.

    A new item begins at the block's base indent; lines indented
    deeper continue the previous item's description.
    """
    non_blank = [ln for ln in block if ln.strip()]
    if not non_blank:
        return []
    base = min(_indent(ln) for ln in non_blank)
    items: list[dict] = []
    cur: list[str] | None = None
    for line in block:
        if not line.strip():
            continue
        if _indent(line) <= base:
            if cur is not None:
                items.append(_finish_item(cur))
            cur = [line.strip()]
        elif cur is not None:
            cur.append(line.strip())
        else:
            cur = [line.strip()]
    if cur is not None:
        items.append(_finish_item(cur))
    return items


def _join_block_text(block: list[str]) -> str:
    """Join an indented prose block into paragraphs (blank-separated)."""
    paras: list[str] = []
    buf: list[str] = []
    for line in block:
        if line.strip():
            buf.append(line.strip())
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras)


def _parse_sphinx_fields(
    lines: list[str], i: int, n: int
) -> tuple[list[dict], int]:
    """Consume a contiguous run of ``:param:``-style fields from ``i``."""
    raw: list[dict] = []
    while i < n:
        line = lines[i]
        if not line.strip():
            break
        m = _SPHINX_FIELD.match(line)
        if m and _indent(line) == 0:
            raw.append(
                {
                    "kind": m.group(1),
                    "name": m.group(2),
                    "parts": [m.group(3)],
                }
            )
            i += 1
        elif _indent(line) > 0 and raw:
            raw[-1]["parts"].append(line.strip())
            i += 1
        else:
            break
    items = []
    for field in raw:
        name = field["name"] or field["kind"]
        text = " ".join(p.strip() for p in field["parts"]).strip()
        items.append({"name": name, "type": None, "text": text})
    return items, i


def parse_docstring(doc: str) -> dict:
    """Parse a docstring into summary, description, and sections.

    :param doc: A cleaned docstring (as from ``inspect.getdoc``).
    :return: ``{"summary", "description", "sections"}`` where each
        section is ``{"title", "kind": "params"|"text", ...}`` — a
        ``params`` section carries ``items`` (name/type/text), a
        ``text`` section carries ``text``.
    """
    lines = (doc or "").splitlines()
    summary = lines[0].strip() if lines else ""
    sections: list[dict] = []
    desc_paras: list[str] = []
    para: list[str] = []

    def close_para() -> None:
        if para:
            desc_paras.append(" ".join(para).strip())
            para.clear()

    i, n = 1, len(lines)
    while i < n:
        line = lines[i]

        header = _GOOGLE_HEADER.match(line)
        if header and _indent(line) == 0:
            close_para()
            title = header.group(1).strip()
            i += 1
            block: list[str] = []
            while i < n and (not lines[i].strip() or _indent(lines[i]) > 0):
                block.append(lines[i])
                i += 1
            if title.lower() in _PARAM_HEADERS:
                sections.append(
                    {
                        "title": title,
                        "kind": "params",
                        "items": _parse_param_block(block),
                    }
                )
            else:
                sections.append(
                    {
                        "title": title,
                        "kind": "text",
                        "text": _join_block_text(block),
                    }
                )
            continue

        if _SPHINX_FIELD.match(line) and _indent(line) == 0:
            close_para()
            items, i = _parse_sphinx_fields(lines, i, n)
            sections.append(
                {"title": "Parameters", "kind": "params", "items": items}
            )
            continue

        if line.strip():
            para.append(line.strip())
        else:
            close_para()
        i += 1

    close_para()
    return {
        "summary": summary,
        "description": "\n\n".join(p for p in desc_paras if p),
        "sections": sections,
    }
