import csv
import datetime
import io
import json
import logging
import math
import os
import sqlite3

from flask import Flask, render_template, request, send_file

from citylex import features, zipf

DB_PATH = "citylex.db"


def _neg_logprob(raw_freq, total_words):
    if raw_freq > 0:
        return round(-math.log10(raw_freq / total_words), 6)
    else:
        return math.inf


def _data_to_csv(cursor, writer, source_table, columns, where=""):
    """
    Fetches and writes data from the specified SQL table for
    given columns and WHERE criteria.

    Args:
        cursor: The SQLite cursor object.
        writer: The CSV DictWriter object.
        source_table (str): The name of the database table to query.
        columns (list): A list of database column names to fetch.
        where (str, optional): An SQL WHERE clause. Defaults to "".
    """
    query = f"SELECT {', '.join(columns)} FROM {source_table}"
    if where:
        query += f" WHERE {where}"
    cursor.execute(query)
    for row in cursor:
        row_dict = dict(zip(columns, row))
        writer.writerow(row_dict)


def _subtlex_data_to_csv(
    cursor, writer, source_name, selected_fields, field_prefix
):
    """
    Fetches and writes frequency data for a given frequency source,
    calculating logprob and zipf if requested.

    Args:
        cursor: The SQLite cursor object.
        writer: The CSV DictWriter object.
        source_name (str): The value in the 'source' column (e.g., 'SUBTLEX-UK', 'CELEX').
        selected_fields (list): The list of fields selected by the user.
        field_prefix (str): Prefix for field names (e.g., 'subtlexuk', 'subtlexus', 'celexfreq').
    """
    # Builds base columns.
    columns = ["wordform", "source"]
    if f"{field_prefix}_raw_frequency" in selected_fields:
        columns.append("raw_frequency")
    if f"{field_prefix}_freq_per_million" in selected_fields:
        columns.append("freq_per_million")
    # Gets total words for logprob/zipf if needed.
    if (
        f"{field_prefix}_logprob" in selected_fields
        or f"{field_prefix}_zipf" in selected_fields
    ):
        cursor.execute(
            "SELECT SUM(raw_frequency) FROM frequency WHERE source = ?",
            (source_name,),
        )
        total_words = cursor.fetchone()[0] or 0
    else:
        total_words = None
    # Fetches frequency data and writes rows.
    cursor.execute(
        f"SELECT {', '.join(columns)}, raw_frequency FROM frequency WHERE source = '{source_name}'"
    )
    for row in cursor:
        raw_freq = row[-1]
        row_dict = dict(zip(columns, row))
        if f"{field_prefix}_logprob" in selected_fields:
            row_dict["-logprob"] = _neg_logprob(raw_freq, total_words)
        if f"{field_prefix}_zipf" in selected_fields:
            zipf_value = (
                zipf.zipf_scale(raw_freq, total_words)
                if total_words and total_words > 0
                else None
            )
            row_dict["zipf"] = (
                round(zipf_value, 6) if zipf_value is not None else None
            )
        writer.writerow(row_dict)


app = Flask(__name__)


@app.route("/", methods=["GET"])
def get():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM frequency WHERE source = 'CELEX' LIMIT 1")
    celex_present = cursor.fetchone() is not None
    password_set = "CELEX_PASSWORD" in os.environ
    return render_template(
        "index.html", celex_present=celex_present, password_set=password_set
    )


