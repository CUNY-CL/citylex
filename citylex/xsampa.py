"""X-SAMPA conversion functions for English.

Table based on: https://en.wikipedia.org/wiki/X-SAMPA

Unknown IPA symbols are passed through unchanged and a warning is logged,
rather than raising a KeyError. This is intentional: IPA strings from
WikiPron can be noisy, and a partial conversion is more useful than a crash.
"""

import logging
from typing import Optional


# Keys are IPA symbols (or short sequences for affricates and long vowels).
# Values are the corresponding X-SAMPA strings.
#
# Notes on deliberate lossy mappings:
# 
#   ɖ → d  (retroflex stop collapsed to alveolar; English lacks this contrast)
#   ʈ → t  (same rationale)
#   ɭ → l  (retroflex lateral collapsed to alveolar)
#   ɳ → n  (retroflex nasal collapsed to alveolar)
#   ɻ → r\ (retroflex approximant treated as rhotic approximant)
#   ʂ → s  (retroflex sibilant collapsed to alveolar sibilant)
#
# These are defensible for broad English transcription but would lose
# information in a cross-linguistic context.

_IPA_TO_XSAMPA: dict[str, str] = {
    # Plain consonants
    "a": "a",
    "b": "b",
    "ɓ": "b<",
    "c": "c",
    "d": "d",
    "ɖ": "d",   # Retroflex — see note above.
    "e": "e",
    "f": "f",
    "ɡ": "g",
    "h": "h",
    "i": "i",
    "j": "j",
    "k": "k",
    "l": "l",
    "ɭ": "l",   # Retroflex — see note above.
    "m": "m",
    "n": "n",
    "ɳ": "n",   # Retroflex — see note above.
    "o": "o",
    "p": "p",
    "ɸ": "p\\",
    "q": "q",
    "r": "r",
    "ɹ": "r\\",
    "ɻ": "r\\",  # Retroflex — see note above.
    "s": "s",
    "ʂ": "s",   # Retroflex — see note above.
    "ɕ": "s\\",
    "t": "t",
    "ʈ": "t",   # Retroflex — see note above.
    "u": "u",
    "v": "v",
    "ʋ": "v\\",
    "w": "w",
    "x": "x",
    "y": "y",
    "z": "z",
    # Vowels and special symbols.
    "ə": "@",
    "ɘ": "@\\",
    "ɚ": "@`",
    "æ": "{",
    "ʉ": "}",
    "ɨ": "1",
    "ø": "2",
    "ɜ": "3",
    "ɾ": "4",
    "ɫ": "5",
    "ɐ": "6",
    "ɵ": "8",
    "œ": "9",
    "ʔ": "?",
    "ʰ": "h",
    "ɑ": "A",
    "ç": "C",
    "ð": "D",
    "ɛ": "E",
    "ɪ": "I",
    "ɲ": "J",
    "ɬ": "K",
    "ŋ": "N",
    "ɔ": "O",
    "ɒ": "Q",
    "ʁ": "R",
    "ʃ": "S",
    "θ": "T",
    "ʊ": "U",
    "ʌ": "V",
    "ʍ": "W",
    "χ": "X",
    "ʏ": "Y",
    "ʒ": "Z",
    # Affricates (must be matched before their component parts).
    "t͡s":  "ts",
    "t͡ʃ":  "tS",
    "t͡ɕ":  "ts\\",
    "d͡ʒ":  "dZ",
    # Rhotacised and other complex symbols.
    "ɝ":   "<?",
    "ɪ̯":   "I^",
    "ʊ̯":   "U^",
    "ɝː":  "<? ɝ ?>:",   # TODO: verify correct X-SAMPA for long rhotacised mid
    # Long vowels.
    "aː":  "a:",
    "eː":  "e:",
    "iː":  "i:",
    "oː":  "o:",
    "uː":  "u:",
    "æː":  "{:",
    "ɑː":  "A:",
    "ɔː":  "O:",
    "ʊː":  "U:",
    "ʌː":  "V:",
    "ɛː":  "E:",
    "ɪː":  "I:",
    "œː":  "9:",
    "ɜː":  "3:",
    "əː":  "@:",
    # Syllabic consonants.
    "ɫ̩":  "5_=",
    "l̩":  "l_=",
    "m̩":  "m_=",
    "n̩":  "n_=",
}


def ipa_to_xsampa(ipa: str) -> str:
    """Maps a space-separated IPA string to an X-SAMPA string.

    Each whitespace-delimited token is looked up in the conversion table.
    Tokens that are not found are passed through unchanged, with a warning
    emitted.

    Args:
        ipa: a space-separated IPA string, e.g. ``"p ɹ ɪ ˈn ʌ n s ɪ ˌeɪ ʃ ə n"``.

    Returns:
        The corresponding X-SAMPA string, with the same whitespace structure.
    """
    result: list[str] = []
    for symbol in ipa.split():
        mapped: Optional[str] = _IPA_TO_XSAMPA.get(symbol)
        if mapped is None:
            logging.warning("Unknown IPA symbol in X-SAMPA conversion: %r", symbol)
            result.append(symbol)
        else:
            result.append(mapped)
    return " ".join(result)
