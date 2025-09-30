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
    # Adverbs.
    ("B", "ADV", "ADV"),
    ("B", "ADV", "ADV|_"),
    ("", "ADV;CMPR", "ADV|Degree=Cmp"),
    ("", "ADV;SPRL", "ADV|Degree=Sup"),
    # Adjectives.
    ("b", "ADJ", "ADJ"),
    ("b", "ADJ", "ADJ|_"),
    ("c", "ADJ;CMPR", "ADJ|Degree=Cmp"),
    ("s", "ADJ;SPRL", "ADJ|Degree=Sup"),
    # Verbs.
    # CELEX collapses imperatives with infinitives to 'i'.
    ("i", "V;IMP", "VERB|Mood=Imp"),
    ("i", "V;NFIN;IMP+SBJV", "VERB|VerbForm=Inf"),
    # CELEX collapses gerund + participles to 'p'.
    ("p", "V;GER", "VERB|VerbForm=Ger"),
    ("p", "V;V.PTCP;PST", "VERB|Tense=Past|VerbForm=Part"),
    ("p", "V;V.PTCP;PRS", "VERB|Tense=Pres|VerbForm=Part"),
    ("a1S", "V;PST", "VERB|Tense=Past"),
    # Finite verbs: UD->UM only.
    ("", "V;PRS", "VERB|Tense=Pres"),
    ("", "V;PRS", "VERB|Number=Sing|Person=1|Tense=Pres"),
    ("", "V;PRS", "VERB|Number=Sing|Person=2|Tense=Pres"),
    # Third-person singular.
    ("e3S", ["V;PRS;3;SG"], "VERB|Number=Sing|Person=3|Tense=Pres"),
    ("", "V;PRS", "VERB|Number=Plur|Person=1|Tense=Pres"),
    ("", "V;PRS", "VERB|Number=Plur|Person=2|Tense=Pres"),
    ("", "V;PRS", "VERB|Number=Plur|Person=3|Tense=Pres"),
    ("", "V;PST", "VERB|Number=Sing|Person=1|Tense=Past"),
    ("", "V;PST", "VERB|Number=Sing|Person=2|Tense=Past"),
    ("", "V;PST", "VERB|Number=Sing|Person=3|Tense=Past"),
    ("", "V;PST", "VERB|Number=Plur|Person=1|Tense=Past"),
    ("", "V;PST", "VERB|Number=Plur|Person=2|Tense=Past"),
    ("", "V;PST", "VERB|Number=Plur|Person=3|Tense=Past"),
    ("", "V;SBJV;PRS", "VERB|Mood=Sub|Tense=Pres"),
    # Nouns.
    (
        "S",
        "N;SG",
        [
            "NOUN|Number=Sing",
            "PROPN|Number=Sing",
            # CELEX doesn't track gender for EN.
            "PROPN|Gender=Fem|Number=Sing",
            "PROPN|Gender=Masc|Number=Sing",
        ],
    ),
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
    # Bare nouns (UD without Number).
    ("", "N", "NOUN"),
    ("", "N", "PROPN"),
    # Determiners.
    ("", "DET", "DET"),
    ("", "DET;SG", "DET|Number=Sing"),
    ("", "DET;PL", "DET|Number=Plur"),
    # Explicit Definite forms.
    ("", "DET", "DET|Definite=Ind"),
    ("", "DET;SG", "DET|Definite=Ind|Number=Sing"),
    ("", "DET;PL", "DET|Definite=Ind|Number=Plur"),
    ("", "DET;PL", "DET|Number=Plur|Person=3"),
    # Pronouns.
    ("", "PRON", "PRON"),
    # Enumerated singular forms.
    (
        "",
        "PRON;SG",
        [
            "PRON|Number=Sing",
            "PRON|Number=Sing|Person=1",
            "PRON|Number=Sing|Person=2",
            "PRON|Number=Sing|Person=3",
            # Gender distinctions exist in UD/UM.
            "PRON|Gender=Masc|Number=Sing",
            "PRON|Gender=Fem|Number=Sing",
            "PRON|Gender=Neut|Number=Sing",
            "PRON|Gender=Masc|Number=Sing|Person=3",
            "PRON|Gender=Fem|Number=Sing|Person=3",
            "PRON|Gender=Neut|Number=Sing|Person=3",
            # Features sometimes attached in UD.
            "PRON|Definite=Ind|Number=Sing",
            "PRON|Reflex=Yes|Number=Sing",
            "PRON|Poss=Yes|Number=Sing",
            "PRON|Case=Nom|Number=Sing",
            "PRON|Case=Acc|Number=Sing",
        ],
    ),
    (
        "",
        "PRON;PL",
        [
            "PRON|Number=Plur",
            "PRON|Number=Plur|Person=1",
            "PRON|Number=Plur|Person=2",
            "PRON|Number=Plur|Person=3",
            "PRON|Gender=Masc|Number=Plur",
            "PRON|Gender=Fem|Number=Plur",
            "PRON|Gender=Neut|Number=Plur",
            "PRON|Gender=Masc|Number=Plur|Person=2",
            "PRON|Gender=Fem|Number=Plur|Person=1",
            "PRON|Definite=Ind|Number=Plur",
            "PRON|Reflex=Yes|Number=Plur",
            "PRON|Poss=Yes|Number=Plur",
        ],
    ),
    # UD pronouns without Number to coarse PRON.
    ("", "PRON", "PRON|PronType=Rel"),
    ("", "PRON", "PRON|Gender=Neut"),
    ("", "PRON", "PRON|Person=1"),
    ("", "PRON", "PRON|Person=2"),
    ("", "PRON", "PRON|Person=3"),
    ("", "PRON", "PRON|Gender=Masc|Person=2"),
    ("", "PRON", "PRON|Gender=Fem|Person=2"),
    ("", "PRON", "PRON|Poss=Yes"),
    ("", "PRON", "PRON|Reflex=Yes"),
    ("", "PRON", "PRON|Definite=Ind"),
    ("", "PRON", "PRON|Case=Nom"),
    ("", "PRON", "PRON|Case=Acc"),
    # Numerals.
    ("", "NUM", "NUM"),
    ("", "NUM;PL", "NUM|Number=Plur"),
    ("", "NUM;SG", "NUM|Number=Sing"),
    # Closed classes.
    ("", "ADP", "ADP"),
    ("", "SCONJ", "SCONJ"),
    ("", "PART", "PART"),
    ("", "INTJ", "INTJ"),
    ("", "SYM", "SYM"),
    ("", "X", "X"),
    ("", "AUX", "AUX"),
    ("", "CCONJ", "CCONJ"),
    # Auxiliaries with features to coarse AUX.
    ("", "AUX", "AUX|VerbForm=Inf"),
    ("", "AUX", "AUX|VerbForm=Ger"),
    ("", "AUX", "AUX|Tense=Pres"),
    ("", "AUX", "AUX|Tense=Past"),
    ("", "AUX", "AUX|Tense=Past|VerbForm=Part"),
    ("", "PUNCT", "PUNCT"),
    ("", "PART", "PART|Polarity=Neg"),
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
