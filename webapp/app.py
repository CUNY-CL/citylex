"""CityLex Flask web application."""

import csv
import datetime
import io
import json
import logging
import math
import os
import sqlite3

from collections.abc import Generator, Iterator
from typing import Any

import flask

from citylex import features, xsampa, zipf

DB_PATH = "citylex.db"
FREQUENCY_PRECISION = 6

# Helpers.


def _neg_logprob(raw_freq: int, total_words: int) -> float:
    if raw_freq > 0:
        return -math.log10(raw_freq / total_words)
    return math.inf


def _flatten(maybe_list: str | list[str]) -> str:
    """Joins a list of tags to a comma-separated string, or passes through."""
    if isinstance(maybe_list, list):
        return ",".join(maybe_list)
    return maybe_list


def _fetch_total_words(cursor: sqlite3.Cursor, source: str) -> int:
    """Returns the total raw-frequency count for a given source."""
    cursor.execute(
        "SELECT SUM(raw_frequency) FROM frequency WHERE source = ?",
        (source,),
    )
    row = cursor.fetchone()
    return row[0] or 0 if row else 0


# TSV streaming.
#
# Each _generate_*_tsv function is a generator that yields individual rows
# as formatted strings. The outer _generate_tsv assembles them in order.
# We use csv.writer writing into a reusable StringIO so all quoting/escaping
# is handled by the stdlib: callers never construct raw TSV strings.


def _csv_row(
    writer: "csv.DictWriter[str]",
    buf: io.StringIO,
    row: dict[str, Any],
) -> str:
    """Writes one DictWriter row."""
    writer.writerow(row)
    value = buf.getvalue()
    buf.seek(0)
    buf.truncate(0)
    return value


def _generate_celex_tsv(
    cursor: sqlite3.Cursor,
    writer: "csv.DictWriter[str]",
    buf: io.StringIO,
    selected_sources: list[str],
    selected_fields: list[str],
) -> Iterator[str]:
    """Yields TSV rows for all selected CELEX sub-sources."""
    # Because the three CELEX sub-sources (freq / feat / pron) share wordforms
    # we still need to aggregate per wordform — but we do it one source at a
    # time and keep only the current result set in memory, not the whole DB.
    celex_data: dict[str, dict[str, Any]] = {}
    if "celexfreq" in selected_sources:
        total = _fetch_total_words(cursor, "CELEX")
        cursor.execute(
            "SELECT wordform, raw_frequency, freq_per_million "
            "FROM frequency WHERE source = 'CELEX'"
        )
        for wordform, raw_freq, freq_per_mil in cursor:
            entry = celex_data.setdefault(wordform, {"source": "CELEX"})
            if "celexfreq_raw_frequency" in selected_fields:
                entry["raw_frequency"] = raw_freq
            if "celexfreq_freq_per_million" in selected_fields:
                entry["freq_per_million"] = freq_per_mil
            if "celexfreq_logprob" in selected_fields:
                entry["-logprob"] = round(
                    _neg_logprob(raw_freq, total), FREQUENCY_PRECISION
                )
            if "celexfreq_zipf" in selected_fields:
                entry["zipf"] = round(
                    zipf.zipf_scale(raw_freq, total),
                    FREQUENCY_PRECISION,
                )
    if "celexfeat" in selected_sources:
        cursor.execute(
            "SELECT wordform, tags FROM features WHERE source = 'CELEX'"
        )
        for wordform, celex_tags in cursor:
            entry = celex_data.setdefault(wordform, {"source": "CELEX"})
            if "celex_CELEXtags" in selected_fields:
                entry["celex_tags"] = celex_tags
            if "celex_UDtags" in selected_fields:
                if ud := features.tag_to_tag("CELEX", "UD", celex_tags):
                    entry["ud_tags"] = _flatten(ud)
            if "celex_UMtags" in selected_fields:
                if um := features.tag_to_tag("CELEX", "UniMorph", celex_tags):
                    entry["um_tags"] = _flatten(um)

    if "celexpron" in selected_sources:
        cursor.execute(
            "SELECT wordform, pronunciation FROM pronunciation "
            "WHERE source = 'CELEX' AND standard = 'DISC'"
        )
        for wordform, pronunciation in cursor:
            entry = celex_data.setdefault(wordform, {"source": "CELEX"})
            if "celex_DISC" in selected_fields:
                entry["DISC_pronunciation"] = pronunciation
    for wordform, data in celex_data.items():
        row: dict[str, Any] = {
            "wordform": wordform,
            "source": data["source"],
        }
        for key in (
            "raw_frequency",
            "freq_per_million",
            "-logprob",
            "zipf",
            "celex_tags",
            "ud_tags",
            "um_tags",
            "DISC_pronunciation",
        ):
            if key in data:
                row[key] = data[key]
        if len(row) < 3:
            continue
        yield _csv_row(writer, buf, row)