@app.route("/", methods=["POST"])
def post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Extracts form data.
    selected_sources = request.form.getlist("sources[]")
    selected_fields = request.form.getlist("fields[]")
    output_format = request.form["output_format"]
    licenses = request.form.getlist("licenses")
    if not selected_sources or not selected_fields:
        return render_template("400.html"), 400
    # Logs user selections.
    logging.info(f"Selected sources: {selected_sources}")
    logging.info(f"Selected fields: {selected_fields}")
    logging.info(f"Output format: {output_format}")
    logging.info(f"Licenses: {licenses}")
    # Password protects CELEX data if present.
    if os.environ.get("CELEX_PASSWORD"):
        celex_sources_selected = any(
            s in selected_sources
            for s in ["celexfreq", "CELEX_feat", "CELEX_pron"]
        )
        if celex_sources_selected:
            celex_password_env = os.environ.get("CELEX_PASSWORD")
            celex_password_form = request.form.get("celex_password")
            if (
                not celex_password_form
                or celex_password_form != celex_password_env
            ):
                return render_template("401.html"), 401
    # Builds CSV column headers.
    columns = ["wordform", "source"]
    if (
        "subtlexus_raw_frequency" in selected_fields
        or "subtlexuk_raw_frequency" in selected_fields
        or "celexfreq_raw_frequency" in selected_fields
    ):
        columns.append("raw_frequency")
    if (
        "subtlexus_freq_per_million" in selected_fields
        or "subtlexuk_freq_per_million" in selected_fields
        or "celexfreq_freq_per_million" in selected_fields
    ):
        columns.append("freq_per_million")
    if (
        "subtlexuk_logprob" in selected_fields
        or "subtlexus_logprob" in selected_fields
        or "celexfreq_logprob" in selected_fields
    ):
        columns.append("-logprob")
    if (
        "subtlexuk_zipf" in selected_fields
        or "subtlexus_zipf" in selected_fields
        or "celexfreq_zipf" in selected_fields
    ):
        columns.append("zipf")
    if (
        "wikipronus_IPA" in selected_fields
        or "wikipronuk_IPA" in selected_fields
        or "celex_DISC" in selected_fields
    ):
        columns.append("pronunciation")
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
        columns.append("ud_tags")
    if (
        "udlex_UMtags" in selected_fields
        or "um_UMtags" in selected_fields
        or "celex_UMtags" in selected_fields
    ):
        columns.append("um_tags")
    if "elp_segmentation" in selected_fields:
        columns.append("segmentation")
    if "elp_nmorph" in selected_fields:
        columns.append("nmorph")
    # TSV option
    if output_format == "long":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        # Fetches and writes SUBTLEX-US data.
        if "subtlexuk" in selected_sources:
            _subtlex_data_to_csv(
                cursor, writer, "SUBTLEX-UK", selected_fields, "subtlexuk"
            )
        # Fetches and writes SUBTLEX-UK data.
        if "subtlexus" in selected_sources:
            _subtlex_data_to_csv(
                cursor, writer, "SUBTLEX-US", selected_fields, "subtlexus"
            )
        # Fetches and writes WikiPron-US data.
        if "WikiPron US" in selected_sources:
            wp_us_columns = ["wordform", "source", "pronunciation"]
            _data_to_csv(
                cursor,
                writer,
                "pronunciation",
                wp_us_columns,
                "source = 'WikiPron US' AND standard = 'IPA'",
            )
        # Fetches and writes WikiPron-UK data.
        if "WikiPron UK" in selected_sources:
            wp_uk_columns = ["wordform", "source", "pronunciation"]
            _data_to_csv(
                cursor,
                writer,
                "pronunciation",
                wp_uk_columns,
                "source = 'WikiPron UK' AND standard = 'IPA'",
            )
        # Fetches and writes CELEX data.
        if any(
            s in selected_sources
            for s in ["celexfreq", "CELEX_feat", "CELEX_pron"]
        ):
            celex_wordforms_data = {}
            # Fetches CELEX frequencies if selected.
            if "celexfreq" in selected_sources:
                cursor.execute(
                    "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = 'CELEX'"
                )
                celex_freq_results = cursor.fetchall()
                # Calculates total_words for logprob and zipf for CELEX.
                cursor.execute(
                    "SELECT SUM(raw_frequency) FROM frequency WHERE source = 'CELEX'"
                )
                celex_total_words = cursor.fetchone()[0] or 0
                for (
                    wordform,
                    raw_frequency,
                    freq_per_million,
                ) in celex_freq_results:
                    if wordform not in celex_wordforms_data:
                        celex_wordforms_data[wordform] = {"source": "CELEX"}

                    if "celexfreq_raw_frequency" in selected_fields:
                        celex_wordforms_data[wordform][
                            "raw_frequency"
                        ] = raw_frequency
                    if "celexfreq_freq_per_million" in selected_fields:
                        celex_wordforms_data[wordform][
                            "freq_per_million"
                        ] = freq_per_million
                    if "celexfreq_logprob" in selected_fields:
                        celex_wordforms_data[wordform]["-logprob"] = (
                            _neg_logprob(raw_frequency, celex_total_words)
                        )
                    if "celexfreq_zipf" in selected_fields:
                        zipf_value = (
                            zipf.zipf_scale(raw_frequency, celex_total_words)
                            if celex_total_words > 0
                            else None
                        )
                        celex_wordforms_data[wordform]["zipf"] = (
                            round(zipf_value, 6)
                            if zipf_value is not None
                            else None
                        )
            # Fetches CELEX features if selected.
            if "CELEX_feat" in selected_sources:
                cursor.execute(
                    "SELECT wordform, tags FROM features WHERE source = 'CELEX'"
                )
                celex_feat_results = cursor.fetchall()
                for wordform, celex_tags in celex_feat_results:
                    if wordform not in celex_wordforms_data:
                        celex_wordforms_data[wordform] = {"source": "CELEX"}

                    if "celex_CELEXtags" in selected_fields:
                        celex_wordforms_data[wordform][
                            "celex_tags"
                        ] = celex_tags
                    if "celex_UDtags" in selected_fields:
                        celex_wordforms_data[wordform]["ud_tags"] = (
                            features.tag_to_tag("CELEX", "UD", celex_tags)
                        )
                    if "celex_UMtags" in selected_fields:
                        celex_wordforms_data[wordform]["um_tags"] = (
                            features.tag_to_tag(
                                "CELEX", "UniMorph", celex_tags
                            )
                        )
            # Fetches CELEX pronunciations if selected.
            if "CELEX_pron" in selected_sources:
                cursor.execute(
                    "SELECT wordform, pronunciation FROM pronunciation WHERE source = 'CELEX' AND standard = 'DISC'"
                )
                celex_pron_results = cursor.fetchall()
                for wordform, pronunciation in celex_pron_results:
                    if wordform not in celex_wordforms_data:
                        celex_wordforms_data[wordform] = {"source": "CELEX"}
                    if "celex_DISC" in selected_fields:
                        celex_wordforms_data[wordform][
                            "pronunciation"
                        ] = pronunciation
            # Writes consolidated CELEX data to CSV.
            for wordform, data in celex_wordforms_data.items():
                row_to_write = {
                    "wordform": wordform,
                    "source": data["source"],
                }
                # Populates fields.
                if (
                    "celexfreq_raw_frequency" in selected_fields
                    and "raw_frequency" in data
                ):
                    row_to_write["raw_frequency"] = data["raw_frequency"]
                if (
                    "celexfreq_freq_per_million" in selected_fields
                    and "freq_per_million" in data
                ):
                    row_to_write["freq_per_million"] = data["freq_per_million"]
                if (
                    "celexfreq_logprob" in selected_fields
                    and "-logprob" in data
                ):
                    row_to_write["-logprob"] = data["-logprob"]
                if "celexfreq_zipf" in selected_fields and "zipf" in data:
                    row_to_write["zipf"] = data["zipf"]
                if (
                    "celex_CELEXtags" in selected_fields
                    and "celex_tags" in data
                ):
                    row_to_write["celex_tags"] = data["celex_tags"]
                if "celex_UDtags" in selected_fields and "ud_tags" in data:
                    row_to_write["ud_tags"] = data["ud_tags"]
                if "celex_UMtags" in selected_fields and "um_tags" in data:
                    row_to_write["um_tags"] = data["um_tags"]
                if "celex_DISC" in selected_fields and "pronunciation" in data:
                    row_to_write["pronunciation"] = data["pronunciation"]
                writer.writerow(row_to_write)
        # Fetches and writes UDLexicons data.
        if "UDLexicons" in selected_sources:
            cursor.execute(
                "SELECT wordform, source, tags FROM features WHERE source = 'UDLexicons'"
            )
            for row in cursor:
                wordform, source, ud_tags = row
                row_dict = {"wordform": wordform, "source": source}
                if "udlex_UDtags" in selected_fields:
                    row_dict["ud_tags"] = ud_tags
                if "udlex_UMtags" in selected_fields:
                    row_dict["um_tags"] = features.tag_to_tag(
                        "UD", "UniMorph", ud_tags
                    )
                if "udlex_CELEXtags" in selected_fields:
                    row_dict["celex_tags"] = features.tag_to_tag(
                        "UD", "CELEX", ud_tags
                    )
                writer.writerow(row_dict)
        # Fetches and writes UniMorph data.
        if "UniMorph" in selected_sources:
            cursor.execute(
                "SELECT wordform, source, tags FROM features WHERE source = 'UniMorph'"
            )
            for row in cursor:
                wordform, source, um_tags = row
                row_dict = {"wordform": wordform, "source": source}

                if "um_UDtags" in selected_fields:
                    row_dict["ud_tags"] = features.tag_to_tag(
                        "UniMorph", "UD", um_tags
                    )
                if "um_UMtags" in selected_fields:
                    row_dict["um_tags"] = um_tags
                if "um_CELEXtags" in selected_fields:
                    row_dict["celex_tags"] = features.tag_to_tag(
                        "UniMorph", "CELEX", um_tags
                    )
                writer.writerow(row_dict)
        # Fetches and writes ELP segmentations.
        if "ELP" in selected_sources:
            elp_columns = ["wordform", "source"]
            if "elp_segmentation" in selected_fields:
                elp_columns.append("segmentation")
            if "elp_nmorph" in selected_fields:
                elp_columns.append("nmorph")
            _data_to_csv(
                cursor, writer, "segmentation", elp_columns, "source = 'ELP'"
            )
        # Sends the file as a response.
        contents = io.BytesIO(output.getvalue().encode("utf-8"))
        return send_file(
            contents,
            mimetype="text/tab-separated-values",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.tsv",
        )
    # JSON option
    elif output_format == "wide":
        aggregated_data = {}
        def add_to_aggregated_data(wordform, key, value):
            if wordform not in aggregated_data:
                aggregated_data[wordform] = {}
            if key not in aggregated_data[wordform]:
                aggregated_data[wordform][key] = []
            if value is not None:
                aggregated_data[wordform][key].append(value)
        # Processes frequency data.
        for source, source_fieldname in [
            ("SUBTLEX-UK", "subtlexuk"),
            ("SUBTLEX-US", "subtlexus"),
            ("CELEX", "celexfreq"),
        ]:
            if source_fieldname in selected_sources:
                # Total words for logprob and Zipf scale calculation
                cursor.execute(
                    "SELECT SUM(raw_frequency) FROM frequency WHERE source = ?",
                    (source,),
                )
                total_words = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = ?",
                    (source,),
                )
                for wordform, raw_frequency, freq_per_million in cursor:
                    if f"{source_fieldname}_raw_frequency" in selected_fields:
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (Raw frequency)",
                            raw_frequency,
                        )
                    if (
                        f"{source_fieldname}_freq_per_million"
                        in selected_fields
                    ):
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (Frequency per million words)",
                            freq_per_million,
                        )
                    if f"{source_fieldname}_logprob" in selected_fields:
                        logprob = _neg_logprob(raw_frequency, total_words)
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (-log10 probability)",
                            logprob,
                        )
                    if f"{source_fieldname}_zipf" in selected_fields:
                        zipf_val = (
                            zipf.zipf_scale(raw_frequency, total_words)
                            if total_words and total_words > 0
                            else None
                        )
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (Zipf scale)",
                            (
                                round(zipf_val, 6)
                                if zipf_val is not None
                                else None
                            ),
                        )
        # Processes UDLexicons data.
        if "UDLexicons" in selected_sources:
            cursor.execute(
                "SELECT wordform, tags FROM features WHERE source = 'UDLexicons'"
            )
            for wordform, ud_tags in cursor:
                if "udlex_UDtags" in selected_fields:
                    add_to_aggregated_data(
                        wordform,
                        "UDLexicons (Universal Dependency-style tags)",
                        ud_tags,
                    )
                if "udlex_UMtags" in selected_fields:
                    um_tags = features.tag_to_tag("UD", "UniMorph", ud_tags)
                    add_to_aggregated_data(
                        wordform, "UDLexicons (UniMorph-style tags)", um_tags
                    )
                if "udlex_CELEXtags" in selected_fields:
                    celex_tags = features.tag_to_tag("UD", "CELEX", ud_tags)
                    add_to_aggregated_data(
                        wordform, "UDLexicons (CELEX tags)", celex_tags
                    )
        # Processes UniMorph data.
        if "UniMorph" in selected_sources:
            cursor.execute(
                "SELECT wordform, tags FROM features WHERE source = 'UniMorph'"
            )
            for wordform, um_tags in cursor:
                if "um_UDtags" in selected_fields:
                    ud_tags = features.tag_to_tag("UniMorph", "UD", um_tags)
                    add_to_aggregated_data(
                        wordform,
                        "UniMorph (Universal Dependency-style tags)",
                        ud_tags,
                    )
                if "um_UMtags" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "UniMorph (UniMorph-style tags)", um_tags
                    )
                if "um_CELEXtags" in selected_fields:
                    celex_tags = features.tag_to_tag(
                        "UniMorph", "CELEX", um_tags
                    )
                    add_to_aggregated_data(
                        wordform, "UniMorph (CELEX tags)", celex_tags
                    )
        # Processes CELEX features data.
        if "CELEX_feat" in selected_sources:
            cursor.execute(
                "SELECT wordform, tags FROM features WHERE source = 'CELEX'"
            )
            for wordform, celex_tags in cursor:
                if "celex_UDtags" in selected_fields:
                    ud_tags = features.tag_to_tag("CELEX", "UD", celex_tags)
                    add_to_aggregated_data(
                        wordform,
                        "CELEX (Universal Dependency-style tags)",
                        ud_tags,
                    )
                if "celex_UMtags" in selected_fields:
                    um_tags = features.tag_to_tag(
                        "CELEX", "UniMorph", celex_tags
                    )
                    add_to_aggregated_data(
                        wordform, "CELEX (UniMorph-style tags)", um_tags
                    )
                if "celex_CELEXtags" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "CELEX (CELEX tags)", celex_tags
                    )
        # Processes ELP segmentations.
        if "ELP" in selected_sources:
            cursor.execute(
                "SELECT wordform, segmentation, nmorph FROM segmentation WHERE source = 'ELP'"
            )
            for wordform, segmentation, nmorph in cursor:
                if "elp_segmentation" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "ELP (Segmentation)", segmentation
                    )
                if "elp_nmorph" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "ELP (Number of morphs)", nmorph
                    )
        # Processes pronunciation data.
        for source_key, field_prefix, display_name in [
            ("WikiPron US", "wikipronus", "WikiPron US (IPA)"),
            ("WikiPron UK", "wikipronuk", "WikiPron UK (IPA)"),
            ("CELEX_pron", "celex_DISC", "CELEX (DISC)"),
        ]:
            if source_key in selected_sources:
                # For CELEX, filters by standard = 'DISC'.
                where_clause = (
                    "standard = 'IPA'"
                    if source_key.startswith("WikiPron")
                    else "standard = 'DISC'"
                )
                cursor.execute(
                    f"SELECT wordform, pronunciation FROM pronunciation WHERE source = '{source_key.split('_')[0]}' AND {where_clause}"
                )
                for wordform, pronunciation in cursor:
                    # Checks if the specific field for this pronunciation type was selected.
                    if (
                        (
                            field_prefix == "wikipronus"
                            and "wikipronus_IPA" in selected_fields
                        )
                        or (
                            field_prefix == "wikipronuk"
                            and "wikipronuk_IPA" in selected_fields
                        )
                        or (
                            field_prefix == "celex_DISC"
                            and "celex_DISC" in selected_fields
                        )
                    ):
                        add_to_aggregated_data(
                            wordform, display_name, pronunciation
                        )
        # Sends the file as a response.
        contents = io.BytesIO(
            json.dumps(
                aggregated_data, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        )
        return send_file(
            contents,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.json",
        )


if __name__ == "__main__":
    app.run()
