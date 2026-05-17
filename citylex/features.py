"""Converts between different morphological feature formats.

* For CELEX, see the CELEX English manual (ch. 3).
* For UniMorph, see https://unimorph.github.io/doc/unimorph-schema.pdf.
* For Universal Dependencies, see https://universaldependencies.org/u/feat/.

Mappings are defined once in ``_CANONICAL`` as a flat list of
``(source_format, source_tag, target_format, target_tag)`` tuples.
The lookup dict ``_map_dict`` is derived from that table automatically, so
there is no risk of updating one direction while forgetting the other.

One-to-many relationships are represented as lists of target tags; the helper
``tag_to_tag`` returns either a single string, a list of strings, or ``None``.
"""

from collections import defaultdict
from typing import Union

# Canonical mapping table. Format: (from_format, from_tag, to_format, to_tag).
#
# Where a single source tag maps to *multiple* target tags, add one entry per
# target tag — `_build_map` will accumulate them into a list automatically.
# Where a single source tag maps to a single target tag, add one entry and it
# will be stored as a plain string (no list wrapper needed).

_CANONICAL: list[tuple[str, str, str, str]] = [
    # Adverb.
    ("CELEX", "B", "UniMorph", "ADV"),
    ("CELEX", "B", "UD", "ADV"),
    ("UniMorph", "ADV", "CELEX", "B"),
    ("UniMorph", "ADV", "UD", "ADV"),
    ("UniMorph", "ADV;CMPR", "UD", "ADV|Degree=Cmp"),
    ("UniMorph", "ADV;SPRL", "UD", "ADV|Degree=Sup"),
    ("UD", "ADV", "CELEX", "B"),
    ("UD", "ADV", "UniMorph", "ADV"),
    ("UD", "ADV|Degree=Cmp", "UniMorph", "ADV;CMPR"),
    ("UD", "ADV|Degree=Sup", "UniMorph", "ADV;SPRL"),
    # Adjective.
    ("CELEX", "b", "UniMorph", "ADJ"),
    ("CELEX", "b", "UD", "ADJ"),
    ("CELEX", "c", "UniMorph", "ADJ;CMPR"),
    ("CELEX", "c", "UD", "ADJ|Degree=Cmp"),
    ("CELEX", "s", "UniMorph", "ADJ;SPRL"),
    ("CELEX", "s", "UD", "ADJ|Degree=Sup"),
    ("UniMorph", "ADJ", "CELEX", "b"),
    ("UniMorph", "ADJ", "UD", "ADJ"),
    ("UniMorph", "ADJ;CMPR", "CELEX", "c"),
    ("UniMorph", "ADJ;CMPR", "UD", "ADJ|Degree=Cmp"),
    ("UniMorph", "ADJ;SPRL", "CELEX", "s"),
    ("UniMorph", "ADJ;SPRL", "UD", "ADJ|Degree=Sup"),
    ("UD", "ADJ", "CELEX", "b"),
    ("UD", "ADJ", "UniMorph", "ADJ"),
    ("UD", "ADJ|Degree=Cmp", "CELEX", "c"),
    ("UD", "ADJ|Degree=Cmp", "UniMorph", "ADJ;CMPR"),
    ("UD", "ADJ|Degree=Sup", "CELEX", "s"),
    ("UD", "ADJ|Degree=Sup", "UniMorph", "ADJ;SPRL"),
    # Noun (proper nouns collapse to the same CELEX/UniMorph tags).
    ("CELEX", "S", "UniMorph", "N;SG"),
    ("CELEX", "P", "UniMorph", "N;PL"),
    ("UniMorph", "N;SG", "CELEX", "S"),
    ("UniMorph", "N;PL", "CELEX", "P"),
    ("UD", "NOUN|Number=Sing", "CELEX", "S"),
    ("UD", "NOUN|Number=Sing", "UniMorph", "N;SG"),
    ("UD", "NOUN|Number=Plur", "CELEX", "P"),
    ("UD", "NOUN|Number=Plur", "UniMorph", "N;PL"),
    ("UD", "PROPN|Gender=Fem|Number=Sing", "CELEX", "S"),
    ("UD", "PROPN|Gender=Fem|Number=Sing", "UniMorph", "N;SG"),
    ("UD", "PROPN|Gender=Masc|Number=Sing", "CELEX", "S"),
    ("UD", "PROPN|Gender=Masc|Number=Sing", "UniMorph", "N;SG"),
    ("UD", "PROPN|Number=Plur", "CELEX", "P"),
    ("UD", "PROPN|Number=Plur", "UniMorph", "N;PL"),
    ("UD", "PROPN|Gender=Fem|Number=Plur", "CELEX", "P"),
    ("UD", "PROPN|Gender=Fem|Number=Plur", "UniMorph", "N;PL"),
    ("UD", "PROPN|Gender=Masc|Number=Plur", "CELEX", "P"),
    ("UD", "PROPN|Gender=Masc|Number=Plur", "UniMorph", "N;PL"),
    # Verb — infinitive/imperative/subjunctive.
    # CELEX conflates several English bare-stem uses as "i":
    # - infinitive
    # - imperative
    # - present subjunctive
    #
    # UD and UniMorph distinguish these analyses, so CELEX to UD/UniMorph
    # is one-to-many, while the reverse direction collapses back to "i".
    ("CELEX", "i", "UniMorph", "V;NFIN"),
    ("CELEX", "i", "UniMorph", "V;IMP"),
    ("CELEX", "i", "UniMorph", "V;SBJV;PRS"),
    ("CELEX", "i", "UD", "VERB|VerbForm=Inf"),
    ("CELEX", "i", "UD", "VERB|Mood=Imp"),
    ("CELEX", "i", "UD", "VERB|Mood=Sub|Tense=Pres"),
    ("UniMorph", "V;NFIN", "CELEX", "i"),
    ("UniMorph", "V;IMP", "CELEX", "i"),
    ("UniMorph", "V;SBJV;PRS", "CELEX", "i"),
    ("UniMorph", "V;NFIN", "UD", "VERB|VerbForm=Inf"),
    ("UniMorph", "V;IMP", "UD", "VERB|Mood=Imp"),
    ("UniMorph", "V;SBJV;PRS", "UD", "VERB|Mood=Sub|Tense=Pres"),
    ("UD", "VERB|VerbForm=Inf", "CELEX", "i"),
    ("UD", "VERB|Mood=Imp", "CELEX", "i"),
    ("UD", "VERB|Mood=Sub|Tense=Pres", "CELEX", "i"),
    ("UD", "VERB|VerbForm=Inf", "UniMorph", "V;NFIN"),
    ("UD", "VERB|Mood=Imp", "UniMorph", "V;IMP"),
    ("UD", "VERB|Mood=Sub|Tense=Pres", "UniMorph", "V;SBJV;PRS"),
    # Verb — present participle.
    ("CELEX", "pe", "UniMorph", "V;V.PTCP;PRS"),
    ("CELEX", "pe", "UD", "VERB|Tense=Pres|VerbForm=Part"),
    ("UniMorph", "V;V.PTCP;PRS", "CELEX", "pe"),
    ("UniMorph", "V;V.PTCP;PRS", "UD", "VERB|Tense=Pres|VerbForm=Part"),
    ("UD", "VERB|Tense=Pres|VerbForm=Part", "CELEX", "pe"),
    ("UD", "VERB|Tense=Pres|VerbForm=Part", "UniMorph", "V;V.PTCP;PRS"),
    # Verb — present tense (non-3sg).
    # CELEX distinguishes 1sg / 2sg / plural; UniMorph merges them as V;PRS.
    ("CELEX", "e1S", "UniMorph", "V;PRS"),
    ("CELEX", "e1S", "UD", "VERB|Number=Sing|Person=1|Tense=Pres"),
    ("CELEX", "e2S", "UniMorph", "V;PRS"),
    ("CELEX", "e2S", "UD", "VERB|Number=Sing|Person=2|Tense=Pres"),
    ("CELEX", "eP", "UniMorph", "V;PRS"),
    ("CELEX", "eP", "UD", "VERB|Number=Plur|Person=1|Tense=Pres"),
    ("CELEX", "eP", "UD", "VERB|Number=Plur|Person=2|Tense=Pres"),
    ("CELEX", "eP", "UD", "VERB|Number=Plur|Person=3|Tense=Pres"),
    ("UniMorph", "V;PRS", "CELEX", "e1S"),
    ("UniMorph", "V;PRS", "CELEX", "e2S"),
    ("UniMorph", "V;PRS", "CELEX", "eP"),
    ("UniMorph", "V;PRS", "UD", "VERB|Number=Sing|Person=1|Tense=Pres"),
    ("UniMorph", "V;PRS", "UD", "VERB|Number=Sing|Person=2|Tense=Pres"),
    ("UniMorph", "V;PRS", "UD", "VERB|Number=Plur|Person=1|Tense=Pres"),
    ("UniMorph", "V;PRS", "UD", "VERB|Number=Plur|Person=2|Tense=Pres"),
    ("UniMorph", "V;PRS", "UD", "VERB|Number=Plur|Person=3|Tense=Pres"),
    ("UD", "VERB|Number=Sing|Person=1|Tense=Pres", "CELEX", "e1S"),
    ("UD", "VERB|Number=Sing|Person=1|Tense=Pres", "UniMorph", "V;PRS"),
    ("UD", "VERB|Number=Sing|Person=2|Tense=Pres", "CELEX", "e2S"),
    ("UD", "VERB|Number=Sing|Person=2|Tense=Pres", "UniMorph", "V;PRS"),
    ("UD", "VERB|Number=Plur|Person=1|Tense=Pres", "CELEX", "eP"),
    ("UD", "VERB|Number=Plur|Person=1|Tense=Pres", "UniMorph", "V;PRS"),
    ("UD", "VERB|Number=Plur|Person=2|Tense=Pres", "CELEX", "eP"),
    ("UD", "VERB|Number=Plur|Person=2|Tense=Pres", "UniMorph", "V;PRS"),
    ("UD", "VERB|Number=Plur|Person=3|Tense=Pres", "CELEX", "eP"),
    ("UD", "VERB|Number=Plur|Person=3|Tense=Pres", "UniMorph", "V;PRS"),
    # Verb — present tense 3sg.
    ("CELEX", "e3S", "UniMorph", "V;PRS;3;SG"),
    ("CELEX", "e3S", "UD", "VERB|Number=Sing|Person=3|Tense=Pres"),
    ("UniMorph", "V;PRS;3;SG", "CELEX", "e3S"),
    ("UniMorph", "V;PRS;3;SG", "UD", "VERB|Number=Sing|Person=3|Tense=Pres"),
    ("UD", "VERB|Number=Sing|Person=3|Tense=Pres", "CELEX", "e3S"),
    ("UD", "VERB|Number=Sing|Person=3|Tense=Pres", "UniMorph", "V;PRS;3;SG"),
    # Verb — past tense.
    ("CELEX", "a1S", "UniMorph", "V;PST"),
    ("CELEX", "a1S", "UD", "VERB|Number=Sing|Person=1|Tense=Past"),
    ("CELEX", "a2S", "UniMorph", "V;PST"),
    ("CELEX", "a2S", "UD", "VERB|Number=Sing|Person=2|Tense=Past"),
    ("CELEX", "a3S", "UniMorph", "V;PST"),
    ("CELEX", "a3S", "UD", "VERB|Number=Sing|Person=3|Tense=Past"),
    ("CELEX", "aP", "UniMorph", "V;PST"),
    ("CELEX", "aP", "UD", "VERB|Number=Plur|Person=1|Tense=Past"),
    ("CELEX", "aP", "UD", "VERB|Number=Plur|Person=2|Tense=Past"),
    ("CELEX", "aP", "UD", "VERB|Number=Plur|Person=3|Tense=Past"),
    ("UniMorph", "V;PST", "CELEX", "a1S"),
    ("UniMorph", "V;PST", "CELEX", "a2S"),
    ("UniMorph", "V;PST", "CELEX", "a3S"),
    ("UniMorph", "V;PST", "CELEX", "aP"),
    ("UniMorph", "V;PST", "UD", "VERB|Number=Sing|Person=1|Tense=Past"),
    ("UniMorph", "V;PST", "UD", "VERB|Number=Sing|Person=2|Tense=Past"),
    ("UniMorph", "V;PST", "UD", "VERB|Number=Sing|Person=3|Tense=Past"),
    ("UniMorph", "V;PST", "UD", "VERB|Number=Plur|Person=1|Tense=Past"),
    ("UniMorph", "V;PST", "UD", "VERB|Number=Plur|Person=2|Tense=Past"),
    ("UniMorph", "V;PST", "UD", "VERB|Number=Plur|Person=3|Tense=Past"),
    ("UD", "VERB|Number=Sing|Person=1|Tense=Past", "CELEX", "a1S"),
    ("UD", "VERB|Number=Sing|Person=1|Tense=Past", "UniMorph", "V;PST"),
    ("UD", "VERB|Number=Sing|Person=2|Tense=Past", "CELEX", "a2S"),
    ("UD", "VERB|Number=Sing|Person=2|Tense=Past", "UniMorph", "V;PST"),
    ("UD", "VERB|Number=Sing|Person=3|Tense=Past", "CELEX", "a3S"),
    ("UD", "VERB|Number=Sing|Person=3|Tense=Past", "UniMorph", "V;PST"),
    ("UD", "VERB|Number=Plur|Person=1|Tense=Past", "CELEX", "aP"),
    ("UD", "VERB|Number=Plur|Person=1|Tense=Past", "UniMorph", "V;PST"),
    ("UD", "VERB|Number=Plur|Person=2|Tense=Past", "CELEX", "aP"),
    ("UD", "VERB|Number=Plur|Person=2|Tense=Past", "UniMorph", "V;PST"),
    ("UD", "VERB|Number=Plur|Person=3|Tense=Past", "CELEX", "aP"),
    ("UD", "VERB|Number=Plur|Person=3|Tense=Past", "UniMorph", "V;PST"),
    # Verb — past participle.
    ("CELEX", "pa", "UniMorph", "V;V.PTCP;PST"),
    ("CELEX", "pa", "UD", "VERB|Tense=Past|VerbForm=Part"),
    ("UniMorph", "V;V.PTCP;PST", "CELEX", "pa"),
    ("UniMorph", "V;V.PTCP;PST", "UD", "VERB|Tense=Past|VerbForm=Part"),
    ("UD", "VERB|Tense=Past|VerbForm=Part", "CELEX", "pa"),
    ("UD", "VERB|Tense=Past|VerbForm=Part", "UniMorph", "V;V.PTCP;PST"),
]


