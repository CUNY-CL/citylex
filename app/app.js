/**
 * app.js — CityLex client-side query engine.
 *
 * Replaces the Flask backend entirely. All SQL queries run in the browser
 * via sql.js-httpvfs (lazy range-request SQLite). Output is assembled in
 * memory and downloaded via a Blob URL.
 *
 * Corresponds to app.py; the query logic is a direct port.
 * Features and X-SAMPA conversion are imported from features.js / xsampa.js.
 */

import sqlHttpVfs from "https://esm.sh/sql.js-httpvfs@0.8.12";
const { createDbWorker } = sqlHttpVfs;

import { tagToTag } from "./features.min.js";
import { ipaToXsampa } from "./xsampa.min.js";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DB_CONFIG = {
  from: "jsonconfig",
  // Construct a fully qualified absolute URL to prevent blob-base resolution failures inside the worker.
  configUrl: new URL("./citylex.db.json", window.location.href).href,
};

// Proxy the CDN worker via a local Blob to satisfy the Same-Origin Policy.
const WORKER_CDN_URL = "https://cdn.jsdelivr.net/npm/sql.js-httpvfs@0.8.12/dist/sqlite.worker.js";
const WORKER_URL = URL.createObjectURL(
  new Blob([`importScripts("${WORKER_CDN_URL}");`], { type: "application/javascript" })
);

// Target the correct distribution filename for the WASM asset.
const WASM_URL    = "https://cdn.jsdelivr.net/npm/sql.js-httpvfs@0.8.12/dist/sql-wasm.wasm";
const FREQ_PRECISION = 6;

// ---------------------------------------------------------------------------
// DB worker (initialised once on first use)
// ---------------------------------------------------------------------------

let _workerPromise = null;

function getWorker() {
  if (!_workerPromise) {
    // Pass DB_CONFIG inside an array to fulfill the library's expected signature
    _workerPromise = createDbWorker([DB_CONFIG], WORKER_URL, WASM_URL);
  }
  return _workerPromise;
}

// ---------------------------------------------------------------------------
// Math helpers
// ---------------------------------------------------------------------------

function negLogProb(rawFreq, total) {
  if (rawFreq > 0) return -Math.log10(rawFreq / total);
  return Infinity;
}

function zipfScale(count, total) {
  if (count > 0) return Math.log10(count) - Math.log10(total) + 9.0;
  return 0.0;
}

function round(value, precision) {
  const factor = Math.pow(10, precision);
  return Math.round(value * factor) / factor;
}

// ---------------------------------------------------------------------------
// Tag flattening.
// ---------------------------------------------------------------------------

function flatten(maybeList) {
  if (Array.isArray(maybeList)) return maybeList.join(",");
  return maybeList;
}

// ---------------------------------------------------------------------------
// TSV column ordering.
// ---------------------------------------------------------------------------

function buildTsvColumns(selectedFields) {
  const f = new Set(selectedFields);
  const cols = ["wordform", "source"];
  if (["subtlexUS_raw_frequency","subtlexUK_raw_frequency","celexfreq_raw_frequency"].some(x => f.has(x)))
    cols.push("raw_frequency");
  if (["subtlexUS_freq_per_million","subtlexUK_freq_per_million","celexfreq_freq_per_million"].some(x => f.has(x)))
    cols.push("freq_per_million");
  if (["subtlexUK_logprob","subtlexUS_logprob","celexfreq_logprob"].some(x => f.has(x)))
    cols.push("-logprob");
  if (["subtlexUK_zipf","subtlexUS_zipf","celexfreq_zipf"].some(x => f.has(x)))
    cols.push("zipf");
  if (["wikipronUS_IPA","wikipronUK_IPA"].some(x => f.has(x)))
    cols.push("IPA_pronunciation");
  if (["wikipronUS_XSAMPA","wikipronUK_XSAMPA"].some(x => f.has(x)))
    cols.push("XSAMPA_pronunciation");
  if (f.has("celex_DISC"))
    cols.push("DISC_pronunciation");
  if (["udlex_CELEXtags","um_CELEXtags","celex_CELEXtags"].some(x => f.has(x)))
    cols.push("celex_tags");
  if (["udlex_UDtags","um_UDtags","celex_UDtags"].some(x => f.has(x)))
    cols.push("ud_tags");
  if (["udlex_UMtags","um_UMtags","celex_UMtags"].some(x => f.has(x)))
    cols.push("um_tags");
  if (f.has("elp_segmentation"))
    cols.push("segmentation");
  if (f.has("elp_nmorph"))
    cols.push("nmorph");
  return cols;
}

