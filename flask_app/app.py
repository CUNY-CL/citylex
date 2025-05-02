import csv
import datetime
import io
import sqlite3
import logging

from flask import Flask, render_template, request, send_file

from citylex import features

DB_PATH = "citylex.db"

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
    # output_format = request.form["output_format"]
    licenses = request.form.getlist("licenses")

    # TODO: add client-side validation in script.js to deactivate "Generate and Download" button if no sources are selected
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
    if "wikipronus_IPA" in selected_fields or "wikipronuk_IPA" in selected_fields:
        columns.append("IPA_pronunciation")
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

    # TODO: Refactor to use a single query per SQL table using WHERE source IN (...)
    # Fetches and writes SUBTLEX-US data
    if "SUBTLEX-US" in selected_sources:
        us_columns = ["wordform", "source"]
        if "subtlexus_raw_frequency" in selected_fields:
            us_columns.append("raw_frequency")
        if "subtlexus_freq_per_million" in selected_fields:
            us_columns.append("freq_per_million")
        us_query = (
            f"SELECT {', '.join(us_columns)} FROM frequency WHERE source = 'SUBTLEX-US'"
        )
        cursor.execute(us_query)
        for row in cursor:
            row_dict = dict(zip(us_columns, row))
            writer.writerow(row_dict)

    # Fetches and writes SUBTLEX-UK data
    if "SUBTLEX-UK" in selected_sources:
        uk_columns = ["wordform", "source"]
        if "subtlexuk_raw_frequency" in selected_fields:
            uk_columns.append("raw_frequency")
        if "subtlexuk_freq_per_million" in selected_fields:
            uk_columns.append("freq_per_million")
        uk_query = (
            f"SELECT {', '.join(uk_columns)} FROM frequency WHERE source = 'SUBTLEX-UK'"
        )
        cursor.execute(uk_query)
        for row in cursor:
            row_dict = dict(zip(uk_columns, row))
            writer.writerow(row_dict)  

    # Fetches and writes WikiPron-US data
    if "WikiPron-US" in selected_sources:
        wp_us_columns = ["wordform", "source", "pronunciation"]
        wp_us_query = f"SELECT wordform, source, pronunciation FROM pronunciation WHERE source = 'WikiPron US' AND standard = 'IPA'"
        cursor.execute(wp_us_query)
        for row in cursor:
            row_dict = dict(zip(wp_us_columns, row))
            row_dict["IPA_pronunciation"] = row_dict.pop("pronunciation")
            writer.writerow(row_dict)

    # Fetches and writes WikiPron-UK data
    if "WikiPron-UK" in selected_sources:
        wp_uk_columns = ["wordform", "source", "pronunciation"]
        wp_uk_query = f"SELECT wordform, source, pronunciation FROM pronunciation WHERE source = 'WikiPron UK' AND standard = 'IPA'"
        cursor.execute(wp_uk_query)
        for row in cursor:
            row_dict = dict(zip(wp_uk_columns, row))
            row_dict["IPA_pronunciation"] = row_dict.pop("pronunciation")
            writer.writerow(row_dict)

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
        elp_query = (
            f"SELECT {', '.join(elp_columns)} FROM segmentation WHERE source = 'ELP'"
        )
        cursor.execute(elp_query)
        for row in cursor:
            row_dict = dict(zip(elp_columns, row))
            writer.writerow(row_dict)

    # Sends the file as a response
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/tab-separated-values",
        as_attachment=True,
        download_name=f"citylex-{datetime.date.today().isoformat()}.tsv",
    )


if __name__ == "__main__":
    app.run()
