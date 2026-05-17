"""CityLex Flask web application."""

import csv
import datetime
import io
import json
import logging
import math
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

import flask

from citylex import features, xsampa, zipf

DB_PATH = "citylex.db"
FREQUENCY_PRECISION = 6


class _SetEncoder(json.JSONEncoder):
    """JSON encoder that converts sets to sorted lists."""

    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)


def _neg_logprob(raw_freq: int, total_words: int) -> float:
    if raw_freq > 0:
        return -math.log10(raw_freq / total_words)
    return math.inf


def _flatten(maybe_list: Union[str, List[str], None]) -> Optional[str]:
    if isinstance(maybe_list, list):
        return ",".join(maybe_list)
    return maybe_list


def _data_to_tsv(
    cursor: sqlite3.Cursor,
    writer: csv.DictWriter,
    source_table: str,
    columns: List[str],
    where: str = "",
) -> None:
    """Fetches and writes data from the specified SQL table.

    Args:
        cursor: The SQLite cursor object.
        writer: The TSV DictWriter object.
        source_table: The name of the database table to query.
        columns: A list of database column names to fetch.
        where: An optional SQL WHERE clause.
    """
    query = f"SELECT {', '.join(columns)} FROM {source_table}"
    if where:
        query += f" WHERE {where}"
    cursor.execute(query)
    for row in cursor:
        row_dict = dict(zip(columns, row))
        writer.writerow(row_dict)


def _wikipron_data_to_tsv(
    cursor: sqlite3.Cursor,
    writer: csv.DictWriter,
    selected_fields: List[str],
    uk_or_us: str,
) -> None:
    # uk_or_us must be capitalized: "UK" or "US"
    cursor.execute(
        "SELECT SUM(raw_frequency) FROM frequency WHERE source = ?", (source,)
    )
    for wordform, source, ipa_pron in cursor:
        row_dict = {"wordform": wordform, "source": source}
        if f"wikipron{uk_or_us}_IPA" in selected_fields:
            row_dict["IPA_pronunciation"] = ipa_pron
        if f"wikipron{uk_or_us}_XSAMPA" in selected_fields:
            row_dict["XSAMPA_pronunciation"] = xsampa.ipa_to_xsampa(ipa_pron)
        writer.writerow(row_dict)


