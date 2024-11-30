"""X-SAMPA conversion functions for English.

Table based on: https://en.wikipedia.org/wiki/X-SAMPA
"""

import pynini
from pynini.lib import rewrite, pynutil

_ipa_xsampa_map = [
    ("a", "a"),
    ("b", "b"),
    ("ɓ", "b<"),
    ("c", "c"),
    ("d", "d"),
    ("ɖ", "d"),
    ("e", "e"),
    ("f", "f"),
    ("ɡ", "g"),
    ("h", "h"),
    ("i", "i"),
    ("j", "j"),
    ("k", "k"),
    ("l", "l"),
    ("ɭ", "l"),
    ("m", "m"),
    ("n", "n"),
    ("ɳ", "n"),
    ("o", "o"),
    ("p", "p"),
    ("ɸ", "p\\"),
    ("q", "q"),
    ("r", "r"),
    ("ɹ", "r\\"),
    ("ɻ", "r\\"),
    ("s", "s"),
    ("ʂ", "s"),
    ("ɕ", "s\\"),
    ("t", "t"),
    ("ʈ", "t"),
    ("u", "u"),
    ("v", "v"),
    ("ʋ", "v\\"),
    ("w", "w"),
    ("x", "x"),
    ("y", "y"),
    ("z", "z"),
    ("ə", "@"),
    ("ɘ", "@\\"),
    ("ɚ", "@`"),
    ("æ", "{"),
    ("ʉ", "}"),
    ("ɨ", "1"),
    ("ø", "2"),
    ("ɜ", "3"),
    ("ɾ", "4"),
    ("ɫ", "5"),
    ("ɐ", "6"),
    ("ɵ", "8"),
    ("œ", "9"),
    ("ʔ", "?"),
    ("ʰ", "h"),
    ("ɑ", "A"),
    ("ç", "C"),
    ("ð", "D"),
    ("ɛ", "E"),
    ("ɪ", "I"),
    ("ɲ", "J"),
    ("ɬ", "K"),
    ("ŋ", "N"),
    ("ɔ", "O"),
    ("ɒ", "Q"),
    ("ʁ", "R"),
    ("ʃ", "S"),
    ("θ", "T"),
    ("ʊ", "U"),
    ("ʌ", "V"),
    ("ʍ", "W"),
    ("χ", "X"),
    ("ʏ", "Y"),
    ("ʒ", "Z"),
    ("t͡s", "ts"),
    ("t͡ʃ", "tS"),
    ("t͡ɕ", "ts\\"),
    ("d͡ʒ", "dZ"),
    ("l̩", "l="),
    ("n̩", "n="),
    ("ɝ", "<?"),
    ("ɪ̯", "I^"),
    ("ɫ̩", "5="),
    ("aː", "a:"),
    ("eː", "e:"),
    ("iː", "i:"),
    ("oː", "o:"),
    ("uː", "u:"),
    ("æː", "{:"),
    ("ɑː", "A:"),
    ("ɔː", "O:"),
    ("ʊː", "U:"),
    ("ʌː", "V:"),
    ("ɛː", "E:"),
    ("ɪː", "I:"),
    ("œː", "9:"),
    ("ɜː", "3:"),
    ("ʊ̯", "U^"),
    ("ɝː", "<? ɝ ?>:"),
    ("m̩", "m_="),
    ("əː", "@:"),
    ("n̩", "n_="),
]

_IPA_TO_XSAMPA = (
    pynutil.join(pynini.string_map(_ipa_xsampa_map), " ").closure().optimize()
)


def ipa_to_xsampa(ipa_string: str) -> str:
    """Maps from IPA to X-SAMPA strings.

    Args:
        ipa_string: IPA string input.

    Returns:
        The correpsonding X-SAMPA string.
    """
    return rewrite.one_top_rewrite(ipa_string, _IPA_TO_XSAMPA)
