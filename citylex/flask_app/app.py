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


def freq_data_to_csv(cursor, writer, source_name, selected_fields, field_prefix):
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
    columns = ["wordform", "source"]
    if f"{field_prefix}_raw_frequency" in selected_fields:
        columns.append("raw_frequency")
    if f"{field_prefix}_freq_per_million" in selected_fields:
        columns.append("freq_per_million")

    # Get total words for logprob/zipf if needed
    if (
        f"{field_prefix}_logprob" in selected_fields
        or f"{field_prefix}_zipf" in selected_fields
    ):
        cursor.execute(
            "SELECT SUM(raw_frequency) FROM frequency WHERE source = ?", (source_name,)
        )
        total_words = cursor.fetchone()[0] or 0
    else:
        total_words = None

    cursor.execute(f"SELECT {', '.join(columns)} FROM frequency WHERE source = '{source_name}'")
    for row in cursor:
        row_dict = dict(zip(columns, row))
        raw_frequency = row_dict.get("raw_frequency", 0)

        if f"{field_prefix}_logprob" in selected_fields:
            row_dict["logprob"] = (
                math.log10(raw_frequency / total_words)
                if raw_frequency > 0 and total_words and total_words > 0
                else float("-inf")
            )
        if f"{field_prefix}_zipf" in selected_fields:
            row_dict["zipf"] = (
                zipf.zipf_scale(raw_frequency, total_words)
                if total_words and total_words > 0
                else None
            )

        writer.writerow(row_dict)


app = Flask(__name__)


@app.route("/", methods=["GET"])
def get():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM frequency WHERE source = 'CELEX' LIMIT 1"
        )
        celex_present = cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"Error querying CELEX data: {e}")
        celex_present = 0

    password_set = "CELEX_PASSWORD" in os.environ

    return render_template("index.html", celex_present=celex_present, password_set=password_set)


