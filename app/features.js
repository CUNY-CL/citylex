/**
 * features.js — morphological tag conversion for CityLex.
 *
 * The _CANONICAL table is the single source of truth; do not add mappings
 * anywhere else.
 *
 * Public API:
 *   tagToTag(fromName, toName, tag) → string | string[] | null
 */

// ---------------------------------------------------------------------------
// Canonical mapping table
// Format: [fromFormat, fromTag, toFormat, toTag]
// ---------------------------------------------------------------------------

const _CANONICAL = [
  // Adverb — no comparative/superlative adverb codes in CELEX.
  ["CELEX",    "B",              "UniMorph", "ADV"],
  ["CELEX",    "B",              "UD",       "ADV"],
  ["UniMorph", "ADV",            "CELEX",    "B"],
  ["UniMorph", "ADV",            "UD",       "ADV"],
  ["UniMorph", "ADV;CMPR",       "UD",       "ADV|Degree=Cmp"],
  ["UniMorph", "ADV;SPRL",       "UD",       "ADV|Degree=Sup"],
  ["UD",       "ADV",            "CELEX",    "B"],
  ["UD",       "ADV",            "UniMorph", "ADV"],
  ["UD",       "ADV|Degree=Cmp", "UniMorph", "ADV;CMPR"],
  ["UD",       "ADV|Degree=Sup", "UniMorph", "ADV;SPRL"],
  // Adjective.
  ["CELEX",    "b",              "UniMorph", "ADJ"],
  ["CELEX",    "b",              "UD",       "ADJ"],
  ["CELEX",    "c",              "UniMorph", "ADJ;CMPR"],
  ["CELEX",    "c",              "UD",       "ADJ|Degree=Cmp"],
  ["CELEX",    "s",              "UniMorph", "ADJ;SPRL"],
  ["CELEX",    "s",              "UD",       "ADJ|Degree=Sup"],
  ["UniMorph", "ADJ",            "CELEX",    "b"],
  ["UniMorph", "ADJ",            "UD",       "ADJ"],
  ["UniMorph", "ADJ;CMPR",       "CELEX",    "c"],
  ["UniMorph", "ADJ;CMPR",       "UD",       "ADJ|Degree=Cmp"],
  ["UniMorph", "ADJ;SPRL",       "CELEX",    "s"],
  ["UniMorph", "ADJ;SPRL",       "UD",       "ADJ|Degree=Sup"],
  ["UD",       "ADJ",            "CELEX",    "b"],
  ["UD",       "ADJ",            "UniMorph", "ADJ"],
  ["UD",       "ADJ|Degree=Cmp", "CELEX",    "c"],
  ["UD",       "ADJ|Degree=Cmp", "UniMorph", "ADJ;CMPR"],
  ["UD",       "ADJ|Degree=Sup", "CELEX",    "s"],
  ["UD",       "ADJ|Degree=Sup", "UniMorph", "ADJ;SPRL"],
  // Noun — CELEX S/P → UD recovers only NOUN|Number=* (proper-noun info lost).
  ["CELEX",    "S",                             "UniMorph", "N;SG"],
  ["CELEX",    "S",                             "UD",       "NOUN|Number=Sing"],
  ["CELEX",    "P",                             "UniMorph", "N;PL"],
  ["CELEX",    "P",                             "UD",       "NOUN|Number=Plur"],
  ["UniMorph", "N;SG",                          "CELEX",    "S"],
  ["UniMorph", "N;SG",                          "UD",       "NOUN|Number=Sing"],
  ["UniMorph", "N;PL",                          "CELEX",    "P"],
  ["UniMorph", "N;PL",                          "UD",       "NOUN|Number=Plur"],
  ["UD",       "NOUN|Number=Sing",              "CELEX",    "S"],
  ["UD",       "NOUN|Number=Sing",              "UniMorph", "N;SG"],
  ["UD",       "NOUN|Number=Plur",              "CELEX",    "P"],
  ["UD",       "NOUN|Number=Plur",              "UniMorph", "N;PL"],
  ["UD",       "PROPN|Number=Sing",             "CELEX",    "S"],
  ["UD",       "PROPN|Number=Sing",             "UniMorph", "N;SG"],
  ["UD",       "PROPN|Number=Plur",             "CELEX",    "P"],
  ["UD",       "PROPN|Number=Plur",             "UniMorph", "N;PL"],
  ["UD",       "PROPN|Gender=Fem|Number=Sing",  "CELEX",    "S"],
  ["UD",       "PROPN|Gender=Fem|Number=Sing",  "UniMorph", "N;SG"],
  ["UD",       "PROPN|Gender=Masc|Number=Sing", "CELEX",    "S"],
  ["UD",       "PROPN|Gender=Masc|Number=Sing", "UniMorph", "N;SG"],
  ["UD",       "PROPN|Gender=Fem|Number=Plur",  "CELEX",    "P"],
  ["UD",       "PROPN|Gender=Fem|Number=Plur",  "UniMorph", "N;PL"],
  ["UD",       "PROPN|Gender=Masc|Number=Plur", "CELEX",    "P"],
  ["UD",       "PROPN|Gender=Masc|Number=Plur", "UniMorph", "N;PL"],
  // Verb — infinitive/imperative/present subjunctive.
  // CELEX conflates all three as "i" (bare stem in English).
  ["CELEX",    "i",                       "UniMorph", "V;NFIN"],
  ["CELEX",    "i",                       "UniMorph", "V;IMP"],
  ["CELEX",    "i",                       "UniMorph", "V;SBJV;PRS"],
  ["CELEX",    "i",                       "UD",       "VERB|VerbForm=Inf"],
  ["CELEX",    "i",                       "UD",       "VERB|Mood=Imp"],
  ["CELEX",    "i",                       "UD",       "VERB|Mood=Sub|Tense=Pres"],
  ["UniMorph", "V;NFIN",                  "CELEX",    "i"],
  ["UniMorph", "V;NFIN",                  "UD",       "VERB|VerbForm=Inf"],
  ["UniMorph", "V;IMP",                   "CELEX",    "i"],
  ["UniMorph", "V;IMP",                   "UD",       "VERB|Mood=Imp"],
  ["UniMorph", "V;SBJV;PRS",              "CELEX",    "i"],
  ["UniMorph", "V;SBJV;PRS",              "UD",       "VERB|Mood=Sub|Tense=Pres"],
  ["UD",       "VERB|VerbForm=Inf",        "CELEX",    "i"],
  ["UD",       "VERB|VerbForm=Inf",        "UniMorph", "V;NFIN"],
  ["UD",       "VERB|Mood=Imp",            "CELEX",    "i"],
  ["UD",       "VERB|Mood=Imp",            "UniMorph", "V;IMP"],
  ["UD",       "VERB|Mood=Sub|Tense=Pres", "CELEX",   "i"],
  ["UD",       "VERB|Mood=Sub|Tense=Pres", "UniMorph", "V;SBJV;PRS"],
  // Verb — gerund (no CELEX target).
  ["UniMorph", "V;GER",             "UD",       "VERB|VerbForm=Ger"],
  ["UD",       "VERB|VerbForm=Ger", "UniMorph", "V;GER"],
  // Verb — present participle.
  ["CELEX",    "pe",                           "UniMorph", "V;V.PTCP;PRS"],
  ["CELEX",    "pe",                           "UD",       "VERB|Tense=Pres|VerbForm=Part"],
  ["UniMorph", "V;V.PTCP;PRS",                "CELEX",    "pe"],
  ["UniMorph", "V;V.PTCP;PRS",                "UD",       "VERB|Tense=Pres|VerbForm=Part"],
  ["UD",       "VERB|Tense=Pres|VerbForm=Part", "CELEX",  "pe"],
  ["UD",       "VERB|Tense=Pres|VerbForm=Part", "UniMorph", "V;V.PTCP;PRS"],
  // Verb — present tense (non-3sg).
  ["CELEX",    "e1S",  "UniMorph", "V;PRS"],
  ["CELEX",    "e1S",  "UD",       "VERB|Number=Sing|Person=1|Tense=Pres"],
  ["CELEX",    "e2S",  "UniMorph", "V;PRS"],
  ["CELEX",    "e2S",  "UD",       "VERB|Number=Sing|Person=2|Tense=Pres"],
  ["CELEX",    "eP",   "UniMorph", "V;PRS"],
  ["CELEX",    "eP",   "UD",       "VERB|Number=Plur|Person=1|Tense=Pres"],
  ["CELEX",    "eP",   "UD",       "VERB|Number=Plur|Person=2|Tense=Pres"],
  ["CELEX",    "eP",   "UD",       "VERB|Number=Plur|Person=3|Tense=Pres"],
  ["UniMorph", "V;PRS", "CELEX",   "e1S"],
  ["UniMorph", "V;PRS", "CELEX",   "e2S"],
  ["UniMorph", "V;PRS", "CELEX",   "eP"],
  ["UniMorph", "V;PRS", "UD",      "VERB|Number=Sing|Person=1|Tense=Pres"],
  ["UniMorph", "V;PRS", "UD",      "VERB|Number=Sing|Person=2|Tense=Pres"],
  ["UniMorph", "V;PRS", "UD",      "VERB|Number=Plur|Person=1|Tense=Pres"],
  ["UniMorph", "V;PRS", "UD",      "VERB|Number=Plur|Person=2|Tense=Pres"],
  ["UniMorph", "V;PRS", "UD",      "VERB|Number=Plur|Person=3|Tense=Pres"],
  ["UD", "VERB|Number=Sing|Person=1|Tense=Pres", "CELEX",    "e1S"],
  ["UD", "VERB|Number=Sing|Person=1|Tense=Pres", "UniMorph", "V;PRS"],
  ["UD", "VERB|Number=Sing|Person=2|Tense=Pres", "CELEX",    "e2S"],
  ["UD", "VERB|Number=Sing|Person=2|Tense=Pres", "UniMorph", "V;PRS"],
  ["UD", "VERB|Number=Plur|Person=1|Tense=Pres", "CELEX",    "eP"],
  ["UD", "VERB|Number=Plur|Person=1|Tense=Pres", "UniMorph", "V;PRS"],
  ["UD", "VERB|Number=Plur|Person=2|Tense=Pres", "CELEX",    "eP"],
  ["UD", "VERB|Number=Plur|Person=2|Tense=Pres", "UniMorph", "V;PRS"],
  ["UD", "VERB|Number=Plur|Person=3|Tense=Pres", "CELEX",    "eP"],
  ["UD", "VERB|Number=Plur|Person=3|Tense=Pres", "UniMorph", "V;PRS"],
  // Verb — present tense 3sg.
  ["CELEX",    "e3S",                               "UniMorph", "V;PRS;3;SG"],
  ["CELEX",    "e3S",                               "UD",       "VERB|Number=Sing|Person=3|Tense=Pres"],
  ["UniMorph", "V;PRS;3;SG",                        "CELEX",    "e3S"],
  ["UniMorph", "V;PRS;3;SG",                        "UD",       "VERB|Number=Sing|Person=3|Tense=Pres"],
  ["UD",       "VERB|Number=Sing|Person=3|Tense=Pres", "CELEX",    "e3S"],
  ["UD",       "VERB|Number=Sing|Person=3|Tense=Pres", "UniMorph", "V;PRS;3;SG"],
  // Verb — past tense.
  ["CELEX",    "a1S",  "UniMorph", "V;PST"],
  ["CELEX",    "a1S",  "UD",       "VERB|Number=Sing|Person=1|Tense=Past"],
  ["CELEX",    "a2S",  "UniMorph", "V;PST"],
  ["CELEX",    "a2S",  "UD",       "VERB|Number=Sing|Person=2|Tense=Past"],
  ["CELEX",    "a3S",  "UniMorph", "V;PST"],
  ["CELEX",    "a3S",  "UD",       "VERB|Number=Sing|Person=3|Tense=Past"],
  ["CELEX",    "aP",   "UniMorph", "V;PST"],
  ["CELEX",    "aP",   "UD",       "VERB|Number=Plur|Person=1|Tense=Past"],
  ["CELEX",    "aP",   "UD",       "VERB|Number=Plur|Person=2|Tense=Past"],
  ["CELEX",    "aP",   "UD",       "VERB|Number=Plur|Person=3|Tense=Past"],
  ["UniMorph", "V;PST", "CELEX",   "a1S"],
  ["UniMorph", "V;PST", "CELEX",   "a2S"],
  ["UniMorph", "V;PST", "CELEX",   "a3S"],
  ["UniMorph", "V;PST", "CELEX",   "aP"],
  ["UniMorph", "V;PST", "UD",      "VERB|Number=Sing|Person=1|Tense=Past"],
  ["UniMorph", "V;PST", "UD",      "VERB|Number=Sing|Person=2|Tense=Past"],
  ["UniMorph", "V;PST", "UD",      "VERB|Number=Sing|Person=3|Tense=Past"],
  ["UniMorph", "V;PST", "UD",      "VERB|Number=Plur|Person=1|Tense=Past"],
  ["UniMorph", "V;PST", "UD",      "VERB|Number=Plur|Person=2|Tense=Past"],
  ["UniMorph", "V;PST", "UD",      "VERB|Number=Plur|Person=3|Tense=Past"],
  ["UD", "VERB|Number=Sing|Person=1|Tense=Past", "CELEX",    "a1S"],
  ["UD", "VERB|Number=Sing|Person=1|Tense=Past", "UniMorph", "V;PST"],
  ["UD", "VERB|Number=Sing|Person=2|Tense=Past", "CELEX",    "a2S"],
  ["UD", "VERB|Number=Sing|Person=2|Tense=Past", "UniMorph", "V;PST"],
  ["UD", "VERB|Number=Sing|Person=3|Tense=Past", "CELEX",    "a3S"],
  ["UD", "VERB|Number=Sing|Person=3|Tense=Past", "UniMorph", "V;PST"],
  ["UD", "VERB|Number=Plur|Person=1|Tense=Past", "CELEX",    "aP"],
  ["UD", "VERB|Number=Plur|Person=1|Tense=Past", "UniMorph", "V;PST"],
  ["UD", "VERB|Number=Plur|Person=2|Tense=Past", "CELEX",    "aP"],
  ["UD", "VERB|Number=Plur|Person=2|Tense=Past", "UniMorph", "V;PST"],
  ["UD", "VERB|Number=Plur|Person=3|Tense=Past", "CELEX",    "aP"],
  ["UD", "VERB|Number=Plur|Person=3|Tense=Past", "UniMorph", "V;PST"],
  // Verb — past participle.
  ["CELEX",    "pa",                            "UniMorph", "V;V.PTCP;PST"],
  ["CELEX",    "pa",                            "UD",       "VERB|Tense=Past|VerbForm=Part"],
  ["UniMorph", "V;V.PTCP;PST",                 "CELEX",    "pa"],
  ["UniMorph", "V;V.PTCP;PST",                 "UD",       "VERB|Tense=Past|VerbForm=Part"],
  ["UD",       "VERB|Tense=Past|VerbForm=Part", "CELEX",   "pa"],
  ["UD",       "VERB|Tense=Past|VerbForm=Part", "UniMorph", "V;V.PTCP;PST"],
];

