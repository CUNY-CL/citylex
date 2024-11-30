import pytest

from citylex import xsampa


@pytest.mark.parametrize(
    "source,expected",
    [
        ("ɑː", "A:"),
        ("t͡ʃ", "tS"),
        ("m̩", "m_="),
        ("ɘ", "@\\"),
        ("ʏ", "Y"),
        ("t͡ʃ ɾ", "tS 4"),
    ],
)
def test_ipa_to_xsampa(source, expected):
    assert xsampa.ipa_to_xsampa(source) == expected