def _subtlex_data_to_tsv(
    cursor: sqlite3.Cursor,
    writer: csv.DictWriter,
    selected_fields: List[str],
    uk_or_us: str,
) -> None:
    """Fetches and writes frequency data for a given SUBTLEX source.

    Args:
        cursor: The SQLite cursor object.
        writer: The TSV DictWriter object.
        selected_fields: The list of fields selected by the user.
        uk_or_us: Either 'UK' or 'US' to specify the SUBTLEX source.
    """
    source_name = f"SUBTLEX-{uk_or_us}"
    field_prefix = f"subtlex{uk_or_us}"
    # Builds base columns.
    columns = ["wordform", "source"]
    if f"{field_prefix}_raw_frequency" in selected_fields:
        columns.append("raw_frequency")
    if f"{field_prefix}_freq_per_million" in selected_fields:
        columns.append("freq_per_million")
    # Gets total words for logprob/zipf if needed.
    total_words = 0
    if (
        f"{field_prefix}_logprob" in selected_fields
        or f"{field_prefix}_zipf" in selected_fields
    ):
        cursor.execute(
            "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = 'CELEX'"
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
            "SELECT wordform, pronunciation FROM pronunciation WHERE source = 'CELEX' AND standard = 'DISC'"
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
    writer: csv.DictWriter[str],
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
        "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = ?",
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


app = flask.Flask(__name__)


@app.route("/", methods=["GET"])
def get() -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM frequency WHERE source = 'CELEX' LIMIT 1")
    return flask.render_template(
        "index.html",
        celex_present=cursor.fetchone() is not None,
        password_set="CELEX_PASSWORD" in os.environ,
    )
    for db_row in cursor:
        row = dict(zip(cols, db_row))
        yield _csv_row(writer, buf, row)


@app.route("/", methods=["POST"])
def post() -> Union[flask.Response, Tuple[str, int]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Extracts form data.
    selected_sources = flask.request.form.getlist("sources[]")
    selected_fields = flask.request.form.getlist("fields[]")
    output_format = flask.request.form["output_format"]
    licenses = flask.request.form.getlist("licenses")
    if not selected_sources or not selected_fields:
        return flask.render_template("400.html"), 400
    # Logs user selections.
    logging.info(f"Selected sources: {selected_sources}")
    logging.info(f"Selected fields: {selected_fields}")
    logging.info(f"Output format: {output_format}")
    logging.info(f"Licenses: {licenses}")
    # Password protects CELEX data if present.
    celex_password_env = os.environ.get("CELEX_PASSWORD")
    if celex_password_env:
        celex_sources_selected = any(
            s in selected_sources
            for s in ["celexfreq", "celexfeat", "celexpron"]
        )
        if celex_sources_selected:
            celex_password_form = flask.request.form.get("celex_password")
            if (
                not celex_password_form
                or celex_password_form != celex_password_env
            ):
                return flask.render_template("401.html"), 401
    # Builds TSV column headers.
    columns = ["wordform", "source"]
    if (
        "subtlexUS_raw_frequency" in selected_fields
        or "subtlexUK_raw_frequency" in selected_fields
        or "celexfreq_raw_frequency" in selected_fields
    ):
        columns.append("raw_frequency")
    if (
        "subtlexUS_freq_per_million" in selected_fields
        or "subtlexUK_freq_per_million" in selected_fields
        or "celexfreq_freq_per_million" in selected_fields
    ):
        columns.append("freq_per_million")
    if (
        "subtlexUK_logprob" in selected_fields
        or "subtlexUS_logprob" in selected_fields
        or "celexfreq_logprob" in selected_fields
    ):
        columns.append("-logprob")
    if (
        "subtlexUK_zipf" in selected_fields
        or "subtlexUS_zipf" in selected_fields
        or "celexfreq_zipf" in selected_fields
    ):
        columns.append("zipf")
    if (
        "wikipronUS_IPA" in selected_fields
        or "wikipronUK_IPA" in selected_fields
    ):
        columns.append("IPA_pronunciation")
    if (
        "wikipronUS_XSAMPA" in selected_fields
        or "wikipronUK_XSAMPA" in selected_fields
    ):
        columns.append("XSAMPA_pronunciation")
    if "celex_DISC" in selected_fields:
        columns.append("DISC_pronunciation")
    if (
        "udlex_CELEXtags" in selected_fields
        or "um_CELEXtags" in selected_fields
        or "celex_CELEXtags" in selected_fields
    ):
        columns.append("celex_tags")
    if (
        "udlex_UDtags" in selected_fields
        or "um_UDtags" in selected_fields
        or "celex_UDtags" in selected_fields
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


def _add_to_word_entry(
    entry: dict[str, set[Any]], key: str, value: Any
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
    aggregated: dict[str, dict[str, set[Any]]] = {}

    def add(wordform: str, key: str, value: Any) -> None:
        _add_to_word_entry(aggregated.setdefault(wordform, {}), key, value)

    for db_source, field_prefix in (
        ("SUBTLEX-UK", "subtlexUK"),
        ("SUBTLEX-US", "subtlexUS"),
        ("CELEX", "celexfreq"),
    ):
        columns.append("um_tags")
    if "elp_segmentation" in selected_fields:
        columns.append("segmentation")
    if "elp_nmorph" in selected_fields:
        columns.append("nmorph")
    # TSV option.
    if output_format == "long":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        # Fetches and writes CELEX data; we do this all at once.
        if any(
            s in selected_sources
            for s in ["celexfreq", "celexfeat", "celexpron"]
        ):
            celex_wordforms_data: dict[
                str, dict[str, Optional[Union[int, float, str]]]
            ] = {}
            # Fetches CELEX frequencies if selected.
            if "celexfreq" in selected_sources:
                cursor.execute(
                    "SELECT wordform, raw_frequency, freq_per_million "
                    "FROM frequency "
                    "WHERE source = 'CELEX'"
                )
                celex_freq_results = cursor.fetchall()
                # Calculates total_words for logprob and zipf for CELEX.
                cursor.execute(
                    "SELECT SUM(raw_frequency) "
                    "FROM frequency "
                    "WHERE source = 'CELEX'"
                )
                celex_total_words = cursor.fetchone()[0] or 0
                for (
                    wordform,
                    f"{db_source} (Frequency per million words)",
                    freq_per_mil,
                )
                cx = (
                    features.tag_to_tag("UD", "CELEX", ud_tags)
                    if "udlex_CELEXtags" in selected_fields
                    else None
                )
                # If a requested mapping is missing, skip the row.
                if ("udlex_UMtags" in selected_fields and not um) or (
                    "udlex_CELEXtags" in selected_fields and not cx
                ):
                    continue
                row = {"wordform": wordform, "source": source}
                if "udlex_CELEXtags" in selected_fields:
                    row["celex_tags"] = _flatten(cx)
                if "udlex_UMtags" in selected_fields:
                    row["um_tags"] = _flatten(um)
                if "udlex_UDtags" in selected_fields:
                    row["ud_tags"] = ud_tags
                # Skip rows with only wordform and source.
                if len(row) < 3:
                    continue
                writer.writerow(row)
        # Fetches and writes UniMorph data.
        if "UniMorph" in selected_sources:
            cursor.execute(
                "SELECT wordform, source, tags "
                "FROM features "
                "WHERE source = 'UniMorph'"
            )
            for wordform, source, um_tags in cursor:
                ud = (
                    features.tag_to_tag("UniMorph", "UD", um_tags)
                    if "um_UDtags" in selected_fields
                    else None
                )
                cx = (
                    features.tag_to_tag("UniMorph", "CELEX", um_tags)
                    if "um_CELEXtags" in selected_fields
                    else None
                )
                # If a requested mapping is missing, skip the row.
                if ("um_UDtags" in selected_fields and not ud) or (
                    "um_CELEXtags" in selected_fields and not cx
                ):
                    continue
                row = {"wordform": wordform, "source": source}
                if "um_UDtags" in selected_fields:
                    row["ud_tags"] = _flatten(ud)
                if "um_UMtags" in selected_fields:
                    row["um_tags"] = um_tags
                if "um_CELEXtags" in selected_fields:
                    row["celex_tags"] = _flatten(cx)
                # Skip rows with only wordform and source.
                if len(row) < 3:
                    continue
                writer.writerow(row)
        # Fetches and writes ELP segmentations.
        if "ELP" in selected_sources:
            elp_columns = ["wordform", "source"]
            if "elp_segmentation" in selected_fields:
                elp_columns.append("segmentation")
            if "elp_nmorph" in selected_fields:
                elp_columns.append("nmorph")
            _data_to_tsv(
                cursor, writer, "segmentation", elp_columns, "source = 'ELP'"
            )
        # Fetches and writes WikiPron-US data.
        if "WikiPron US" in selected_sources:
            _wikipron_data_to_tsv(cursor, writer, selected_fields, "US")
        # Fetches and writes WikiPron-UK data.
        if "WikiPron UK" in selected_sources:
            _wikipron_data_to_tsv(cursor, writer, selected_fields, "UK")
        # Sends the file as a response.
        contents = io.BytesIO(output.getvalue().encode("utf-8"))
        return flask.send_file(
            contents,
            mimetype="text/tab-separated-values",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.tsv",
        )
    # JSON option.
    elif output_format == "wide":
        aggregated_data: Dict[str, Any] = {}

        def add_to_aggregated_data(wordform, key, value):
            try:
                ptr1 = aggregated_data[wordform]
            except KeyError:
                ptr1 = aggregated_data[wordform] = {}
            try:
                ptr2 = ptr1[key]
            except KeyError:
                ptr2 = ptr1[key] = set()
            if isinstance(value, list):
                ptr2.update(value)
            else:
                ptr2.add(value)

        # Processes frequency data.
        for source, source_fieldname in [
            ("SUBTLEX-UK", "subtlexUK"),
            ("SUBTLEX-US", "subtlexUS"),
            ("CELEX", "celexfreq"),
        ]:
            if source_fieldname in selected_sources:
                # Total words for logprob and Zipf scale calculation
                cursor.execute(
                    "SELECT SUM(raw_frequency) "
                    "FROM frequency "
                    "WHERE source = ?",
                    (source,),
                )
            if f"{field_prefix}_zipf" in selected_fields:
                add(
                    wordform,
                    f"{db_source} (Zipf scale)",
                    round(
                        zipf.zipf_scale(raw_freq, total), FREQUENCY_PRECISION
                    ),
                )
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
                        add(
                            wordform,
                            "UDLexicons features (CELEX-style tags)",
                            cx,
                        )
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
                        add(
                            wordform,
                            "UniMorph features (CELEX-style tags)",
                            cx,
                        )
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
                    if um := features.tag_to_tag(
                        "CELEX", "UniMorph", celex_tags
                    ):
                        add(
                            wordform,
                            "CELEX features (UniMorph-style tags)",
                            um,
                        )
        if "ELP" in selected_sources:
            cursor.execute(
                "SELECT wordform, segmentation, nmorph FROM segmentation WHERE source = 'ELP'"
            )
            for wordform, segmentation, nmorph in cursor:
                if "elp_segmentation" in selected_fields:
                    add(wordform, "ELP (Segmentation)", segmentation)
                if "elp_nmorph" in selected_fields:
                    add(wordform, "ELP (Number of morphs)", nmorph)
        for source_key, field_prefix, ipa_label in (
            ("WikiPron US", "wikipronUS", "WikiPron US (IPA)"),
            ("WikiPron UK", "wikipronUK", "WikiPron UK (IPA)"),
        ):
            if source_key not in selected_sources:
                continue
            cursor.execute(
                "SELECT wordform, pronunciation FROM pronunciation WHERE source = ? AND standard = 'IPA'",
                (source_key,),
            )
            for wordform, pronunciation in cursor:
                if f"{field_prefix}_IPA" in selected_fields:
                    add(wordform, ipa_label, pronunciation)
                if f"{field_prefix}_XSAMPA" in selected_fields:
                    xsampa_label = ipa_label.replace("(IPA)", "(X-SAMPA)")
                    add(
                        wordform,
                        xsampa_label,
                        xsampa.ipa_to_xsampa(pronunciation),
                    )
        if "celexpron" in selected_sources:
            cursor.execute(
                "SELECT wordform, pronunciation FROM pronunciation WHERE source = 'CELEX' AND standard = 'DISC'"
            )
            for wordform, pronunciation in cursor:
                if "celex_DISC" in selected_fields:
                    add(wordform, "CELEX (DISC)", pronunciation)
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


def _stream_tsv_response(
    selected_sources: list[str],
    selected_fields: list[str],
    columns: list[str],
    today: str,
) -> Response:
    """Generates a streaming TSV response and guarantees DB connection closure."""

    def tsv_stream() -> Generator[str, None, None]:
        try:
            cursor = conn.cursor()
            yield from _generate_tsv(
                cursor, selected_sources, selected_fields, columns
            )
        finally:
            conn.close()

    conn = sqlite3.connect(DB_PATH)
    return Response(
        stream_with_context(tsv_stream()),
        mimetype="text/tab-separated-values",
        headers={
            "Content-Disposition": f'attachment; filename="citylex-{today}.tsv"'
        },
    )


def _stream_json_response(
    selected_sources: list[str],
    selected_fields: list[str],
    today: str,
) -> Response:
    """Generates a streaming JSON response and guarantees DB connection closure."""

    def json_stream() -> Generator[str, None, None]:
        try:
            cursor = conn.cursor()
            yield from _generate_json(
                cursor, selected_sources, selected_fields
            )
        finally:
            conn.close()

    conn = sqlite3.connect(DB_PATH)
    return Response(
        stream_with_context(json_stream()),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="citylex-{today}.json"'
        },
    )


app = Flask(__name__)


@app.route("/", methods=["GET"])
def get() -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM frequency WHERE source = 'CELEX' LIMIT 1"
        )
        celex_present = cursor.fetchone() is not None
        return render_template(
            "index.html",
            celex_present=celex_present,
            password_set="CELEX_PASSWORD" in os.environ,
        )
    finally:
        conn.close()


@app.route("/", methods=["POST"])
def post() -> Response | tuple[str, int]:
    selected_sources: list[str] = request.form.getlist("sources[]")
    selected_fields: list[str] = request.form.getlist("fields[]")
    output_format: str = request.form["output_format"]
    licenses: list[str] = request.form.getlist("licenses")
    if not selected_sources or not selected_fields:
        return render_template("400.html"), 400
    logging.info("Selected sources: %s", selected_sources)
    logging.info("Selected fields: %s", selected_fields)
    logging.info("Output format: %s", output_format)
    logging.info("Licenses: %s", licenses)
    celex_password_env = os.environ.get("CELEX_PASSWORD")
    if celex_password_env:
        celex_selected = any(
            s in selected_sources
            for s in ("celexfreq", "celexfeat", "celexpron")
        )
        return flask.send_file(
            contents,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.json",
        )
    # Unreachable.
    return "", 500


if __name__ == "__main__":
    app.run()
