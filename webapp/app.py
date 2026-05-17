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
    writer: "csv.DictWriter[str]", buf: io.StringIO, row: dict[str, Any]
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
                    zipf.zipf_scale(raw_freq, total), FREQUENCY_PRECISION
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
        row: dict[str, Any] = {"wordform": wordform, "source": data["source"]}
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
        row: dict[str, Any] = {"wordform": wordform, "source": source_name}
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
        row: dict[str, Any] = {"wordform": wordform, "source": source_name}
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
            cursor, writer, buf, selected_fields, "UDLexicons", "udlex", "UD"
        )
    if "UniMorph" in selected_sources:
        yield from _generate_features_tsv(
            cursor, writer, buf, selected_fields, "UniMorph", "um", "UniMorph"
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
    """Yields a streaming wide-format JSON document, one wordform per chunk."""
    # We must accumulate per-wordform data in memory for the wide format,
    # but we build it source-by-source to avoid holding everything at once.
    # The final emit is still word-by-word so the HTTP response streams.
    aggregated: dict[str, dict[str, set[Any]]] = {}

    def add(wordform: str, key: str, value: Any) -> None:
        _add_to_word_entry(aggregated.setdefault(wordform, {}), key, value)

    # Frequency sources.
    for db_source, field_prefix in (
        ("SUBTLEX-UK", "subtlexUK"),
        ("SUBTLEX-US", "subtlexUS"),
        ("CELEX", "celexfreq"),
    ):
        if field_prefix not in selected_sources:
            continue
        total = _fetch_total_words(cursor, db_source)
        cursor.execute(
            "SELECT wordform, raw_frequency, freq_per_million "
            "FROM frequency WHERE source = ?",
            (db_source,),
        )
        for wordform, raw_freq, freq_per_mil in cursor:
            if f"{field_prefix}_raw_frequency" in selected_fields:
                add(wordform, f"{db_source} (Raw frequency)", raw_freq)
            if f"{field_prefix}_freq_per_million" in selected_fields:
                add(
                    wordform,
                    f"{db_source} (Frequency per million words)",
                    freq_per_mil,
                )
            if f"{field_prefix}_logprob" in selected_fields:
                add(
                    wordform,
                    f"{db_source} (-log10 probability)",
                    round(_neg_logprob(raw_freq, total), FREQUENCY_PRECISION),
                )
            if f"{field_prefix}_zipf" in selected_fields:
                add(
                    wordform,
                    f"{db_source} (Zipf scale)",
                    round(
                        zipf.zipf_scale(raw_freq, total), FREQUENCY_PRECISION
                    ),
                )

    # Feature sources.
    if "UDLexicons" in selected_sources:
        cursor.execute(
            "SELECT wordform, tags FROM features WHERE source = 'UDLexicons'"
        )
        for wordform, ud_tags in cursor:
            if "udlex_UDtags" in selected_fields:
                add(
                    wordform,
                    "UDLexicons features (Universal Dependency-style tags)",
                    ud_tags,
                )
            if "udlex_UMtags" in selected_fields:
                if um := features.tag_to_tag("UD", "UniMorph", ud_tags):
                    add(
                        wordform,
                        "UDLexicons features (UniMorph-style tags)",
                        um,
                    )
            if "udlex_CELEXtags" in selected_fields:
                if cx := features.tag_to_tag("UD", "CELEX", ud_tags):
                    add(wordform, "UDLexicons features (CELEX-style tags)", cx)
    if "UniMorph" in selected_sources:
        cursor.execute(
            "SELECT wordform, tags FROM features WHERE source = 'UniMorph'"
        )
        for wordform, um_tags in cursor:
            if "um_UMtags" in selected_fields:
                add(wordform, "UniMorph features", um_tags)
            if "um_UDtags" in selected_fields:
                if ud := features.tag_to_tag("UniMorph", "UD", um_tags):
                    add(
                        wordform,
                        "UniMorph features (Universal Dependency-style tags)",
                        ud,
                    )
            if "um_CELEXtags" in selected_fields:
                if cx := features.tag_to_tag("UniMorph", "CELEX", um_tags):
                    add(wordform, "UniMorph features (CELEX-style tags)", cx)
    if "celexfeat" in selected_sources:
        cursor.execute(
            "SELECT wordform, tags FROM features WHERE source = 'CELEX'"
        )
        for wordform, celex_tags in cursor:
            if "celex_CELEXtags" in selected_fields:
                add(wordform, "CELEX features", celex_tags)
            if "celex_UDtags" in selected_fields:
                if ud := features.tag_to_tag("CELEX", "UD", celex_tags):
                    add(
                        wordform,
                        "CELEX features (Universal Dependency-style tags)",
                        ud,
                    )
            if "celex_UMtags" in selected_fields:
                if um := features.tag_to_tag("CELEX", "UniMorph", celex_tags):
                    add(wordform, "CELEX features (UniMorph-style tags)", um)
    # Segmentation.
    if "ELP" in selected_sources:
        cursor.execute(
            "SELECT wordform, segmentation, nmorph "
            "FROM segmentation "
            "WHERE source = 'ELP'"
        )
        for wordform, segmentation, nmorph in cursor:
            if "elp_segmentation" in selected_fields:
                add(wordform, "ELP (Segmentation)", segmentation)
            if "elp_nmorph" in selected_fields:
                add(wordform, "ELP (Number of morphs)", nmorph)
    # Pronunciation sources.
    for source_key, field_prefix, ipa_label in (
        ("WikiPron US", "wikipronUS", "WikiPron US (IPA)"),
        ("WikiPron UK", "wikipronUK", "WikiPron UK (IPA)"),
    ):
        if source_key not in selected_sources:
            continue
        cursor.execute(
            "SELECT wordform, pronunciation "
            "FROM pronunciation "
            "WHERE source = ? AND standard = 'IPA'",
            (source_key,),
        )
        for wordform, pronunciation in cursor:
            if f"{field_prefix}_IPA" in selected_fields:
                add(wordform, ipa_label, pronunciation)
            if f"{field_prefix}_XSAMPA" in selected_fields:
                xsampa_label = ipa_label.replace("(IPA)", "(X-SAMPA)")
                add(
                    wordform, xsampa_label, xsampa.ipa_to_xsampa(pronunciation)
                )

    if "celexpron" in selected_sources:
        cursor.execute(
            "SELECT wordform, pronunciation FROM pronunciation "
            "WHERE source = 'CELEX' AND standard = 'DISC'"
        )
        for wordform, pronunciation in cursor:
            if "celex_DISC" in selected_fields:
                add(wordform, "CELEX (DISC)", pronunciation)
    # Emits the JSON object incrementally. Each wordform entry is serialized
    # individually so we never hold the full document in memory. Sets are
    # converted to sorted lists by the encoder.
    encoder = _SetEncoder(ensure_ascii=False, separators=(",", ":"))
    yield "{"
    first = True
    for wordform, entry in aggregated.items():
        prefix = "" if first else ","
        first = False
        key_str = json.dumps(wordform, ensure_ascii=False)
        value_str = encoder.encode(entry)
        yield f"{prefix}{key_str}:{value_str}"
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
        "zipf": {"subtlexUK_zipf", "subtlexUS_zipf", "celexfreq_zipf"},
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM frequency WHERE source = 'CELEX' LIMIT 1")
    celex_present = cursor.fetchone() is not None
    conn.close()
    return flask.render_template(
        "index.html",
        celex_present=celex_present,
        password_set="CELEX_PASSWORD" in os.environ,
    )


@app.route("/", methods=["POST"])
def post() -> flask.Response | tuple[str, int]:
    selected_sources: list[str] = flask.request.form.getlist("sources[]")
    selected_fields: list[str] = flask.request.form.getlist("fields[]")
    output_format: str = flask.request.form["output_format"]
    licenses: list[str] = flask.request.form.getlist("licenses")
    if not selected_sources or not selected_fields:
        return flask.render_template("400.html"), 400
    logging.info("Selected sources: %s", selected_sources)
    logging.info("Selected fields: %s", selected_fields)
    logging.info("Output format: %s", output_format)
    logging.info("Licenses: %s", licenses)
    # CELEX password gate.
    celex_password_env = os.environ.get("CELEX_PASSWORD")
    if celex_password_env:
        celex_selected = any(
            s in selected_sources
            for s in ("celexfreq", "celexfeat", "celexpron")
        )
        if celex_selected:
            celex_password_form = flask.request.form.get("celex_password")
            if (
                not celex_password_form
                or celex_password_form != celex_password_env
            ):
                return flask.render_template("401.html"), 401
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if output_format == "long":
        columns = _build_tsv_columns(selected_fields)

        def tsv_stream() -> Generator[str, None, None]:
            yield from _generate_tsv(
                cursor, selected_sources, selected_fields, columns
            )
            conn.close()

        return flask.Response(
            flask.stream_with_context(tsv_stream()),
            mimetype="text/tab-separated-values",
            headers={
                "Content-Disposition":
                f'attachment; filename="citylex-{today}.tsv"'
            },
        )
    elif output_format == "wide":

        def json_stream() -> Generator[str, None, None]:
            yield from _generate_json(
                cursor, selected_sources, selected_fields
            )
            conn.close()

        return flask.Response(
            flask.stream_with_context(json_stream()),
            mimetype="application/json",
            headers={
                "Content-Disposition":
                f'attachment; filename="citylex-{today}.json"'
            },
        )
    conn.close()
    return flask.render_template("400.html"), 400


if __name__ == "__main__":
    app.run()
