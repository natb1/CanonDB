"""card — the check on a write of the page's ``ordo/current`` before it is sent.

The page draws what the document holds and says nothing of a field it
cannot draw: a reading of tradition given as a plain string draws an empty
line, a prediction that is not an object draws "No prediction was sealed",
and a question that carries a recommendation breaks the rule that a question
is put alone. This module reads the object about to be written, whole or a
partial ``update`` holding any of its fields, and returns one finding per
fault. An empty list is a write the page can draw.

A field may be removed by the deletion marker ``{"__delete__": true}``,
which is taken wherever a field may stand.

Nothing here reaches the network or writes the page.
"""

from __future__ import annotations

from typing import List

#: the parts of a prediction the page draws
PREDICTION = ("predicted", "diverged", "addressed")


def deleted(value) -> bool:
    """The deletion marker, which removes the field it stands for."""
    return isinstance(value, dict) and value.get("__delete__") is True and len(value) == 1


def _texts(value) -> bool:
    """A string or a list of strings."""
    return isinstance(value, str) or (isinstance(value, list)
                                      and all(isinstance(x, str) for x in value))


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _filled(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _readings(context: dict, side: str) -> List[str]:
    value = context[side]
    if deleted(value):
        return []
    if not isinstance(value, list):
        return ["context.%s is not a list of objects {who, text}" % side]
    out = []
    for n, item in enumerate(value):
        where = "context.%s[%d]" % (side, n)
        if not isinstance(item, dict):
            out.append("%s is not an object {who, text}; the page draws it as an empty line"
                       % where)
            continue
        for key in ("who", "text"):
            if not _filled(item.get(key)):
                out.append("%s has no %s, a non-empty string" % (where, key))
    return out


def _prediction(value) -> List[str]:
    if deleted(value):
        return []
    if not isinstance(value, dict):
        return ["context.prediction is not an object of %s" % ", ".join(PREDICTION)]
    out = []
    for key in sorted(value):
        if key not in PREDICTION:
            out.append("context.prediction holds %r, which the page does not draw; its keys "
                       "are %s" % (key, ", ".join(PREDICTION)))
        elif not deleted(value[key]) and not _texts(value[key]):
            out.append("context.prediction.%s is not a string or a list of strings" % key)
    return out


def _log(value) -> List[str]:
    if deleted(value):
        return []
    if not isinstance(value, list):
        return ["context.log is not a list of records {at, paragraphs}"]
    out = []
    for n, record in enumerate(value):
        where = "context.log[%d]" % n
        if not isinstance(record, dict):
            out.append("%s is not an object {at, paragraphs}" % where)
            continue
        if not _filled(record.get("at")):
            out.append("%s has no at" % where)
        if "paragraphs" in record and not _texts(record["paragraphs"]):
            out.append("%s.paragraphs is not a string or a list of strings" % where)
    return out


def _context(context) -> List[str]:
    if deleted(context):
        return []
    if not isinstance(context, dict):
        return ["context is not an object"]
    out = []
    if "paragraphs" in context and not deleted(context["paragraphs"]):
        if isinstance(context["paragraphs"], str):
            out.append("context.paragraphs is a string; the page draws only a list of strings "
                       "there, so it would show nothing")
        elif not _strings(context["paragraphs"]):
            out.append("context.paragraphs is not a list of strings")
    for side in ("for", "against"):
        if side in context:
            out.extend(_readings(context, side))
    if "prediction" in context:
        out.extend(_prediction(context["prediction"]))
    if "log" in context:
        out.extend(_log(context["log"]))
    return out


def _recommends(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(isinstance(x, str) and x.strip() for x in value)
    return False


def _next(value) -> List[str]:
    if deleted(value):
        return []
    if not isinstance(value, dict):
        return ["next is not an object"]
    out = []
    for key in ("kind", "prompt"):
        if not _filled(value.get(key)):
            out.append("next has no %s; a write of next carries kind and prompt" % key)
    if value.get("kind") == "question" and _recommends(value.get("recommendation")):
        out.append("next is a question and carries a recommendation; a question is put "
                   "with none")
    return out


def check(update) -> List[str]:
    """The findings on an object about to be written to ``ordo/current``."""
    if not isinstance(update, dict):
        return ["the write is not a JSON object"]
    out = []
    if "context" in update:
        out.extend(_context(update["context"]))
    if "next" in update:
        out.extend(_next(update["next"]))
    return out
