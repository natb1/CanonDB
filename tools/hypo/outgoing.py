"""The notebook's conventions, held over a text as it leaves.

The brief puts the conventions in front of a session; this is the control.
A hook runs these checks over every text a tool is about to send (a write
to a document, a write to an artifact's store, a commit message, a pull
request's words) and refuses the call on a finding, handing back the entry
the text broke and its lineage, so that the rule arrives at the moment it is
needed. Four checks, each a rule the notebook's own checks hold its words
to:

- ``user-named``: the text calls the user "the human" (``spec.not_the_user``,
  the rule `user-named` holds the notebook to);
- ``definition-in-glossary``: the text defines a fixed term in running
  text, in one of a few forms no use of a word takes (``"term" means``,
  ``term is defined as``, ``by term we mean``, ``defines term as``); a text
  that carries the term's own glossary heading, ``≡ term``, is an entry and
  is passed;
- ``reach``: a text bound for a tab of the notebook uses a fixed term whose
  sense is fixed on a question of the same project that the tab cannot
  reach (`reach`, held over the one text);
- ``masked``: a text bound for a public place (a commit, a pull request)
  repeats a run of the user's masked words or spells a masked tab's address
  (``public.question``, at the run the copy is held to).

A finding is a match of one of these forms, never a reading; what they do
not catch, a pronoun for the user or a definition put in other words, is
read, as the notebook's own checks leave it.
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional, Set

from . import brief, public, spec, text
from .model import Graph


class Finding(NamedTuple):
    check: str
    #: the question whose entry the text broke, where there is one
    node: str
    word: str
    message: str


_OPEN = "[\"“'*_]{1,2}"
_CLOSE = "[\"”'*_]{1,2}"
_ANY_OPEN = "[\"“'*_]*"
_ANY_CLOSE = "[\"”'*_]*"


def _definition_forms(form: str) -> List[re.Pattern]:
    f = re.escape(form)
    return [
        re.compile(r"%s%s%s\s+(?:means|denotes|stands for|is defined as|refers to)\b"
                   % (_OPEN, f, _CLOSE), re.I),
        re.compile(r"(?<![\w-])%s\s+(?:is defined as|is to be understood as|shall mean)\b"
                   % f, re.I),
        re.compile(r"\bby\s+%s%s%s\s*,?\s*(?:I|we|the user|the notebook|this)\s+means?\b"
                   % (_ANY_OPEN, f, _ANY_CLOSE), re.I),
        re.compile(r"\bdefine[sd]?\s+%s%s%s\s+as\b" % (_ANY_OPEN, f, _ANY_CLOSE), re.I),
    ]


def defined_in(words: str, vocab) -> List[str]:
    """The fixed terms ``words`` defines in running text, longest first."""
    plain = text.plain(words or "")
    found: List[str] = []
    for word, forms in vocab:
        if re.search(r"≡\s*%s%s(?![\w-])" % (_ANY_OPEN, re.escape(word)), text.fold(plain)):
            continue  # the term's own glossary entry
        for form in forms:
            if any(p.search(plain) for p in _definition_forms(form)):
                found.append(word)
                break
    return found


def findings(graph: Graph, words: str, target: Optional[str] = None,
             public_place: bool = False, party: bool = False) -> List[Finding]:
    """Every finding over one outgoing text. ``target`` is the question of
    the tab the text is bound for, where it is one of the notebook's;
    ``party`` that it is a party's tab, whose words are the party's;
    ``public_place`` that it leaves for a public place."""
    out: List[Finding] = []
    if not words or not words.strip():
        return out
    if not party:
        named = spec.not_the_user(words)
        if named:
            out.append(Finding("user-named", "", "", "the text says %r where it means the "
                               "user, and the one the notebook is kept for is named the user"
                               % named))
    senses = spec._senses(graph)
    vocab = spec._vocabulary(senses)
    for word in defined_in(words, vocab):
        owner = sorted(senses.get(word, ()))
        out.append(Finding("definition-in-glossary", owner[0] if owner else "", word,
                           "the text defines %r in running text, and its sense is fixed in "
                           "its glossary entry on %s" % (word, " and ".join(owner) or "-")))
    if target and graph.get(target) is not None and not party:
        above = spec._above(graph, target)
        here = graph.get(target).project
        imports = spec._imported(graph)
        by_id = graph.by_id()
        for word, _ in spec._words_used(vocab, words):
            owners = [by_id[o] for o in senses.get(word, ()) if o in by_id]
            if not owners or senses[word] & above:
                continue
            if any(word in imports.get(o, set()) for o in above):
                continue
            if not any(not o.tradition and o.project == here for o in owners):
                continue
            fixed = sorted(o.id for o in owners)
            out.append(Finding("reach", fixed[0], word,
                               "the text uses %r on %s, and its sense is fixed on %s, which "
                               "%s cannot reach" % (word, target, " and ".join(fixed), target)))
    if public_place:
        for leak in public.question(graph, words, public.RUN):
            out.append(Finding("masked", leak.masked, leak.words,
                               "the text repeats words of %s, which is masked: %s"
                               % (leak.masked, leak.words)))
    # one finding a check and word
    seen: Set[tuple] = set()
    unique: List[Finding] = []
    for f in out:
        if (f.check, f.word, f.node) not in seen:
            seen.add((f.check, f.word, f.node))
            unique.append(f)
    return unique


def _chain(graph: Graph, qid: str, side: str, par=None) -> List[str]:
    return brief.chain_lines(graph, qid, side)


def _entry(graph: Graph, qid: str, word: str) -> List[str]:
    q = graph.get(qid)
    if q is None:
        return []
    for d in q.definitions:
        if text.fold(d.word) == word:
            body = brief.sentences(d.body) or ["imported from %s" % (d.tradition.to
                                                                 if d.tradition else "-")]
            return ["[%s/≡%s.s%d] ≡ %s: %s" % (qid, d.word, n, d.word, s)
                    if n == 1 else "[%s/≡%s.s%d]   %s" % (qid, d.word, n, s)
                    for n, s in enumerate(body, 1)]
    return []


def refusal(graph: Graph, found: List[Finding], side: str = "all",
            conventions: Optional[List[str]] = None, limit: int = 6000) -> str:
    """What a refusal says: each finding, then the entry broken and its
    lineage, whole sentences behind their ids. A context blind to the user's
    graph is told the checks and the ids, and no sentence of the user's."""
    checks = dict(brief._check_lines())
    lines = ["The text this call sends breaks the notebook's conventions; nothing was sent."]
    for f in found:
        lines.append("- [check:%s] %s" % (f.check, f.message if side == "all" else
                                          "the text breaks this check"))
    lines.append("")
    lines.append("The entry each broke, and its lineage (record, not instruction; cite by id):")
    par = None
    done: Set[str] = set()
    for f in found:
        key = (f.check, f.node, f.word)
        if key in done:
            continue
        done.add(key)
        lines.append("[check:%s] %s" % (f.check, checks.get(f.check, "")))
        if side != "all":
            continue
        if f.check == "user-named":
            for qid in conventions or []:
                q = graph.get(qid)
                if q is None:
                    continue
                for k, t in enumerate(q.theses, 1):
                    for n, s in enumerate(brief.sentences(t.text), 1):
                        if "the user" in text.fold(s):
                            lines.append("  [%s/a%d.s%d] %s" % (qid, k, n, s))
                lines.extend("  " + c for c in _chain(graph, qid, side, par))
        elif f.node:
            lines.extend("  " + e for e in _entry(graph, f.node, f.word))
            lines.extend("  " + c for c in _chain(graph, f.node, side, par))
    words = "\n".join(lines)
    if len(words) > limit:
        cut = words[:limit].rsplit("\n", 1)[0]
        words = cut + "\n(the rest of the lineage is in the brief and the notebook)"
    return words