def _generate_subtlex_tsv(
    cursor: sqlite3.Cursor,
    writer: "csv.DictWriter[str]",
    buf: io.StringIO,
    selected_fields: list[str],
    uk_or_us: str,
) -> Iterator[str]:
    """Yields TSV rows for a SUBTLEX source, streaming the cursor directly."""
    source_name = f"SUBTLEX-{uk_or_us}"
    field_prefix = f"subtlex{uk_or_us}"
    want_logprob = f"{field_prefix}_logprob" in selected_fields
    want_zipf = f"{field_prefix}_zipf" in selected_fields
    total = (
        _fetch_total_words(cursor, source_name)
        if (want_logprob or want_zipf)
        else 0
    )
    cursor.execute(
        "SELECT wordform, raw_frequency, freq_per_million "
        "FROM frequency WHERE source = ?",
        (source_name,),
    )
    for wordform, raw_freq, freq_per_mil in cursor:
        row: dict[str, Any] = {
            "wordform": wordform,
            "source": source_name,
        }
        if f"{field_prefix}_raw_frequency" in selected_fields:
            row["raw_frequency"] = raw_freq
        if f"{field_prefix}_freq_per_million" in selected_fields:
            row["freq_per_million"] = freq_per_mil
        if want_logprob:
            row["-logprob"] = round(
                _neg_logprob(raw_freq, total), FREQUENCY_PRECISION
            )
        if want_zipf:
            row["zipf"] = round(
                zipf.zipf_scale(raw_freq, total), FREQUENCY_PRECISION
            )
        yield _csv_row(writer, buf, row)


def _generate_features_tsv(
    cursor: sqlite3.Cursor,
    writer: "csv.DictWriter[str]",
    buf: io.StringIO,
    selected_fields: list[str],
    source: str,
    field_prefix: str,
    from_format: str,
) -> Iterator[str]:
    """Yields TSV rows for UDLexicons or UniMorph feature sources."""
    ud_field = f"{field_prefix}_UDtags"
    um_field = f"{field_prefix}_UMtags"
    cx_field = f"{field_prefix}_CELEXtags"
    cursor.execute(
        "SELECT wordform, source, tags FROM features WHERE source = ?",
        (source,),
    )
    for wordform, src, tags in cursor:
        row: dict[str, Any] = {"wordform": wordform, "source": src}
        if ud_field in selected_fields:
            if from_format == "UniMorph":
                if ud := features.tag_to_tag("UniMorph", "UD", tags):
                    row["ud_tags"] = _flatten(ud)
                else:
                    continue
            else:
                row["ud_tags"] = tags
        if um_field in selected_fields:
            if from_format == "UD":
                if um := features.tag_to_tag("UD", "UniMorph", tags):
                    row["um_tags"] = _flatten(um)
                else:
                    continue
            else:
                row["um_tags"] = tags
        if cx_field in selected_fields:
            src_fmt = "UD" if from_format == "UD" else "UniMorph"
            if cx := features.tag_to_tag(src_fmt, "CELEX", tags):
                row["celex_tags"] = _flatten(cx)
            else:
                continue
        if len(row) < 3:
            continue
        yield _csv_row(writer, buf, row)


def _generate_elp_tsv(
    cursor: sqlite3.Cursor,
    writer: "csv.DictWriter[str]",
    buf: io.StringIO,
    selected_fields: list[str],
) -> Iterator[str]:
    """Yields TSV rows for ELP segmentations."""
    cols = ["wordform", "source"]
    if "elp_segmentation" in selected_fields:
        cols.append("segmentation")
    if "elp_nmorph" in selected_fields:
        cols.append("nmorph")
    cursor.execute(
        f"SELECT {', '.join(cols)} FROM segmentation WHERE source = 'ELP'"
    )
    for db_row in cursor:
        row = dict(zip(cols, db_row))
        yield _csv_row(writer, buf, row)


