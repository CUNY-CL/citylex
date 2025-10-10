"""Converts between different feature formats.

* For CELEX, see the CELEX English manual (ch. 3).
* For UniMorph, see https://unimorph.github.io/doc/unimorph-schema.pdf.
* For Universal Dependencies, see https://universaldependencies.org/u/feat/.
"""

from typing import Dict, List, Union


# Format is:
# [source tag][from_tag][destination_tag] = to_tag or [to_tag, to_tag, ...]
# tag_to_tag uses a different order, but this is much easier to define.
_map_dict: Dict[str, Dict[str, Dict[str, Union[str, List[str]]]]] = {
    "CELEX": {
        # Adverb.
        "B": {"UniMorph": "ADV", "UD": "ADV"},
        # Adjective.
        "b": {"UniMorph": "ADJ", "UD": "ADJ"},
        "c": {"UniMorph": "ADJ;CMPR", "UD": "ADJ|Degree=Cmp"},
        "s": {"UniMorph": "ADJ;SPRL", "UD": "ADJ|Degree=Sup"},
        # Noun.
        "S": {"UniMorph": "N;SG"},  # Can't say whether it's proper in UD.
        "P": {"UniMorph": "N;PL"},  # Ditto.
        # Verb.
        "i": {"UniMorph": "V;NFIN;IMP+SBJV", "UD": "VERB|VerbForm=Inf"},
        "pe": {
            "UniMorph": "V;V.PTCP;PRS",
            "UD": "VERB|Tense=Pres|VerbForm=Part",
        },
        "e1S": {
            "UniMorph": "V;PRS",
            "UD": "VERB|Number=Sing|Person=1|Tense=Pres",
        },
        "e2S": {
            "UniMorph": "V;PRS",
            "UD": "VERB|Number=Sing|Person=2|Tense=Pres",
        },
        "e3S": {
            "UniMorph": "V;PRS;3;SG",
            "UD": "VERB|Number=Sing|Person=3|Tense=Pres",
        },
        "eP": {
            "UniMorph": "V;PRS",
            "UD": [
                "VERB|Number=Plur|Person=1|Tense=Pres",
                "VERB|Number=Plur|Person=2|Tense=Pres",
                "VERB|Number=Plur|Person=3|Tense=Pres",
            ],
        },
        "a1S": {
            "UniMorph": "V;PST",
            "UD": "VERB|Number=Sing|Person=1|Tense=Past",
        },
        "a2S": {
            "UniMorph": "V;PST",
            "UD": "VERB|Number=Sing|Person=2|Tense=Past",
        },
        "a3S": {
            "UniMorph": "V;PST;3;SG",
            "UD": "VERB|Number=Sing|Person=3|Tense=Past",
        },
        "aP": {
            "UniMorph": "V;PST",
            "UD": [
                "VERB|Number=Plur|Person=1|Tense=Past",
                "VERB|Number=Plur|Person=2|Tense=Past",
                "VERB|Number=Plur|Person=3|Tense=Past",
            ],
        },
        "pa": {
            "UniMorph": "V;V.PTCP;PST",
            "UD": "VERB|Tense=Past|VerbForm=Part",
        },
    },
    "UniMorph": {
        # Adverb.
        "ADV": {"CELEX": "B", "UD": "ADV"},
        # No comparative adverbs in CELEX.
        "ADV;CMPR": {"UD": "ADV|Degree=Cmp"},
        # No superlative adverbs in CELEX.
        "ADV;SPLR": {"UD": "ADV|Degree=Sup"},
        # Adjective.
        "ADJ": {"CELEX": "b", "UD": "ADJ"},
        "ADJ;CMPR": {"CELEX": "c", "UD": "ADJ|Degree=Cmp"},
        "ADJ;SPLR": {"CELEX": "s", "UD": "ADJ|Degree=Sup"},
        # Noun.
        "N;SG": {"CELEX": "S"},  # Can't say whether it's proper in UD.
        "N;PL": {"CELEX": "P"},  # Ditto.
        # Verb.
        "V;NFIN;IMP+SBJV": {
            "CELEX": "i",
            "UD": ["VERB|Mood=Imp", "VERB|VerbForm=Inf"],
        },
        "V;V.PTCP;PRS": {"CELEX": "ae", "UD": "VERB|Tense=Pres|VerbForm=Part"},
        "V;GER": {"UD": "VERB|VerbForm=Ger"},  # No gerunds in CELEX.
        "V;PRS": {
            "CELEX": ["e1S", "e2S", "eP"],
            "UD": [
                "VERB|Number=Sing|Person=1|Tense=Pres",
                "VERB|Number=Sing|Person=2|Tense=Pres",
                "VERB|Number=Plur|Person=1|Tense=Pres",
                "VERB|Number=Plur|Person=2|Tense=Pres",
                "VERB|Number=Plur|Person=3|Tense=Pres",
            ],
        },
        "V;PRS;3;SG": {
            "CELEX": "e3S",
            "UD": "VERB|Number=Sing|Person=3|Tense=Pres",
        },
        # No present subjunctive in CELEX.
        "V;SBJV;PRS": {"UD": "VERB|Mood=Sub|Tense=Pres"},
        "V;PST": {
            "CELEX": ["a1S", "a2S", "a3S", "aP"],
            "UD": [
                "VERB|Number=Sing|Person=1|Tense=Past",
                "VERB|Number=Sing|Person=2|Tense=Past",
                "VERB|Number=Sing|Person=3|Tense=Past",
                "VERB|Number=Plur|Person=1|Tense=Past",
                "VERB|Number=Plur|Person=2|Tense=Past",
                "VERB|Number=Plur|Person=3|Tense=Past",
            ],
        },
        "V;V.PTCP;PST": {"CELEX": "pa", "UD": "VERB|Tense=Past|VerbForm=Part"},
    },
    "UD": {
        # Adverb.
        "ADV": {"CELEX": "B", "UniMorph": "ADV"},
        # No comparative adverbs in CELEX.
        "ADV|Degree=Cmp": {"UniMorph": "ADV;CMPR"},
        # No superlative adverbs in CELEX.
        "ADV|Degree=Sup": {"UniMorph": "ADV;SPRL"},
        # Adjective.
        "ADJ": {"CELEX": "b", "UniMorph": "ADJ"},
        "ADJ|Degree=Cmp": {"CELEX": "c", "UniMorph": "ADJ;CMPR"},
        "ADJ|Degree=Sup": {"CELEX": "s", "UniMorph": "ADJ;SPRL"},
        # Noun.
        "NOUN|Number=Sing": {"CELEX": "S", "UniMorph": "N;SG"},
        "NOUN|Number=Plur": {"CELEX": "P", "UniMorph": "N;PL"},
        "PROPN|Gender=Fem|Number=Sing": {"CELEX": "S", "UniMorph": "N;SG"},
        "PROPN|Gender=Masc|Number=Sing": {"CELEX": "S", "UniMorph": "N;SG"},
        "PROPN|Number=Plur": {"CELEX": "P", "UniMorph": "N;PL"},
        "PROPN|Gender=Fem|Number=Plur": {"CELEX": "P", "UniMorph": "N;PL"},
        "PROPN|Gender=Masc|Number=Plur": {"CELEX": "P", "UniMorph": "N;PL"},
        # Verb.
        "VERB|VerbForm=Inf": {"CELEX": "i", "UniMorph": "V;NFIN;IMP+SBJV"},
        # No imperative in CELEX.
        "VERB|Mood=Imp": {"UniMorph": "V;NFIN;IMP+SBJV"},
        "VERB|Tense=Pres|VerbForm=Part": {
            "CELEX": "pe",
            "UniMorph": "V;V.PTCP;PRS",
        },
        "VERB|VerbForm=Ger": {"UniMorph": "V;GER"},  # No gerunds in CELEX.
        "VERB|Number=Sing|Person=1|Tense=Pres": {
            "CELEX": "e1S",
            "UniMorph": "V;PRS",
        },
        "VERB|Number=Sing|Person=2|Tense=Pres": {
            "CELEX": "e2S",
            "UniMorph": "V;PRS",
        },
        "VERB|Number=Sing|Person=3|Tense=Pres": {
            "CELEX": "e3S",
            "UniMorph": "V;PRS;3;SG",
        },
        "VERB|Number=Plur|Person=1|Tense=Pres": {
            "CELEX": "eP",
            "UniMorph": "V;PRS",
        },
        "VERB|Number=Plur|Person=2|Tense=Pres": {
            "CELEX": "eP",
            "UniMorph": "V;PRS",
        },
        "VERB|Number=Plur|Person=3|Tense=Pres": {
            "CELEX": "eP",
            "UniMorph": "V;PRS",
        },
        # No present subjunctive in CELEX.
        "VERB|Mood=Sub|Tense=Pres": {"UniMorph": "V;SBJV;PRS"},
        "VERB|Number=Sing|Person=1|Tense=Past": {
            "CELEX": "a1S",
            "UniMorph": "V;PST",
        },
        "VERB|Number=Sing|Person=2|Tense=Past": {
            "CELEX": "a2S",
            "UniMorph": "V;PST",
        },
        "VERB|Number=Sing|Person=3|Tense=Past": {
            "CELEX": "a3S",
            "UniMorph": "V;PST",
        },
        "VERB|Number=Plur|Person=1|Tense=Past": {
            "CELEX": "aP",
            "UniMorph": "V;PST",
        },
        "VERB|Number=Plur|Person=2|Tense=Past": {
            "CELEX": "aP",
            "UniMorph": "V;PST",
        },
        "VERB|Number=Plur|Person=3|Tense=Past": {
            "CELEX": "aP",
            "UniMorph": "V;PST",
        },
        "VERB|Tense=Past|VerbForm=Part": {
            "CELEX": "pa",
            "UniMorph": "V;V.PTCP;PST",
        },
    },
}


def tag_to_tag(
    from_name: str, to_name: str, tag: str
) -> Union[str, List[str], None]:
    """Maps a morphological tag in one feature system to another.

    Args:
        from_name: the source system for the morphological tag (one of:
            "CELEX", "UniMorph", "UD").
        to_name: the target for the morphological tag (one of:
            "CELEX", "UniMorph", "UD").
        tag: the source system tag to look up.

    Returns:
        Tag, list of tags, or None.
    """
    try:
        return _map_dict[from_name][tag][to_name]
    except KeyError:
        return None
