"""Converts between different feature formats.

* For CELEX, see the CELEX English manual (ch. 3).
* For UniMorph, see https://unimorph.github.io/doc/unimorph-schema.pdf.
* For Universal Dependencies, see https://universaldependencies.org/u/feat/.

Use `tag_to_tag` to retrieve actual mappings.
"""

from typing import Dict, Optional

# The format is (CELEX tag, UniMorph tag, UD tag). Use an interior list to
# indicate that multiple tags in one system map to a single tag in another;
# in this case, only the first tag will be mapped to.
_map_cols = ("CELEX", "UniMorph", "UD")
_map_tuples = [
    # Adverb.
    ("B", "ADV", "ADV|_"),
    # Positive adjective.
    ("b", "ADJ", "ADJ|_"),
    # Comparative adjective.
    ("c", "ADJ;CMPR", "ADJ|Degree=Cmp"),
    # Superlative adjective.
    ("s", "ADJ;RL", "ADJ|Degree=Sup"),
    # Infinitive.
    ("i", "V;NFIN", "VERB|VerbForm=Inf"),
    # Present participle.
    ("pe", "V.PTCP;PRS", "VERB|Tense=Pres|VerbForm=Part"),
    # Past participle.
    ("pa", "V.PTCP;PST", "VERB|Tense=Past|VerbForm=Part"),
    # Simple past.
    ("a1S", "V;PST", "VERB|Tense=Past"),
    # 3sg present.
    ("e3S", "V;SG;3;PRS", "VERB|Number=Sing|Person=3|Tense=Pres"),
    # Noun singular.
    (
        "S",
        "N;SG",
        [
            "NOUN|Number=Sing",
            "PROPN|Number=Sing",
            "PROPN|Gender=Fem|Number=Sing",
            "PROPN|Gender=Masc|Number=Sing",
        ],
    ),
    # Noun plural.
    (
        "P",
        "N;PL",
        [
            "NOUN|Number=Plur",
            "PROPN|Number=Plur",
            "PROPN|Gender=Fem|Number=Plur",
            "PROPN|Gender=Masc|Number=Plur",
        ],
    ),
]


def _inner_dict_factory(from_index: int, to_index: int) -> Dict[str, str]:
    result = {}
    for row in _map_tuples:
        from_tag = row[from_index]
        to_tag = row[to_index]
        if isinstance(from_tag, str):
            if isinstance(to_tag, str):
                result[from_tag] = to_tag
            else:
                # Only taking the first tag from the interior list.
                result[from_tag] = to_tag[0]
        else:
            assert isinstance(to_tag, str), "unexpected many-to-many mapping"
            for tag in from_tag:
                result[tag] = to_tag
    return result


# Turns the above into dictionaries. The format is
# [source tag][destination tag][tag].
_map_dict = {
    outer: {
        inner: _inner_dict_factory(i, j)
        for j, inner in enumerate(_map_cols)
        if i != j
    }
    for i, outer in enumerate(_map_cols)
}


def tag_to_tag(from_name: str, to_name: str, tag: str) -> Optional[str]:
    """Maps a morphological tag in one feature system to another.

    Args:
        from_name: the source system for the morphological tag (one of:
            "CELEX", "UniMorph", "UD").
        to_name: the target for the morphological tag (one of:
            "CELEX", "UniMorph, "UD").
        tag: the source system tag to look up.

    Returns:
        The tag in the target system, or None if not found.
    """
    assert from_name != to_name, "no-op mapping"
    return _map_dict[from_name][to_name].get(tag)
