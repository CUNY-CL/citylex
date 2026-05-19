/**
 * xsampa.js — IPA to X-SAMPA conversion for CityLex.
 *
 * Public API:
 *   ipaToXsampa(ipa) → string
 */

// Keys are IPA symbols; values are X-SAMPA strings.
// See xsampa.py for notes on deliberate lossy mappings (retroflex consonants).
const _IPA_TO_XSAMPA = {
  // Plain consonants.
  "a": "a", "b": "b", "ɓ": "b<", "c": "c", "d": "d",
  "ɖ": "d",    // retroflex — see xsampa.py
  "e": "e", "f": "f", "ɡ": "g", "h": "h", "i": "i",
  "j": "j", "k": "k", "l": "l",
  "ɭ": "l",    // retroflex
  "m": "m", "n": "n",
  "ɳ": "n",    // retroflex
  "o": "o", "p": "p", "ɸ": "p\\", "q": "q", "r": "r",
  "ɹ": "r\\", "ɻ": "r\\",  // retroflex
  "s": "s",
  "ʂ": "s",    // retroflex
  "ɕ": "s\\",
  "t": "t",
  "ʈ": "t",    // retroflex
  "u": "u", "v": "v", "ʋ": "v\\", "w": "w", "x": "x", "y": "y", "z": "z",
  // Vowels and special symbols.
  "ə": "@", "ɘ": "@\\", "ɚ": "@`", "æ": "{", "ʉ": "}", "ɨ": "1",
  "ø": "2", "ɜ": "3", "ɾ": "4", "ɫ": "5", "ɐ": "6", "ɵ": "8",
  "œ": "9", "ʔ": "?", "ʰ": "h",
  "ɑ": "A", "ç": "C", "ð": "D", "ɛ": "E", "ɪ": "I", "ɲ": "J",
  "ɬ": "K", "ŋ": "N", "ɔ": "O", "ɒ": "Q", "ʁ": "R", "ʃ": "S",
  "θ": "T", "ʊ": "U", "ʌ": "V", "ʍ": "W", "χ": "X", "ʏ": "Y", "ʒ": "Z",
  // Affricates.
  "t͡s": "ts", "t͡ʃ": "tS", "t͡ɕ": "ts\\", "d͡ʒ": "dZ",
  // Rhotacised and other complex symbols.
  "ɝ": "<?", "ɪ̯": "I^", "ʊ̯": "U^",
  "ɝː": "<? ɝ ?>:",  // TODO: verify correct X-SAMPA for long rhotacised mid.
  // Long vowels.
  "aː": "a:", "eː": "e:", "iː": "i:", "oː": "o:", "uː": "u:",
  "æː": "{:", "ɑː": "A:", "ɔː": "O:", "ʊː": "U:", "ʌː": "V:",
  "ɛː": "E:", "ɪː": "I:", "œː": "9:", "ɜː": "3:", "əː": "@:",
  // Syllabic consonants.
  "ɫ̩": "5_=", "l̩": "l_=", "m̩": "m_=", "n̩": "n_=",
};

/**
 * Maps a space-separated IPA string to an X-SAMPA string.
 * Unknown symbols are passed through unchanged (matching xsampa.py behaviour).
 *
 * @param {string} ipa - Space-separated IPA string.
 * @returns {string}
 */
export function ipaToXsampa(ipa) {
  return ipa.split(" ").map(symbol => {
    const mapped = _IPA_TO_XSAMPA[symbol];
    if (mapped === undefined) {
      console.warn(`Unknown IPA symbol in X-SAMPA conversion: ${JSON.stringify(symbol)}`);
      return symbol;
    }
    return mapped;
  }).join(" ");
}
