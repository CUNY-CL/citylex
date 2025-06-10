import csv
import datetime
import io
import json
import logging
import math
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


def _subtlex_to_csv(cursor, writer, uk_or_us, selected_fields):
    """
    Fetches and writes data for SUBTLEX-US and SUBTLEX-UK.

    Args:
        cursor: The SQLite cursor object.
        writer: The CSV DictWriter object.
        uk_or_us (str): Either "uk" or "us" depending on the desired source.
        selected_fields (list): The list of fields selected by the user
            on the form.
    """
    if (
        f"subtlex{uk_or_us}_logprob" in selected_fields
        or f"subtlex{uk_or_us}_zipf" in selected_fields
    ):
        cursor.execute(
            f"SELECT SUM(raw_frequency) FROM frequency WHERE source ='SUBTLEX-{uk_or_us.upper()}'"
        )
        total_words = cursor.fetchone()[0]

    columns = ["wordform", "source"]
    if f"subtlex{uk_or_us}_raw_frequency" in selected_fields:
        columns.append("raw_frequency")
    if f"subtlex{uk_or_us}_freq_per_million" in selected_fields:
        columns.append("freq_per_million")
    query = f"SELECT {', '.join(columns)} FROM frequency WHERE source = 'SUBTLEX-{uk_or_us.upper()}'"
    cursor.execute(query)
    for row in cursor:
        wordform, source, raw_frequency, freq_per_million = row
        row_dict = {"wordform": wordform, "source": source}

        if f"subtlex{uk_or_us}_raw_frequency" in selected_fields:
            row_dict["raw_frequency"] = raw_frequency
        if f"subtlex{uk_or_us}_freq_per_million" in selected_fields:
            row_dict["freq_per_million"] = freq_per_million
        if f"subtlex{uk_or_us}_logprob" in selected_fields:
            row_dict["logprob"] = (
                math.log10(raw_frequency / total_words)
                if raw_frequency > 0 and total_words > 0
                else float("-inf")
            )
        if f"subtlex{uk_or_us}_zipf" in selected_fields:
            row_dict["zipf"] = (
                zipf.zipf_scale(raw_frequency, total_words)
                if total_words > 0
                else None
            )

        writer.writerow(row_dict)


app = Flask(__name__)


