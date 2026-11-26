"""card — the check on a write of the page's ``ordo/current`` before it is sent.

The page draws what the document holds and says nothing of a field it
cannot draw: a reading of tradition given as a plain string draws an empty
line, a prediction that is not an object draws "No prediction was sealed",
notes or paragraphs given as one string draw nothing, a kind outside the
four is drawn as `work` and then shows a recommendation, and a time that does
not parse is drawn bare. A question that carries a recommendation or a `how`
breaks the rule that a question is put alone. This module reads the object
about to be written, whole or a partial ``update`` holding any of its
fields, and returns one finding per fault. An empty list is a write the page
can draw.

A field may be removed by the deletion marker ``{"__delete__": true}``,
which is taken wherever a field may stand.

Nothing here reaches the network or writes the page.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from typing import List

#: the parts of a prediction the page draws
PREDICTION = ("predicted", "diverged", "addressed")

#: the four kinds of action; the page draws any other as `work`
KINDS = ("question", "office", "work", "review")

#: the fields of `next` the card draws: a write holding one carries the action's kind and prompt
DRAWN = ("kind", "prompt", "case", "line", "recommendation", "how", "put_at")

#: an ISO 8601 time with its offset, as every stamp the speaker writes is
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$")


def deleted(value) -> bool:
    """The deletion marker, which removes the field it stands for."""
    return isinstance(value, dict) and value.get("__delete__") is True and len(value) == 1


def _texts(value) -> bool:
    """A string or a list of strings."""
    return isinstance(value, str) or _strings(value)


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def _filled(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time(value) -> bool:
    if not isinstance(value, str) or not ISO.match(value):
        return False
    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _present(holder: dict, key: str) -> bool:
    """The field is written with a value, not removed."""
    return key in holder and not deleted(holder[key])


def _list_of_strings(holder: dict, key: str, where: str) -> List[str]:
    if not _present(holder, key):
        return []
    value = holder[key]
    if isinstance(value, str):
        return ["%s is a string; the page draws only a list of strings there, so it would show "
                "nothing" % where]
    if not _strings(value):
        return ["%s is not a list of strings" % where]
    return []


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
        if "at" not in record:
            out.append("%s has no at" % where)
        elif not _time(record["at"]):
            out.append("%s.at is not an ISO time with its offset; the page would draw it "
                       "bare" % where)
        if "paragraphs" in record and not _texts(record["paragraphs"]):
            out.append("%s.paragraphs is not a string or a list of strings" % where)
    return out


def _context(context) -> List[str]:
    if deleted(context):
        return []
    if not isinstance(context, dict):
        return ["context is not an object"]
    out = []
    if _present(context, "heading") and not isinstance(context["heading"], str):
        out.append("context.heading is not a string")
    out.extend(_list_of_strings(context, "paragraphs", "context.paragraphs"))
    out.extend(_list_of_strings(context, "notes", "context.notes"))
    if _present(context, "at") and not _time(context["at"]):
        out.append("context.at is not an ISO time with its offset")
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


def _kind(holder: dict, where: str) -> List[str]:
    if _present(holder, "kind") and holder["kind"] not in KINDS:
        return ["%s.kind %r is not one of %s; the page would draw it as work"
                % (where, holder["kind"], ", ".join(KINDS))]
    return []


def _next(value) -> List[str]:
    if deleted(value):
        return []
    if not isinstance(value, dict):
        return ["next is not an object"]
    out = []
    if any(_present(value, key) for key in DRAWN):
        for key in ("kind", "prompt"):
            if not _filled(value.get(key)):
                out.append("next has no %s; a write of a field the card draws carries the "
                           "action's kind and prompt" % key)
    out.extend(_kind(value, "next"))
    for key in ("prompt", "case", "line", "how"):
        if _present(value, key) and not isinstance(value[key], str):
            out.append("next.%s is not a string" % key)
    if _present(value, "recommendation") and not _texts(value["recommendation"]):
        out.append("next.recommendation is not a string or a list of strings; the page would "
                   "show none")
    kind = value.get("kind")
    if kind == "question" and _recommends(value.get("recommendation")):
        out.append("next is a question and carries a recommendation; a question is put "
                   "with none")
    if kind in ("question", "review") and _recommends(value.get("how")):
        out.append("next is a %s and carries a how; a how is never set for a question or a "
                   "review" % kind)
    for key in ("put_at", "resolved_at"):
        if _present(value, key) and not _time(value[key]):
            out.append("next.%s is not an ISO time with its offset" % key)
    if _present(value, "deferred"):
        out.extend(_deferred(value["deferred"]))
    if _present(value, "reading"):
        out.extend(_reading(value))
    return out


#: what a reading's record must say for its question to be shown
READ_TOOL, CLEAR = "lead.py record", "does not lead"


def _reading(value: dict) -> List[str]:
    """``next.reading``, the path of the record of the reading of a question
    for the AI's own record (``lead.py record``), which a review that shows
    such a question names: the record must be of exactly the question the
    prompt shows, beside it as ``question.md``, and say it does not lead."""
    path = value["reading"]
    if not isinstance(path, str) or not os.path.isabs(path):
        return ["next.reading is not the absolute path of a question's lead.json"]
    if value.get("kind") != "review":
        return ["next.reading is given on a %r; a question for the AI's record is shown "
                "as a review" % value.get("kind")]
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
        with open(os.path.join(os.path.dirname(path), "question.md"), "rb") as fh:
            raw = fh.read()
    except (OSError, ValueError) as exc:
        return ["next.reading cannot be read with its question beside it: %s" % exc]
    out = []
    if not isinstance(got, dict) or got.get("tool") != READ_TOOL:
        return ["next.reading is not a record %s wrote" % READ_TOOL]
    if got.get("sha256") != hashlib.sha256(raw).hexdigest():
        out.append("next.reading is of another text than the question beside it: read it "
                   "again before it is shown")
    if got.get("verdict") != CLEAR:
        out.append("next.reading says the question leads the answerer: it is never shown")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if not isinstance(value.get("prompt"), str) or text is None \
            or " ".join(text.split()) != " ".join(value["prompt"].split()):
        out.append("next.prompt is not the question its reading was of, word for word")
    return out


def _deferred(value) -> List[str]:
    """``next.deferred``, which the page shows only where its prompt is set."""
    if not isinstance(value, dict):
        return ["next.deferred is not an object {prompt, reason, kind, line}"]
    out = []
    if not _filled(value.get("prompt")):
        out.append("next.deferred has no prompt; the page would not show it")
    for key in ("reason", "line"):
        if _present(value, key) and not isinstance(value[key], str):
            out.append("next.deferred.%s is not a string" % key)
    out.extend(_kind(value, "next.deferred"))
    return out


def _office_deferred(value) -> List[str]:
    """``office_deferred``, which the page ignores unless ``since`` is a time
    and ``bell`` a base time without its colon."""
    if deleted(value):
        return []
    if not isinstance(value, dict):
        return ["office_deferred is not an object {reason, since, bell}"]
    out = []
    if not _time(value.get("since")):
        out.append("office_deferred.since is not an ISO time with its offset; the page "
                   "would ignore the set-aside")
    if not (isinstance(value.get("bell"), str) and re.match(r"^\d{4}$", value["bell"])):
        out.append("office_deferred.bell is not a bell's base time as HHMM; the page would "
                   "ignore the set-aside")
    if _present(value, "reason") and not isinstance(value["reason"], str):
        out.append("office_deferred.reason is not a string")
    return out


def _queue(value) -> List[str]:
    if deleted(value):
        return []
    if not isinstance(value, list):
        return ["queue is not a list of actions"]
    out = []
    for n, item in enumerate(value):
        where = "queue[%d]" % n
        if not isinstance(item, dict):
            out.append("%s is not an object; the page drops it" % where)
            continue
        if not (_filled(item.get("title")) or _filled(item.get("prompt"))):
            out.append("%s has neither title nor prompt; the page drops it" % where)
        out.extend(_kind(item, where))
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
    if "queue" in update:
        out.extend(_queue(update["queue"]))
    if "office_deferred" in update:
        out.extend(_office_deferred(update["office_deferred"]))
    if _present(update, "background") and not _strings(update["background"]):
        out.append("background is not a list of strings")
    if "updated" not in update:
        out.append("the write has no updated; every write sets it")
    elif not _time(update["updated"]):
        out.append("updated is not an ISO time with its offset")
    return out
