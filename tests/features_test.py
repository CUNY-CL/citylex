import pytest

from citylex import features


@pytest.mark.parametrize(
    "from_name,to_name,from_tag,expected_tags",
    [
        # Adverbs.
        ("CELEX", "UniMorph", "B", "ADV"),
        ("CELEX", "UD", "B", "ADV"),
        ("UniMorph", "CELEX", "ADV", "B"),
        ("UniMorph", "UD", "ADV", "ADV"),
        # Some nouns.
        ("CELEX", "UniMorph", "S", "N;SG"),
        ("UniMorph", "CELEX", "N;SG", "S"),
        ("UD", "CELEX", "NOUN|Number=Sing", "S"),
        # Some verbs.
        ("CELEX", "UniMorph", "a1S", "V;PST"),
        ("CELEX", "UniMorph", "aP", "V;PST"),
        ("CELEX", "UniMorph", "pa", "V;V.PTCP;PST"),
        ("CELEX", "UD", "a1S", "VERB|Number=Sing|Person=1|Tense=Past"),
        ("CELEX", "UD", "a2S", "VERB|Number=Sing|Person=2|Tense=Past"),
        ("CELEX", "UD", "a3S", "VERB|Number=Sing|Person=3|Tense=Past"),
        ("CELEX", "UD", "pa", "VERB|Tense=Past|VerbForm=Part"),
        (
            "UniMorph",
            "UD",
            "V;PST",
            [
                "VERB|Number=Sing|Person=1|Tense=Past",
                "VERB|Number=Sing|Person=2|Tense=Past",
                "VERB|Number=Sing|Person=3|Tense=Past",
                "VERB|Number=Plur|Person=1|Tense=Past",
                "VERB|Number=Plur|Person=2|Tense=Past",
                "VERB|Number=Plur|Person=3|Tense=Past",
            ],
        ),
        ("UniMorph", "CELEX", "V;PRS", ["e1S", "e2S", "eP"]),
        ("UniMorph", "CELEX", "V;V.PTCP;PST", "pa"),
        ("UniMorph", "UD", "V;V.PTCP;PST", "VERB|Tense=Past|VerbForm=Part"),
        ("UD", "CELEX", "VERB|Tense=Past|VerbForm=Part", "pa"),
        ("UD", "CELEX", "VERB|Number=Plur|Person=1|Tense=Past", "aP"),
        ("UD", "UniMorph", "VERB|Tense=Past|VerbForm=Part", "V;V.PTCP;PST"),
    ],
)
def test_features(from_name, to_name, from_tag, expected_tags):
    assert features.tag_to_tag(from_name, to_name, from_tag) == expected_tags