// ---------------------------------------------------------------------------
// Build the lookup map from _CANONICAL (mirrors the Python build step exactly)
// ---------------------------------------------------------------------------

// _map: Map<fromFormat, Map<fromTag, Map<toFormat, string[]>>>
const _map = new Map();

for (const [srcFmt, srcTag, dstFmt, dstTag] of _CANONICAL) {
  if (!_map.has(srcFmt)) _map.set(srcFmt, new Map());
  const byTag = _map.get(srcFmt);
  if (!byTag.has(srcTag)) byTag.set(srcTag, new Map());
  const byDst = byTag.get(srcTag);
  if (!byDst.has(dstFmt)) byDst.set(dstFmt, []);
  const arr = byDst.get(dstFmt);
  if (!arr.includes(dstTag)) arr.push(dstTag);
}

// Flatten: single-element arrays become plain strings, multi stay as arrays.
// Mirrors Python: _dst_list[0] if len(_dst_list) == 1 else _dst_list
const _mapDict = new Map();
for (const [srcFmt, byTag] of _map) {
  _mapDict.set(srcFmt, new Map());
  for (const [srcTag, byDst] of byTag) {
    _mapDict.get(srcFmt).set(srcTag, new Map());
    for (const [dstFmt, arr] of byDst) {
      _mapDict.get(srcFmt).get(srcTag).set(
        dstFmt,
        arr.length === 1 ? arr[0] : arr,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Maps a morphological tag in one feature system to another.
 *
 * @param {string} fromName - Source system: "CELEX", "UniMorph", or "UD".
 * @param {string} toName   - Target system: "CELEX", "UniMorph", or "UD".
 * @param {string} tag      - Tag in the source system.
 * @returns {string | string[] | null}
 */
export function tagToTag(fromName, toName, tag) {
  try {
    return _mapDict.get(fromName)?.get(tag)?.get(toName) ?? null;
  } catch {
    return null;
  }
}