// ---------------------------------------------------------------------------
// TSV serialisation — mirrors csv.DictWriter with tab delimiter
// ---------------------------------------------------------------------------

function tsvEscapeCell(value) {
  // TSV: tab and newline in values need quoting; we follow RFC 4180 adapted
  // for tabs: wrap in double-quotes and escape internal double-quotes.
  const s = value === null || value === undefined ? "" : String(value);
  if (s.includes("\t") || s.includes("\n") || s.includes('"')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function buildTsvRow(columns, rowObj) {
  return columns.map(col => tsvEscapeCell(rowObj[col] ?? "")).join("\t") + "\n";
}

// ---------------------------------------------------------------------------
// Query helpers
// ---------------------------------------------------------------------------

async function queryAll(worker, sql, params = []) {
  const results = await worker.db.query(sql, params);
  return results;
}

async function fetchTotal(worker, source) {
  const rows = await queryAll(
    worker,
    "SELECT SUM(raw_frequency) AS t FROM frequency WHERE source = ? ORDER BY wordform ASC",
    [source],
  );
  return rows.length > 0 && rows[0].t != null ? Number(rows[0].t) : 0;
}

// ---------------------------------------------------------------------------
// TSV generation
// ---------------------------------------------------------------------------

/**
 * Generates all TSV rows for the selected sources/fields.
 * Returns the complete TSV string (header + data rows).
 *
 * Unlike the Python streaming generators, we accumulate here: the browser
 * can't stream to a download until the whole Blob is ready. For a 60 MB
 * DB with typical field selections the result set is well within memory.
 */
async function generateTsv(worker, selectedSources, selectedFields) {
  const columns = buildTsvColumns(selectedFields);
  const f = new Set(selectedFields);
  const s = new Set(selectedSources);
  const rows = [];

  // --- CELEX (freq + feat + pron share wordforms; aggregate per wordform) ---
  if (s.has("celexfreq") || s.has("celexfeat") || s.has("celexpron")) {
    const celexData = new Map(); // wordform → entry object

    if (s.has("celexfreq")) {
      const total = await fetchTotal(worker, "CELEX");
      const freqRows = await queryAll(
        worker,
        "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = 'CELEX' ORDER BY wordform ASC",
      );
      for (const { wordform, raw_frequency, freq_per_million } of freqRows) {
        const entry = celexData.get(wordform) || { source: "CELEX" };
        if (f.has("celexfreq_raw_frequency"))   entry.raw_frequency   = raw_frequency;
        if (f.has("celexfreq_freq_per_million")) entry.freq_per_million = freq_per_million;
        if (f.has("celexfreq_logprob"))  entry["-logprob"] = round(negLogProb(raw_frequency, total), FREQ_PRECISION);
        if (f.has("celexfreq_zipf"))     entry.zipf        = round(zipfScale(raw_frequency, total), FREQ_PRECISION);
        celexData.set(wordform, entry);
      }
    }

    if (s.has("celexfeat")) {
      const featRows = await queryAll(
        worker,
        "SELECT wordform, tags FROM features WHERE source = 'CELEX' ORDER BY wordform ASC",
      );
      for (const { wordform, tags } of featRows) {
        const entry = celexData.get(wordform) || { source: "CELEX" };
        if (f.has("celex_CELEXtags")) entry.celex_tags = tags;
        if (f.has("celex_UDtags")) {
          const ud = tagToTag("CELEX", "UD", tags);
          if (ud) entry.ud_tags = flatten(ud);
        }
        if (f.has("celex_UMtags")) {
          const um = tagToTag("CELEX", "UniMorph", tags);
          if (um) entry.um_tags = flatten(um);
        }
        celexData.set(wordform, entry);
      }
    }

    if (s.has("celexpron")) {
      const pronRows = await queryAll(
        worker,
        "SELECT wordform, pronunciation FROM pronunciation WHERE source = 'CELEX' AND standard = 'DISC' ORDER BY wordform ASC",
      );
      for (const { wordform, pronunciation } of pronRows) {
        const entry = celexData.get(wordform) || { source: "CELEX" };
        if (f.has("celex_DISC")) entry.DISC_pronunciation = pronunciation;
        celexData.set(wordform, entry);
      }
    }

    for (const [wordform, entry] of celexData) {
      const row = { wordform, source: entry.source };
      for (const key of ["raw_frequency","freq_per_million","-logprob","zipf",
                         "celex_tags","ud_tags","um_tags","DISC_pronunciation"]) {
        if (key in entry) row[key] = entry[key];
      }
      // Skip rows with no data columns beyond wordform + source.
      if (Object.keys(row).length < 3) continue;
      rows.push(buildTsvRow(columns, row));
    }
  }

  // --- SUBTLEX-UK / SUBTLEX-US ---
  for (const ukOrUs of ["UK", "US"]) {
    const srcKey    = `subtlex${ukOrUs}`;
    const srcName   = `SUBTLEX-${ukOrUs}`;
    if (!s.has(srcKey)) continue;

    const wantLogprob = f.has(`${srcKey}_logprob`);
    const wantZipf    = f.has(`${srcKey}_zipf`);
    const total = (wantLogprob || wantZipf) ? await fetchTotal(worker, srcName) : 0;

    const freqRows = await queryAll(
      worker,
      "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = ? ORDER BY wordform ASC",
      [srcName],
    );
    for (const { wordform, raw_frequency, freq_per_million } of freqRows) {
      const row = { wordform, source: srcName };
      if (f.has(`${srcKey}_raw_frequency`))   row.raw_frequency    = raw_frequency;
      if (f.has(`${srcKey}_freq_per_million`)) row.freq_per_million = freq_per_million;
      if (wantLogprob) row["-logprob"] = round(negLogProb(raw_frequency, total), FREQ_PRECISION);
      if (wantZipf)    row.zipf        = round(zipfScale(raw_frequency, total), FREQ_PRECISION);
      rows.push(buildTsvRow(columns, row));
    }
  }

  // --- UDLexicons and UniMorph feature sources ---
  const featureSources = [
    { srcKey: "UDLexicons", dbSrc: "UDLexicons", prefix: "udlex", fromFmt: "UD"       },
    { srcKey: "UniMorph",   dbSrc: "UniMorph",   prefix: "um",    fromFmt: "UniMorph" },
  ];
  for (const { srcKey, dbSrc, prefix, fromFmt } of featureSources) {
    if (!s.has(srcKey)) continue;
    const udField = `${prefix}_UDtags`;
    const umField = `${prefix}_UMtags`;
    const cxField = `${prefix}_CELEXtags`;

    const featRows = await queryAll(
      worker,
      "SELECT wordform, source, tags FROM features WHERE source = ? ORDER BY wordform ASC",
      [dbSrc],
    );
    for (const { wordform, source, tags } of featRows) {
      const row = { wordform, source };
      if (f.has(udField)) {
        if (fromFmt === "UniMorph") {
          const ud = tagToTag("UniMorph", "UD", tags);
          if (!ud) continue;
          row.ud_tags = flatten(ud);
        } else {
          row.ud_tags = tags;
        }
      }
      if (f.has(umField)) {
        if (fromFmt === "UD") {
          const um = tagToTag("UD", "UniMorph", tags);
          if (!um) continue;
          row.um_tags = flatten(um);
        } else {
          row.um_tags = tags;
        }
      }
      if (f.has(cxField)) {
        const cx = tagToTag(fromFmt, "CELEX", tags);
        if (!cx) continue;
        row.celex_tags = flatten(cx);
      }
      if (Object.keys(row).length < 3) continue;
      rows.push(buildTsvRow(columns, row));
    }
  }

  // --- ELP segmentation ---
  if (s.has("ELP")) {
    const elpRows = await queryAll(
      worker,
      "SELECT wordform, source, segmentation, nmorph FROM segmentation WHERE source = 'ELP' ORDER BY wordform ASC",
    );
    for (const { wordform, source, segmentation, nmorph } of elpRows) {
      const row = { wordform, source };
      if (f.has("elp_segmentation")) row.segmentation = segmentation;
      if (f.has("elp_nmorph"))       row.nmorph        = nmorph;
      rows.push(buildTsvRow(columns, row));
    }
  }

  // --- WikiPron US / UK ---
  for (const ukOrUs of ["US", "UK"]) {
    const srcKey  = `WikiPron ${ukOrUs}`;
    const prefix  = `wikipron${ukOrUs}`;
    if (!s.has(srcKey)) continue;
    const wantIpa    = f.has(`${prefix}_IPA`);
    const wantXsampa = f.has(`${prefix}_XSAMPA`);

    const pronRows = await queryAll(
      worker,
      "SELECT wordform, pronunciation FROM pronunciation WHERE source = ? AND standard = 'IPA' ORDER BY wordform ASC",
      [srcKey],
    );
    for (const { wordform, pronunciation } of pronRows) {
      const row = { wordform, source: srcKey };
      if (wantIpa)    row.IPA_pronunciation   = pronunciation;
      if (wantXsampa) row.XSAMPA_pronunciation = ipaToXsampa(pronunciation);
      if (Object.keys(row).length < 3) continue;
      rows.push(buildTsvRow(columns, row));
    }
  }

  const header = buildTsvRow(columns, Object.fromEntries(columns.map(c => [c, c])));
  return header + rows.join("");
}

// ---------------------------------------------------------------------------
// JSON generation
// ---------------------------------------------------------------------------

/**
 * Builds the wide JSON object keyed by wordform.
 * Values are objects mapping field labels to arrays of values (matching the
 * Python implementation's use of sets/lists per key).
 */
async function generateJson(worker, selectedSources, selectedFields) {
  const f = new Set(selectedFields);
  const s = new Set(selectedSources);

  // aggregated: Map<wordform, Map<label, Set<value>>>
  const aggregated = new Map();

  function add(wordform, label, value) {
    if (!aggregated.has(wordform)) aggregated.set(wordform, new Map());
    const entry = aggregated.get(wordform);
    if (!entry.has(label)) entry.set(label, new Set());
    const bucket = entry.get(label);
    if (Array.isArray(value)) {
      for (const v of value) bucket.add(v);
    } else {
      bucket.add(value);
    }
  }

  // Frequency sources.
  const freqMaps = [
    ["subtlexUK", "SUBTLEX-UK"],
    ["subtlexUS", "SUBTLEX-US"],
    ["celexfreq", "CELEX"],
  ];
  for (const [htmlSrc, dbSrc] of freqMaps) {
    if (!s.has(htmlSrc)) continue;
    const total = await fetchTotal(worker, dbSrc);
    const freqRows = await queryAll(
      worker,
      "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = ? ORDER BY wordform ASC",
      [dbSrc],
    );
    for (const { wordform, raw_frequency, freq_per_million } of freqRows) {
      if (f.has(`${htmlSrc}_raw_frequency`))
        add(wordform, `${dbSrc} (Raw frequency)`, raw_frequency);
      if (f.has(`${htmlSrc}_freq_per_million`))
        add(wordform, `${dbSrc} (Frequency per million words)`, freq_per_million);
      if (f.has(`${htmlSrc}_logprob`))
        add(wordform, `${dbSrc} (-log10 probability)`, round(negLogProb(raw_frequency, total), FREQ_PRECISION));
      if (f.has(`${htmlSrc}_zipf`))
        add(wordform, `${dbSrc} (Zipf scale)`, round(zipfScale(raw_frequency, total), FREQ_PRECISION));
    }
  }

  // UDLexicons features.
  if (s.has("UDLexicons")) {
    const rows = await queryAll(worker, "SELECT wordform, tags FROM features WHERE source = 'UDLexicons' ORDER BY wordform ASC");
    for (const { wordform, tags } of rows) {
      if (f.has("udlex_UDtags"))
        add(wordform, "UDLexicons features (Universal Dependency-style tags)", tags);
      if (f.has("udlex_UMtags")) {
        const um = tagToTag("UD", "UniMorph", tags);
        if (um) add(wordform, "UDLexicons features (UniMorph-style tags)", um);
      }
      if (f.has("udlex_CELEXtags")) {
        const cx = tagToTag("UD", "CELEX", tags);
        if (cx) add(wordform, "UDLexicons features (CELEX-style tags)", cx);
      }
    }
  }

  // UniMorph features.
  if (s.has("UniMorph")) {
    const rows = await queryAll(worker, "SELECT wordform, tags FROM features WHERE source = 'UniMorph' ORDER BY wordform ASC");
    for (const { wordform, tags } of rows) {
      if (f.has("um_UMtags"))
        add(wordform, "UniMorph features", tags);
      if (f.has("um_UDtags")) {
        const ud = tagToTag("UniMorph", "UD", tags);
        if (ud) add(wordform, "UniMorph features (Universal Dependency-style tags)", ud);
      }
      if (f.has("um_CELEXtags")) {
        const cx = tagToTag("UniMorph", "CELEX", tags);
        if (cx) add(wordform, "UniMorph features (CELEX-style tags)", cx);
      }
    }
  }

  // CELEX features.
  if (s.has("celexfeat")) {
    const rows = await queryAll(worker, "SELECT wordform, tags FROM features WHERE source = 'CELEX' ORDER BY wordform ASC");
    for (const { wordform, tags } of rows) {
      if (f.has("celex_CELEXtags"))
        add(wordform, "CELEX features", tags);
      if (f.has("celex_UDtags")) {
        const ud = tagToTag("CELEX", "UD", tags);
        if (ud) add(wordform, "CELEX features (Universal Dependency-style tags)", ud);
      }
      if (f.has("celex_UMtags")) {
        const um = tagToTag("CELEX", "UniMorph", tags);
        if (um) add(wordform, "CELEX features (UniMorph-style tags)", um);
      }
    }
  }

  // ELP segmentation.
  if (s.has("ELP")) {
    const rows = await queryAll(worker, "SELECT wordform, segmentation, nmorph FROM segmentation WHERE source = 'ELP' ORDER BY wordform ASC");
    for (const { wordform, segmentation, nmorph } of rows) {
      if (f.has("elp_segmentation")) add(wordform, "ELP (Segmentation)", segmentation);
      if (f.has("elp_nmorph"))       add(wordform, "ELP (Number of morphs)", Number(nmorph));
    }
  }

  // WikiPron pronunciations.
  for (const [srcKey, prefix, ipaLabel] of [
    ["WikiPron US", "wikipronUS", "WikiPron US (IPA)"],
    ["WikiPron UK", "wikipronUK", "WikiPron UK (IPA)"],
  ]) {
    if (!s.has(srcKey)) continue;
    const rows = await queryAll(
      worker,
      "SELECT wordform, pronunciation FROM pronunciation WHERE source = ? AND standard = 'IPA' ORDER BY wordform ASC",
      [srcKey],
    );
    for (const { wordform, pronunciation } of rows) {
      if (f.has(`${prefix}_IPA`))    add(wordform, ipaLabel, pronunciation);
      if (f.has(`${prefix}_XSAMPA`)) add(wordform, ipaLabel.replace("(IPA)", "(X-SAMPA)"), ipaToXsampa(pronunciation));
    }
  }

  // CELEX pronunciations.
  if (s.has("celexpron")) {
    const rows = await queryAll(
      worker,
      "SELECT wordform, pronunciation FROM pronunciation WHERE source = 'CELEX' AND standard = 'DISC' ORDER BY wordform ASC",
    );
    for (const { wordform, pronunciation } of rows) {
      if (f.has("celex_DISC")) add(wordform, "CELEX (DISC)", pronunciation);
    }
  }

  // Serialise: convert Set values to sorted arrays.
  const out = {};
  for (const [wordform, entry] of aggregated) {
    out[wordform] = {};
    for (const [label, valueSet] of entry) {
      out[wordform][label] = [...valueSet].sort();
    }
  }
  return JSON.stringify(out);
}

// ---------------------------------------------------------------------------
// Download helper
// ---------------------------------------------------------------------------

function triggerDownload(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------------

/**
 * Reactively toggles the 'required' attribute on the license checkbox
 * based on whether any CELEX data sources are currently selected.
 */
function updateCelexValidation() {
  const form = document.querySelector("form");
  if (!form) return;

  const selectedSources = [...form.querySelectorAll("input[name='sources[]']:checked")].map(el => el.value);
  const celexSources = new Set(["celexfreq", "celexfeat", "celexpron"]);
  const celexSelected = selectedSources.some(s => celexSources.has(s));

  const ack = form.querySelector("#celex-license-ack");
  if (ack) {
    ack.required = celexSelected;
  }
}

async function handleSubmit(event) {
  event.preventDefault();

  const form           = event.target;
  const selectedSources = [...form.querySelectorAll("input[name='sources[]']:checked")].map(el => el.value);
  const selectedFields  = [...form.querySelectorAll("input[name='fields[]']:checked")].map(el => el.value);
  const outputFormat    = form.querySelector("input[name='output_format']:checked")?.value ?? "long";

  if (selectedSources.length === 0 || selectedFields.length === 0) {
    showError("Please select at least one data source and one field.");
    return;
  }

  const btn = form.querySelector("button[type='submit']");
  const originalText = btn.textContent;
  btn.textContent = "Working…";
  btn.disabled = true;
  hideError();

  try {
    const worker = await getWorker();
    const today  = new Date().toISOString().slice(0, 10);

    if (outputFormat === "long") {
      const tsv = await generateTsv(worker, selectedSources, selectedFields);
      triggerDownload(tsv, `citylex-${today}.tsv`, "text/tab-separated-values");
    } else {
      const json = await generateJson(worker, selectedSources, selectedFields);
      triggerDownload(json, `citylex-${today}.json`, "application/json");
    }
  } catch (err) {
    console.error(err);
    showError(`Error generating output: ${err.message}`);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

function showError(msg) {
  let el = document.getElementById("js-error");
  if (!el) {
    el = document.createElement("p");
    el.id = "js-error";
    el.style.cssText = "color:red;font-weight:bold;";
    document.querySelector("form")?.prepend(el);
  }
  el.textContent = msg;
  el.style.display = "block";
}

function hideError() {
  const el = document.getElementById("js-error");
  if (el) el.style.display = "none";
}

// Update your initialization block at the bottom of the file
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("form");
  form?.addEventListener("submit", handleSubmit);
  form?.addEventListener("change", updateCelexValidation); // Catch user selections reactively
  detectCelex();
});

// Detect whether the DB has CELEX data and reveal CELEX source blocks if so.
async function detectCelex() {
  try {
    const worker = await getWorker();
    const rows = await queryAll(
      worker,
      "SELECT 1 FROM frequency WHERE source = 'CELEX' LIMIT 1",
    );
    if (rows.length > 0) {
      document.querySelectorAll(".celex-source-block").forEach(el => {
        el.style.display = "";
      });
      const ackSection = document.getElementById("celex-license-section");
      if (ackSection) ackSection.style.display = "";
      
      updateCelexValidation(); // Run initial check after revealing the UI elements
    }
  } catch (err) {
    console.error("CityLex: failed to initialise DB worker:", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector("form")?.addEventListener("submit", handleSubmit);
  detectCelex();
});