# Builds the lookup dict from the canonical table.
#
# Structure: _map_dict[from_format][from_tag][to_format] = tag_or_list
#
# A mapping with a single target is stored as a plain string.
# A mapping with multiple targets is stored as a list of strings.

# Internal accumulator uses sets to deduplicate during construction.
_AccumType = dict[str, dict[str, dict[str, list[str]]]]
_accum: _AccumType = defaultdict(
    lambda: defaultdict(lambda: defaultdict(list))
)
for _src_fmt, _src_tag, _dst_fmt, _dst_tag in _CANONICAL:
    current = _accum[_src_fmt][_src_tag][_dst_fmt]
    if _dst_tag not in current:
        current.append(_dst_tag)

# Flattens sets: single-item sets become plain strings and multi-item become
# lists.
_MapValue = Union[str, list[str]]
_map_dict: dict[str, dict[str, dict[str, _MapValue]]] = {}
for _src_fmt, _src_tags in _accum.items():
    _map_dict[_src_fmt] = {}
    for _src_tag, _dst_fmts in _src_tags.items():
        _map_dict[_src_fmt][_src_tag] = {}
        for _dst_fmt, _dst_list in _dst_fmts.items():
            _map_dict[_src_fmt][_src_tag][_dst_fmt] = (
                _dst_list[0] if len(_dst_list) == 1 else _dst_list
            )


# Public API.


def tag_to_tag(
    from_name: str,
    to_name: str,
    tag: str,
) -> Union[str, list[str], None]:
    """Maps a morphological tag in one feature system to another.

    Args:
        from_name: the source system (one of: "CELEX", "UniMorph", "UD").
        to_name: the target system (one of: "CELEX", "UniMorph", "UD").
        tag: the tag in the source system to look up.

    Returns:
        A single tag string, a list of tag strings, or ``None`` if the
        mapping is not defined.
    """
    try:
        return _map_dict[from_name][tag][to_name]
    except KeyError:
        return None