@app.route("/", methods=["POST"])
def post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    selected_sources = request.form.getlist("sources[]")
    selected_fields = request.form.getlist("fields[]")
    output_format = request.form["output_format"]
    licenses = request.form.getlist("licenses")

    if not selected_sources or not selected_fields:
        return render_template("400.html"), 400

    logging.info(f"Selected sources: {selected_sources}")
    logging.info(f"Selected fields: {selected_fields}")
    logging.info(f"Output format: {output_format}")
    logging.info(f"Licenses: {licenses}")

    if os.environ.get("CELEX_PASSWORD"):
        celex_sources_selected = any(s in selected_sources for s in ["celexfreq", "CELEX_feat", "CELEX_pron"])
        if celex_sources_selected:
            celex_password_env = os.environ.get("CELEX_PASSWORD")
            celex_password_form = request.form.get("celex_password")

            if not celex_password_form or celex_password_form != celex_password_env:
                return render_template("401.html"), 401

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
        columns.append("logprob")
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

    if output_format == "long":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t")
        writer.writeheader()

        # Fetches and writes SUBTLEX-US data
        if "subtlexuk" in selected_sources:
            freq_data_to_csv(cursor, writer, "SUBTLEX-UK", selected_fields, "subtlexuk")

        # Fetches and writes SUBTLEX-UK data
        if "subtlexus" in selected_sources:
            freq_data_to_csv(cursor, writer, "SUBTLEX-US", selected_fields, "subtlexus")
       
        # Feteches and writes CELEX frequency data
        if "celexfreq" in selected_sources:
            freq_data_to_csv(cursor, writer, "CELEX", selected_fields, "celexfreq")

        # Fetches and writes WikiPron-US data
        if "WikiPron US" in selected_sources:
            wp_us_columns = ["wordform", "source", "pronunciation"]
            _data_to_csv(
                cursor,
                writer,
                "pronunciation",
                wp_us_columns,
                "source = 'WikiPron US' AND standard = 'IPA'",
            )

        # Fetches and writes WikiPron-UK data
        if "WikiPron UK" in selected_sources:
            wp_uk_columns = ["wordform", "source", "pronunciation"]
            _data_to_csv(
                cursor,
                writer,
                "pronunciation",
                wp_uk_columns,
                "source = 'WikiPron UK' AND standard = 'IPA'",
            )

        if "CELEX_pron" in selected_sources:
            celex_pron_columns = ["wordform", "source", "pronunciation"]
            _data_to_csv(
                cursor,
                writer,
                "pronunciation",
                celex_pron_columns,
                "source = 'CELEX' and standard = 'DISC'",
            )

        # Fetches and writes UDLexicons data
        if "UDLexicons" in selected_sources:
            cursor.execute("SELECT wordform, source, tags FROM features WHERE source = 'UDLexicons'")
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

        # Fetches and writes UniMorph data
        if "UniMorph" in selected_sources:
            cursor.execute("SELECT wordform, source, tags FROM features WHERE source = 'UniMorph'")
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

        # Fetches and writes CELEX features data
        if "CELEX_feat" in selected_sources:
            cursor.execute("SELECT wordform, source, tags FROM features WHERE source = 'CELEX'")
            for row in cursor:
                wordform, source, celex_tags = row
                row_dict = {"wordform": wordform, "source": source}

                if "celex_UDtags" in selected_fields:
                    row_dict["ud_tags"] = features.tag_to_tag(
                        "CELEX", "UD", celex_tags
                    )
                if "celex_UMtags" in selected_fields:
                    row_dict["um_tags"] = features.tag_to_tag(
                        "CELEX", "UniMorph", celex_tags
                    )
                if "celex_CELEXtags" in selected_fields:
                    row_dict["celex_tags"] = celex_tags

                writer.writerow(row_dict)

        # Fetches and writes ELP segmentations
        if "ELP" in selected_sources:
            elp_columns = ["wordform", "source"]
            if "elp_segmentation" in selected_fields:
                elp_columns.append("segmentation")
            if "elp_nmorph" in selected_fields:
                elp_columns.append("nmorph")
            _data_to_csv(
                cursor, writer, "segmentation", elp_columns, "source = 'ELP'"
            )

        # Sends the file as a response
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/tab-separated-values",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.tsv",
        )

    elif output_format == "wide":
        aggregated_data = {}

        def add_to_aggregated_data(wordform, key, value):
            if wordform not in aggregated_data:
                aggregated_data[wordform] = {}
            if key not in aggregated_data[wordform]:
                aggregated_data[wordform][key] = []
            if value is not None:
                aggregated_data[wordform][key].append(value)

        # Process frequency data
        for source, source_fieldname in [
            ("SUBTLEX-UK", "subtlexuk"),
            ("SUBTLEX-US", "subtlexus"),
            ("CELEX", "celexfreq"),
        ]:
            if source_fieldname in selected_sources:
                # Total words for logprob and Zipf scale calculation
                cursor.execute(
                    "SELECT SUM(raw_frequency) FROM frequency WHERE source = ?", (source, )
                )
                total_words = cursor.fetchone()[0]

                cursor.execute("SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = ?", (source, ))
                for wordform, raw_frequency, freq_per_million in cursor:
                    if f"{source_fieldname}_raw_frequency" in selected_fields:
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (Raw frequency)",
                            raw_frequency,
                        )
                    if f"{source_fieldname}_freq_per_million" in selected_fields:
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (Frequency per million words)",
                            freq_per_million,
                        )
                    if f"{source_fieldname}_logprob" in selected_fields:
                        logprob = (
                            math.log10(raw_frequency / total_words)
                            if raw_frequency > 0 and total_words and total_words > 0
                            else float("-inf")
                        )
                        add_to_aggregated_data(
                            wordform,
                            f"{source} (log10 probability)",
                            logprob,
                        )
                    if f"{source_fieldname}_zipf" in selected_fields:
                        zipf_val = (
                            zipf.zipf_scale(raw_frequency, total_words)
                            if total_words and total_words > 0
                            else None
                        )
                        add_to_aggregated_data(
                            wordform, f"{source} (Zipf scale)", zipf_val
                        )

        # Process UDLexicons data
        if "UDLexicons" in selected_sources:
            cursor.execute("SELECT wordform, tags FROM features WHERE source = 'UDLexicons'")
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

        # Process UniMorph data
        if "UniMorph" in selected_sources:
            cursor.execute("SELECT wordform, tags FROM features WHERE source = 'UniMorph'")
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

        # Process CELEX features data
        if "CELEX_feat" in selected_sources:
            cursor.execute("SELECT wordform, tags FROM features WHERE source = 'CELEX'")
            for wordform, celex_tags in cursor:
                if "celex_UDtags" in selected_fields:
                    ud_tags = features.tag_to_tag("CELEX", "UD", celex_tags)
                    add_to_aggregated_data(
                        wordform, "CELEX (Universal Dependency-style tags)", ud_tags
                    )
                if "celex_UMtags" in selected_fields:
                    um_tags = features.tag_to_tag("CELEX", "UniMorph", celex_tags)
                    add_to_aggregated_data(
                        wordform, "CELEX (UniMorph-style tags)", um_tags
                    )
                if "celex_CELEXtags" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "CELEX (CELEX tags)", celex_tags
                    )

        # Process ELP segmentations
        if "ELP" in selected_sources:
            cursor.execute("SELECT wordform, segmentation, nmorph FROM segmentation WHERE source = 'ELP'")
            for wordform, segmentation, nmorph in cursor:
                if "elp_segmentation" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "ELP (Segmentation)", segmentation
                    )
                if "elp_nmorph" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "ELP (Number of morphs)", nmorph
                    )

        # Process pronunciation data
        for source_key, field_prefix, display_name in [
            ("WikiPron US", "wikipronus", "WikiPron US (IPA)"),
            ("WikiPron UK", "wikipronuk", "WikiPron UK (IPA)"),
            ("CELEX_pron", "celex_DISC", "CELEX (DISC)"),
        ]:
            if source_key in selected_sources:
                # For CELEX, filter by standard = 'DISC'
                where_clause = "standard = 'IPA'" if source_key.startswith("WikiPron") else "standard = 'DISC'"
                cursor.execute(f"SELECT wordform, pronunciation FROM pronunciation WHERE source = '{source_key.split('_')[0]}' AND {where_clause}")
                for wordform, pronunciation in cursor:
                    # Check if the specific field for this pronunciation type was selected
                    if (field_prefix == "wikipronus" and "wikipronus_IPA" in selected_fields) or \
                        (field_prefix == "wikipronuk" and "wikipronuk_IPA" in selected_fields) or \
                        (field_prefix == "celex_DISC" and "celex_DISC" in selected_fields):
                        add_to_aggregated_data(
                            wordform, display_name, pronunciation
                        )

        json_output = io.StringIO()
        json.dump(aggregated_data, json_output, indent=4)
        json_output.seek(0)

        return send_file(
            io.BytesIO(json_output.getvalue().encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.json",
        )


if __name__ == "__main__":
    app.run()
