import pytest

from citylex import features


@pytest.mark.parametrize(
    "from_name,to_name,from_tag,expected_tag",
    [
        # Adverbs.
        ("CELEX", "UniMorph", "B", "ADV"),
        ("CELEX", "UD", "B", "ADV|_"),
        ("UniMorph", "CELEX", "ADV", "B"),
        ("UniMorph", "UD", "ADV", "ADV|_"),
        ("UD", "CELEX", "ADV|_", "B"),
        ("UD", "UniMorph", "ADV|_", "ADV"),
        # Noun singulars; these are a bit more complicated.
        ("CELEX", "UniMorph", "S", "N;SG"),
        ("CELEX", "UD", "S", "NOUN|Number=Sing"),
        ("UniMorph", "CELEX", "N;SG", "S"),
        ("UniMorph", "UD", "N;SG", "NOUN|Number=Sing"),
        ("UD", "CELEX", "NOUN|Number=Sing", "S"),
        ("UD", "CELEX", "PROPN|Number=Sing", "S"),
        ("UD", "CELEX", "PROPN|Gender=Fem|Number=Sing", "S"),
        ("UD", "CELEX", "PROPN|Gender=Masc|Number=Sing", "S"),
        ("UD", "UniMorph", "NOUN|Number=Sing", "N;SG"),
        ("UD", "UniMorph", "PROPN|Number=Sing", "N;SG"),
        ("UD", "UniMorph", "PROPN|Gender=Fem|Number=Sing", "N;SG"),
        ("UD", "UniMorph", "PROPN|Gender=Masc|Number=Sing", "N;SG"),
    ],
)
def test_features(from_name, to_name, from_tag, expected_tag):
    assert features.tag_to_tag(from_name, to_name, from_tag) == expected_tag