@app.route("/", methods=["GET"])
def get():
    return render_template("index.html")


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

    columns = ["wordform", "source"]
    if (
        "subtlexus_raw_frequency" in selected_fields
        or "subtlexuk_raw_frequency" in selected_fields
    ):
        columns.append("raw_frequency")
    if (
        "subtlexus_freq_per_million" in selected_fields
        or "subtlexuk_freq_per_million" in selected_fields
    ):
        columns.append("freq_per_million")
    if (
        "subtlexuk_logprob" in selected_fields
        or "subtlexus_logprob" in selected_fields
    ):
        columns.append("logprob")
    if (
        "subtlexuk_zipf" in selected_fields
        or "subtlexus_zipf" in selected_fields
    ):
        columns.append("zipf")
    if (
        "wikipronus_IPA" in selected_fields
        or "wikipronuk_IPA" in selected_fields
    ):
        columns.append("pronunciation")
    if (
        "udlex_CELEXtags" in selected_fields
        or "um_CELEXtags" in selected_fields
    ):
        columns.append("celex_tags")
    if "udlex_UDtags" in selected_fields or "um_UDtags" in selected_fields:
        columns.append("ud_tags")
    if "udlex_UMtags" in selected_fields or "um_UMtags" in selected_fields:
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
        if "SUBTLEX-US" in selected_sources:
            _subtlex_to_csv(cursor, writer, "us", selected_fields)

        # Fetches and writes SUBTLEX-UK data
        if "SUBTLEX-UK" in selected_sources:
            _subtlex_to_csv(cursor, writer, "uk", selected_fields)

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

        # Fetches and writes UDLexicons data
        if "UDLexicons" in selected_sources:
            udlex_query = """SELECT wordform, source, tags FROM features WHERE source = 'UDLexicons'"""
            cursor.execute(udlex_query)
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
            um_query = "SELECT wordform, source, tags FROM features WHERE source = 'UniMorph'"
            cursor.execute(um_query)
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

        # Process SUBTLEX-US and SUBTLEX-UK data
        for uk_or_us in ["us", "uk"]:
            source_name = f"SUBTLEX-{uk_or_us.upper()}"
            if source_name in selected_sources:
                # Total words for logprob and Zipf scale calculation
                cursor.execute(
                    f"SELECT SUM(raw_frequency) FROM frequency WHERE source ='{source_name}'"
                )
                total_words = cursor.fetchone()[0]

                query = f"SELECT wordform, raw_frequency, freq_per_million FROM frequency WHERE source = '{source_name}'"
                cursor.execute(query)
                for wordform, raw_frequency, freq_per_million in cursor:
                    if f"subtlex{uk_or_us}_raw_frequency" in selected_fields:
                        add_to_aggregated_data(
                            wordform,
                            f"{source_name} (Raw frequency)",
                            raw_frequency,
                        )
                    if (
                        f"subtlex{uk_or_us}_freq_per_million"
                        in selected_fields
                    ):
                        add_to_aggregated_data(
                            wordform,
                            f"{source_name} (Frequency per million words)",
                            freq_per_million,
                        )
                    if f"subtlex{uk_or_us}_logprob" in selected_fields:
                        logprob = (
                            math.log10(raw_frequency / total_words)
                            if raw_frequency > 0 and total_words > 0
                            else float("-inf")
                        )
                        add_to_aggregated_data(
                            wordform,
                            f"{source_name} (log10 probability)",
                            logprob,
                        )
                    if f"subtlex{uk_or_us}_zipf" in selected_fields:
                        zipf_val = (
                            zipf.zipf_scale(raw_frequency, total_words)
                            if total_words > 0
                            else None
                        )
                        add_to_aggregated_data(
                            wordform, f"{source_name} (Zipf scale)", zipf_val
                        )

        # Process UDLexicons data
        if "UDLexicons" in selected_sources:
            udlex_query = """SELECT wordform, tags FROM features WHERE source = 'UDLexicons'"""
            cursor.execute(udlex_query)
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
            um_query = (
                "SELECT wordform, tags FROM features WHERE source = 'UniMorph'"
            )
            cursor.execute(um_query)
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

        # Process ELP segmentations
        if "ELP" in selected_sources:
            query = "SELECT wordform, segmentation, nmorph FROM segmentation WHERE source = 'ELP'"
            cursor.execute(query)
            for wordform, segmentation, nmorph in cursor:
                if "elp_segmentation" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "ELP (Segmentation)", segmentation
                    )
                if "elp_nmorph" in selected_fields:
                    add_to_aggregated_data(
                        wordform, "ELP (Number of morphs)", nmorph
                    )

        # Process WikiPron-US and WikiPron-UK data
        for country, source_key in [
            ("US", "WikiPron US"),
            ("UK", "WikiPron UK"),
        ]:
            if source_key in selected_sources:
                query = f"SELECT wordform, pronunciation FROM pronunciation WHERE source = '{source_key}' AND standard = 'IPA'"
                cursor.execute(query)
                for wordform, pronunciation in cursor:
                    if f"wikipron{country.lower()}_IPA" in selected_fields:
                        add_to_aggregated_data(
                            wordform, f"{source_key} (IPA)", pronunciation
                        )

        json_output = io.StringIO()
        json.dump(
            aggregated_data, json_output, indent=4
        )
        json_output.seek(0)

        return send_file(
            io.BytesIO(json_output.getvalue().encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"citylex-{datetime.date.today().isoformat()}.json",
        )


if __name__ == "__main__":
    app.run()