def _generate_wikipron_tsv(
    cursor: sqlite3.Cursor,
    writer: "csv.DictWriter[str]",
    buf: io.StringIO,
    selected_fields: list[str],
    uk_or_us: str,
) -> Iterator[str]:
    """Yields TSV rows for a WikiPron source (IPA and/or X-SAMPA)."""
    source_name = f"WikiPron {uk_or_us}"
    field_prefix = f"wikipron{uk_or_us}"
    want_ipa = f"{field_prefix}_IPA" in selected_fields
    want_xsampa = f"{field_prefix}_XSAMPA" in selected_fields
    cursor.execute(
        "SELECT wordform, pronunciation FROM pronunciation "
        "WHERE source = ? AND standard = 'IPA'",
        (source_name,),
    )
    for wordform, ipa_pron in cursor:
        row: dict[str, Any] = {
            "wordform": wordform,
            "source": source_name,
        }
        if want_ipa:
            row["IPA_pronunciation"] = ipa_pron
        if want_xsampa:
            row["XSAMPA_pronunciation"] = xsampa.ipa_to_xsampa(ipa_pron)
        if len(row) < 3:
            continue
        yield _csv_row(writer, buf, row)


def _generate_tsv(
    cursor: sqlite3.Cursor,
    selected_sources: list[str],
    selected_fields: list[str],
    columns: list[str],
) -> Generator[str, None, None]:
    """Top-level generator: yields header then all data rows as TSV strings."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=columns,
        delimiter="\t",
        extrasaction="ignore",
        lineterminator="\n",
    )
    # Header.
    writer.writeheader()
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)
    if any(
        s in selected_sources for s in ("celexfreq", "celexfeat", "celexpron")
    ):
        yield from _generate_celex_tsv(
            cursor, writer, buf, selected_sources, selected_fields
        )
    if "subtlexUK" in selected_sources:
        yield from _generate_subtlex_tsv(
            cursor, writer, buf, selected_fields, "UK"
        )
    if "subtlexUS" in selected_sources:
        yield from _generate_subtlex_tsv(
            cursor, writer, buf, selected_fields, "US"
        )
    if "UDLexicons" in selected_sources:
        yield from _generate_features_tsv(
            cursor,
            writer,
            buf,
            selected_fields,
            "UDLexicons",
            "udlex",
            "UD",
        )
    if "UniMorph" in selected_sources:
        yield from _generate_features_tsv(
            cursor,
            writer,
            buf,
            selected_fields,
            "UniMorph",
            "um",
            "UniMorph",
        )
    if "ELP" in selected_sources:
        yield from _generate_elp_tsv(cursor, writer, buf, selected_fields)
    if "WikiPron US" in selected_sources:
        yield from _generate_wikipron_tsv(
            cursor, writer, buf, selected_fields, "US"
        )
    if "WikiPron UK" in selected_sources:
        yield from _generate_wikipron_tsv(
            cursor, writer, buf, selected_fields, "UK"
        )


# JSON streaming.
#
# The wide JSON format is a single object keyed by wordform. True streaming
# of a JSON object is possible by emitting it manually: opening brace, then
# one "key": value pair per wordform separated by commas, then closing brace.
# Each value is serialised with json.dumps so all escaping is handled for us.


class _SetEncoder(json.JSONEncoder):
    """JSON encoder that converts sets to sorted lists."""

    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)


def _add_to_word_entry(
    entry: dict[str, set[Any]],
    key: str,
    value: Any,
) -> None:
    """Adds a value (or list of values) to a set under *key* in *entry*."""
    bucket = entry.setdefault(key, set())
    if isinstance(value, list):
        bucket.update(value)
    else:
        bucket.add(value)


def _generate_json(
    cursor: sqlite3.Cursor,
    selected_sources: list[str],
    selected_fields: list[str],
) -> Generator[str, None, None]:
    """Streams a wide JSON layout."""
    # Maps input parameters safely to canonical database tokens.
    active_queries: list[str] = []
    freq_maps = [
        ("subtlexUK", "SUBTLEX-UK"),
        ("subtlexUS", "SUBTLEX-US"),
        ("celexfreq", "CELEX"),
    ]
    totals = {}
    for html_src, db_src in freq_maps:
        if html_src in selected_sources:
            totals[db_src] = _fetch_total_words(cursor, db_src)
            # Selects placeholder markers to keep schemas unified.
            active_queries.append(
                "SELECT wordform, "
                f"'freq:{db_src}' AS dtype, "
                "raw_frequency AS v1, "
                "freq_per_million AS v2 "
                "FROM frequency "
                f"WHERE source = '{db_src}'"
            )
    feat_sources = [
        s
        for s in ["UDLexicons", "UniMorph", "celexfeat"]
        if s in selected_sources
    ]
    for src in feat_sources:
        db_src = "CELEX" if src == "celexfeat" else src
        active_queries.append(
            "SELECT wordform, "
            f"'feat:{src}' AS dtype, "
            "tags AS v1, "
            "NULL AS v2 "
            "FROM features "
            f"WHERE source = '{db_src}'"
        )
    if "ELP" in selected_sources:
        active_queries.append(
            "SELECT wordform, "
            "'seg:ELP' AS dtype, "
            "segmentation AS v1, "
            "nmorph AS v2 "
            "FROM segmentation "
            "WHERE source = 'ELP'"
        )
    pron_maps = [("wikipronUS", "WikiPron US"), ("wikipronUK", "WikiPron UK")]
    for html_src, db_src in pron_maps:
        if html_src in selected_sources:
            active_queries.append(
                "SELECT wordform, "
                f"'pron:{html_src}' AS dtype, "
                "pronunciation AS v1, "
                "standard AS v2 "
                "FROM pronunciation "
                f"WHERE source = '{db_src}' AND standard = 'IPA'",
            )
    if "celexpron" in selected_sources:
        active_queries.append(
            "SELECT wordform, "
            "'pron:celex' AS dtype, "
            "pronunciation AS v1, "
            "standard AS v2 "
            "FROM pronunciation "
            "WHERE source = 'CELEX' AND standard = 'DISC'"
        )
    if not active_queries:
        yield "{}"
        return
    # Compiles an aggregated UNION query ordered strictly by wordform.
    # This delegates sorting overhead straight to SQLite's compiled C layer!
    master_query = " UNION ALL ".join(active_queries) + " ORDER BY wordform"
    cursor.execute(master_query)
    encoder = _SetEncoder(ensure_ascii=False, separators=(",", ":"))
    yield "{"
    current_word: str | None = None
    current_entry: dict[str, set[Any]] = {}
    is_first_emit = True

    def flush_current() -> str:
        nonlocal is_first_emit
        prefix = "" if is_first_emit else ","
        is_first_emit = False
        key_str = json.dumps(current_word, ensure_ascii=False)
        val_str = encoder.encode(current_entry)
        return f"{prefix}{key_str}:{val_str}"

    # Iterates over the stream cursor.
    for wordform, dtype, v1, v2 in cursor:
        if wordform != current_word:
            if current_word is not None and current_entry:
                yield flush_current()
            current_word = wordform
            current_entry = {}
        # Parses data streams on-the-fly and collect properties locally.
        if dtype.startswith("freq:"):
            db_src = dtype.split(":")[1]
            html_src = next(k for k, v in freq_maps if v == db_src)
            raw_freq, freq_per_mil = int(v1), float(v2)
            if f"{html_src}_raw_frequency" in selected_fields:
                _add_to_word_entry(
                    current_entry, f"{db_src} (Raw frequency)", raw_freq
                )
            if f"{html_src}_freq_per_million" in selected_fields:
                _add_to_word_entry(
                    current_entry,
                    f"{db_src} (Frequency per million words)",
                    freq_per_mil,
                )
            if f"{html_src}_logprob" in selected_fields:
                _add_to_word_entry(
                    current_entry,
                    f"{db_src} (-log10 probability)",
                    round(
                        _neg_logprob(raw_freq, totals[db_src]),
                        FREQUENCY_PRECISION,
                    ),
                )
            if f"{html_src}_zipf" in selected_fields:
                _add_to_word_entry(
                    current_entry,
                    f"{db_src} (Zipf scale)",
                    round(
                        zipf.zipf_scale(raw_freq, totals[db_src]),
                        FREQUENCY_PRECISION,
                    ),
                )
        elif dtype.startswith("feat:"):
            src = dtype.split(":")[1]
            tags = v1
            if src == "UDLexicons":
                if "udlex_UDtags" in selected_fields:
                    _add_to_word_entry(
                        current_entry,
                        "UDLexicons features "
                        "(Universal Dependency-style tags)",
                        tags,
                    )
                if "udlex_UMtags" in selected_fields and (
                    um := features.tag_to_tag("UD", "UniMorph", tags)
                ):
                    _add_to_word_entry(
                        current_entry,
                        "UDLexicons features (UniMorph-style tags)",
                        um,
                    )
                if "udlex_CELEXtags" in selected_fields and (
                    cx := features.tag_to_tag("UD", "CELEX", tags)
                ):
                    _add_to_word_entry(
                        current_entry,
                        "UDLexicons features (CELEX-style tags)",
                        cx,
                    )
            elif src == "UniMorph":
                if "um_UMtags" in selected_fields:
                    _add_to_word_entry(
                        current_entry, "UniMorph features", tags
                    )
                if "um_UDtags" in selected_fields and (
                    ud := features.tag_to_tag("UniMorph", "UD", tags)
                ):
                    _add_to_word_entry(
                        current_entry,
                        "UniMorph features (Universal Dependency-style tags)",
                        ud,
                    )
                if "um_CELEXtags" in selected_fields and (
                    cx := features.tag_to_tag("UniMorph", "CELEX", tags)
                ):
                    _add_to_word_entry(
                        current_entry,
                        "UniMorph features (CELEX-style tags)",
                        cx,
                    )
            elif src == "celexfeat":
                if "celex_CELEXtags" in selected_fields:
                    _add_to_word_entry(current_entry, "CELEX features", tags)
                if "celex_UDtags" in selected_fields and (
                    ud := features.tag_to_tag("CELEX", "UD", tags)
                ):
                    _add_to_word_entry(
                        current_entry,
                        "CELEX features (Universal Dependency-style tags)",
                        ud,
                    )
                if "celex_UMtags" in selected_fields and (
                    um := features.tag_to_tag("CELEX", "UniMorph", tags)
                ):
                    _add_to_word_entry(
                        current_entry,
                        "CELEX features (UniMorph-style tags)",
                        um,
                    )
        elif dtype == "seg:ELP":
            if "elp_segmentation" in selected_fields:
                _add_to_word_entry(current_entry, "ELP (Segmentation)", v1)
            if "elp_nmorph" in selected_fields:
                _add_to_word_entry(
                    current_entry, "ELP (Number of morphs)", int(v2)
                )
        elif dtype.startswith("pron:"):
            sub_type = dtype.split(":")[1]
            if sub_type in ("wikipronUS", "wikipronUK"):
                label = (
                    "WikiPron US (IPA)"
                    if sub_type == "wikipronUS"
                    else "WikiPron UK (IPA)"
                )
                if f"{sub_type}_IPA" in selected_fields:
                    _add_to_word_entry(current_entry, label, v1)
                if f"{sub_type}_XSAMPA" in selected_fields:
                    _add_to_word_entry(
                        current_entry,
                        label.replace("(IPA)", "(X-SAMPA)"),
                        xsampa.ipa_to_xsampa(v1),
                    )
            elif sub_type == "celex" and "celex_DISC" in selected_fields:
                _add_to_word_entry(current_entry, "CELEX (DISC)", v1)
    # Flushes out the very last remaining active token block.
    if current_word is not None and current_entry:
        yield flush_current()
    yield "}"


# Flask app.

app = flask.Flask(__name__)


def _build_tsv_columns(selected_fields: list[str]) -> list[str]:
    """Derives the ordered set of TSV column names from the selected fields."""
    columns: list[str] = ["wordform", "source"]
    freq_fields = {
        "raw_frequency": {
            "subtlexUS_raw_frequency",
            "subtlexUK_raw_frequency",
            "celexfreq_raw_frequency",
        },
        "freq_per_million": {
            "subtlexUS_freq_per_million",
            "subtlexUK_freq_per_million",
            "celexfreq_freq_per_million",
        },
        "-logprob": {
            "subtlexUK_logprob",
            "subtlexUS_logprob",
            "celexfreq_logprob",
        },
        "zipf": {
            "subtlexUK_zipf",
            "subtlexUS_zipf",
            "celexfreq_zipf",
        },
    }
    for col, triggers in freq_fields.items():
        if triggers & set(selected_fields):
            columns.append(col)
    if {"wikipronUS_IPA", "wikipronUK_IPA"} & set(selected_fields):
        columns.append("IPA_pronunciation")
    if {"wikipronUS_XSAMPA", "wikipronUK_XSAMPA"} & set(selected_fields):
        columns.append("XSAMPA_pronunciation")
    if "celex_DISC" in selected_fields:
        columns.append("DISC_pronunciation")
    if {"udlex_CELEXtags", "um_CELEXtags", "celex_CELEXtags"} & set(
        selected_fields
    ):
        columns.append("celex_tags")
    if {"udlex_UDtags", "um_UDtags", "celex_UDtags"} & set(selected_fields):
        columns.append("ud_tags")
    if {"udlex_UMtags", "um_UMtags", "celex_UMtags"} & set(selected_fields):
        columns.append("um_tags")
    if "elp_segmentation" in selected_fields:
        columns.append("segmentation")
    if "elp_nmorph" in selected_fields:
        columns.append("nmorph")
    return columns


@app.route("/", methods=["GET"])
def get() -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM frequency WHERE source = 'CELEX' LIMIT 1"
        )
        celex_present = cursor.fetchone() is not None
    return flask.render_template(
        "index.html",
        celex_present=celex_present,
        password_set="CELEX_PASSWORD" in os.environ,
    )


@app.route("/", methods=["POST"])
def post() -> flask.Response | tuple[str, int]:
    # Extracts form data.
    selected_sources: list[str] = flask.request.form.getlist("sources[]")
    selected_fields: list[str] = flask.request.form.getlist("fields[]")
    output_format: str = flask.request.form["output_format"]
    licenses: list[str] = flask.request.form.getlist("licenses")
    if not selected_sources or not selected_fields:
        return flask.render_template("400.html"), 400
    # Logs user selections.
    logging.info("Selected sources: %s", selected_sources)
    logging.info("Selected fields: %s", selected_fields)
    logging.info("Output format: %s", output_format)
    logging.info("Licenses: %s", licenses)
    # Password protects CELEX data if present.
    celex_password_env = os.environ.get("CELEX_PASSWORD")
    if celex_password_env:
        celex_selected = any(
            s in selected_sources
            for s in ["celexfreq", "celexfeat", "celexpron"]
        )
        if celex_selected:
            celex_password_form = flask.request.form.get("celex_password")
            if (
                not celex_password_form
                or celex_password_form != celex_password_env
            ):
                return flask.render_template("401.html"), 401
    # Responds.
    today = datetime.date.today().isoformat()
    if output_format == "long":
        columns = _build_tsv_columns(selected_fields)

        def tsv_stream() -> Generator[str, None, None]:
            conn = sqlite3.connect(DB_PATH)
            try:
                yield from _generate_tsv(
                    conn.cursor(),
                    selected_sources,
                    selected_fields,
                    columns,
                )
            finally:
                conn.close()

        return flask.Response(
            flask.stream_with_context(tsv_stream()),
            mimetype="text/tab-separated-values",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="citylex-{today}.tsv"'
                ),
            },
        )
    elif output_format == "wide":

        def json_stream() -> Generator[str, None, None]:
            conn = sqlite3.connect(DB_PATH)
            try:
                yield from _generate_json(
                    conn.cursor(), selected_sources, selected_fields
                )
            finally:
                conn.close()

        return flask.Response(
            flask.stream_with_context(json_stream()),
            mimetype="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="citylex-{today}.json"'
                ),
            },
        )
    # Should be unreachable.
    return flask.render_template("400.html"), 400


if __name__ == "__main__":
    app.run()
