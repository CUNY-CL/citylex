import csv
import datetime
import io
import logging
import math
import sqlite3

from flask import Flask, render_template, request, send_file

from citylex import features, zipf

DB_PATH = "citylex.db"

def _fetch_and_write_data(cursor, writer, source_table, columns, where=""):
    """
    Fetches and writes data from a specified table with given columns and an optional WHERE clause.

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

app = Flask(__name__)


def _fetch_and_write_subtlex_data(cursor, writer, uk_or_us, selected_fields):
    """
    Fetches and writes data for SUBTLEX-US and SUBTLEX-UK.

    Args:
        cursor: The SQLite cursor object.
        writer: The CSV DictWriter object.
        uk_or_us (str): Either "uk" or "us" depending on the desired source.
        selected_fields (list): The list of fields selected by the user on the form.
    """
    if f"subtlex{uk_or_us}_logprob" in selected_fields or f"subtlex{uk_or_us}_zipf" in selected_fields:
            cursor.execute(f"SELECT SUM(raw_frequency) FROM frequency WHERE source = 'SUBTLEX-{uk_or_us.upper()}'")
            total_words = cursor.fetchone()[0]

    columns = ["wordform", "source"]
    if f"subtlex{uk_or_us}_raw_frequency" in selected_fields:
        columns.append("raw_frequency")
    if f"subtlex{uk_or_us}_freq_per_million" in selected_fields:
        columns.append("freq_per_million")
    query = (
        f"SELECT {', '.join(columns)} FROM frequency WHERE source = 'SUBTLEX-{uk_or_us.upper()}'"
    )
    cursor.execute(query)
    for row in cursor:
        wordform, source, raw_frequency, freq_per_million = row
        row_dict = {"wordform": wordform, "source": source}

        if f"subtlex{uk_or_us}_raw_frequency" in selected_fields:
            row_dict["raw_frequency"] = raw_frequency
        if f"subtlex{uk_or_us}_freq_per_million" in selected_fields:
            row_dict["freq_per_million"] = freq_per_million
        if f"subtlex{uk_or_us}_logprob" in selected_fields:
            row_dict["logprob"] = math.log10(raw_frequency / total_words) if raw_frequency > 0 and total_words > 0 else float('-inf')
        if f"subtlex{uk_or_us}_zipf" in selected_fields:
            row_dict["zipf"] = zipf.zipf_scale(raw_frequency, total_words) if total_words > 0 else None

        writer.writerow(row_dict)


@app.route("/", methods=["GET"])
def get():
    return render_template("index.html")


@app.route("/", methods=["POST"])
def post():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    selected_sources = request.form.getlist("sources[]")
    selected_fields = request.form.getlist("fields[]")
    # output_format = request.form["output_format"]
    licenses = request.form.getlist("licenses")

    if not selected_sources or not selected_fields:
        return render_template("400.html"), 400

    logging.info(f"Selected sources: {selected_sources}")
    logging.info(f"Selected fields: {selected_fields}")
    # logging.info(f"Output format: {output_format}")
    logging.info(f"Licenses: {licenses}")

    output = io.StringIO()

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
    if "wikipronus_IPA" in selected_fields or "wikipronuk_IPA" in selected_fields:
        columns.append("pronunciation")
    # if "udlex_CELEXtags" in selected_fields or "um_CELEXtags" in selected_fields:
    #     columns.append("celex_tags")
    if "udlex_UDtags" in selected_fields or "um_UDtags" in selected_fields:
        columns.append("ud_tags")
    if "udlex_UMtags" in selected_fields or "um_UMtags" in selected_fields:
        columns.append("um_tags")
    if "elp_segmentation" in selected_fields:
        columns.append("segmentation")
    if "elp_nmorph" in selected_fields:
        columns.append("nmorph")

    writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t")
    writer.writeheader()

    # Fetches and writes SUBTLEX-US data
    if "SUBTLEX-US" in selected_sources:
        _fetch_and_write_subtlex_data(cursor, writer, "us", selected_fields)

    # Fetches and writes SUBTLEX-UK data
    if "SUBTLEX-UK" in selected_sources:
        _fetch_and_write_subtlex_data(cursor, writer, "uk", selected_fields)

    # Fetches and writes WikiPron-US data
    if "WikiPron-US" in selected_sources:
        wp_us_columns = ["wordform", "source", "pronunciation"]
        _fetch_and_write_data(cursor, writer, "pronunciation", wp_us_columns, "source = 'WikiPron US' AND standard = 'IPA'")

    # Fetches and writes WikiPron-UK data
    if "WikiPron-UK" in selected_sources:
        wp_uk_columns = ["wordform", "source", "pronunciation"]
        _fetch_and_write_data(cursor, writer, "pronunciation", wp_uk_columns, "source = 'WikiPron UK' AND standard = 'IPA'")

    # Fetches and writes UDLexicons data
    if "UDLexicons" in selected_sources:
        udlex_query = "SELECT wordform, source, tags FROM features WHERE source = 'UDLexicons'"
        cursor.execute(udlex_query)
        for row in cursor:
            wordform, source, ud_tags = row
            row_dict = {"wordform": wordform, "source": source}
            
            if "udlex_UDtags" in selected_fields:
                row_dict["ud_tags"] = ud_tags
            if "udlex_UMtags" in selected_fields:
                row_dict["um_tags"] = features.tag_to_tag("UD", "UniMorph", ud_tags)
            # if "udlex_CELEXtags" in selected_fields:
            #     row_dict["celex_tags"] = features.tag_to_tag("UD", "CELEX", ud_tags)
            
            writer.writerow(row_dict)

    # Fetches and writes UniMorph data
    if "UniMorph" in selected_sources:
        um_query = "SELECT wordform, source, tags FROM features WHERE source = 'UniMorph'"
        cursor.execute(um_query)
        for row in cursor:
            wordform, source, um_tags = row
            row_dict = {"wordform": wordform, "source": source}
            
            if "um_UDtags" in selected_fields:
                row_dict["ud_tags"] = features.tag_to_tag("UniMorph", "UD", um_tags)
            if "um_UMtags" in selected_fields:
                row_dict["um_tags"] = um_tags
            # if "um_CELEXtags" in selected_fields:
            #     row_dict["celex_tags"] = features.tag_to_tag("UniMorph", "CELEX", um_tags)
            
            writer.writerow(row_dict)

    # Fetches and writes ELP segmentations
    if "ELP" in selected_sources:
        elp_columns = ["wordform", "source"]
        if "elp_segmentation" in selected_fields:
            elp_columns.append("segmentation")
        if "elp_nmorph" in selected_fields:
            elp_columns.append("nmorph")
        _fetch_and_write_data(cursor, writer, "segmentation", elp_columns, "source = 'ELP'")

    # Sends the file as a response
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/tab-separated-values",
        as_attachment=True,
        download_name=f"citylex-{datetime.date.today().isoformat()}.tsv",
    )


if __name__ == "__main__":
    app.run()
