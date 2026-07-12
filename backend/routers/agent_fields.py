"""Attribute each agent's dataclass fields to the class that defines it.

Agent classes are ``@dataclass(frozen=True)``, so their fields are the
authoritative source of "which attribute/parameter comes from where" —
more reliable than the docstrings, which freely re-list inherited
attributes. For each field this module finds the ancestor that
introduced it and pairs it with the most specific description available
across the inheritance chain's docstrings.
"""

import dataclasses
import inspect
import re

from routers.docstrings import parse_docstring


def _field_owner(cls: type, name: str) -> type | None:
    """Return the base-most dataclass in ``cls``'s MRO to declare ``name``.

    Walking derived → base and keeping the last match yields the class
    that *introduced* the field, i.e. where it was first defined.
    """
    owner: type | None = None
    for klass in cls.__mro__:
        if dataclasses.is_dataclass(klass) and name in getattr(
            klass, "__annotations__", {}
        ):
            owner = klass
    return owner


def _clean_type(tp: object) -> str:
    """Render a field annotation as a compact, module-free type string."""
    if isinstance(tp, type):
        return tp.__name__
    text = str(tp).replace("typing.", "")
    return re.sub(
        r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+",
        lambda m: m.group(0).rsplit(".", 1)[-1],
        text,
    )


def _documented_fields(cls: type) -> dict[str, dict]:
    """Map ``field name -> {type, text}`` from ``cls``'s own docstring."""
    parsed = parse_docstring(inspect.getdoc(cls) or "")
    out: dict[str, dict] = {}
    for section in parsed["sections"]:
        if section["kind"] != "params":
            continue
        for item in section["items"]:
            if item["name"] and item["name"] not in out:
                out[item["name"]] = {
                    "type": item["type"],
                    "text": item["text"],
                }
    return out


def build_fields(cls: type) -> list[dict]:
    """Return ``cls``'s dataclass fields, each attributed to its origin.

    :param cls: An agent class (or any dataclass).
    :return: One record per field in inheritance order (base fields
        first) with ``name``, ``type``, ``text`` (description),
        ``owner`` (the class that introduced it), and ``inherited``
        (whether ``owner`` differs from ``cls``). Descriptions and
        curated type strings come from the most specific docstring in
        the MRO that documents the field; the annotation is the type
        fallback.
    """
    if not dataclasses.is_dataclass(cls):
        return []

    doc_cache: dict[type, dict] = {}

    def docs_for(klass: type) -> dict:
        if klass not in doc_cache:
            doc_cache[klass] = _documented_fields(klass)
        return doc_cache[klass]

    fields: list[dict] = []
    for field in dataclasses.fields(cls):
        owner = _field_owner(cls, field.name)
        doc: dict | None = None
        for klass in cls.__mro__:  # derived -> base: most specific wins
            doc = docs_for(klass).get(field.name)
            if doc:
                break
        type_str = (
            doc["type"] if doc and doc["type"] else _clean_type(field.type)
        )
        fields.append(
            {
                "name": field.name,
                "type": type_str,
                "text": doc["text"] if doc else "",
                "owner": owner.__name__ if owner else None,
                "inherited": owner is not None and owner is not cls,
            }
        )
    return fields
