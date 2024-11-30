# problem - not putting stuff into the right columns

import argparse
import csv
import io
import logging
import os
import sqlite3
import unicodedata
import zipfile

from typing import Dict, Iterator, List
from flask import Flask, render_template, request, send_file

import pandas  # type: ignore
import requests


# Helper methods.


def _normalize(field: str) -> str:
    """Performs basic Unicode normalization and casefolding on field."""
    return unicodedata.normalize("NFC", field).casefold()


def _request_url_resource(url: str) -> Iterator[str]:
    """Requests a URL and returns text."""
    logging.info("Requesting URL: %s", url)
    response = requests.get(url, stream=True)
    response.raise_for_status()
    for line in response.iter_lines():
        yield line.decode("utf8", "ignore")


def _request_url_mock_file(url: str) -> io.BytesIO:
    """Requests a URL and returns a mock file."""
    logging.info("Requesting URL: %s", url)
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)


def _request_url_zip_resource(url: str, path: str) -> Iterator[str]:
    """Requests a zip file by URL and the path to the desired file."""
    mock_zip_file = _request_url_mock_file(url)
    # Opens the zip file, and then the specific enclosed file.
    with zipfile.ZipFile(mock_zip_file, "r").open(path, "r") as source:
        for line in source:
            yield line.decode("utf8", "ignore")

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    db_path = "citylex.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if request.method == "GET":
        return render_template('index.html')
    elif request.method == "POST":
        selected_sources = request.form.getlist("sources[]")
        selected_fields = request.form.getlist("fields[]")
        output_format = request.form["output_format"]
        licenses = request.form.getlist("licenses")
        if not selected_sources or not selected_fields:
            return "Please select at least one data source and field.", 400
        print(selected_sources)
        print(selected_fields)
        print(output_format)
        print(licenses)

        output = io.StringIO()
        writer = csv.writer(output, delimiter='\t')

        columns = ["wordform", "source"]
        if "subtlexus_raw_frequency" in selected_fields or "subtlexuk_raw_frequency" in selected_fields:
            columns.append("raw_frequency")
        if "subtlexus_freq_per_million" in selected_fields or "subtlexuk_freq_per_million" in selected_fields:
            columns.append("freq_per_million")
        if "wikipronus_IPA" in selected_fields or "wikipronuk_IPA" in selected_fields:
            columns.append("IPA_pronunciation")

        writer.writerow(columns)  # Write header

        # Fetch and write SUBTLEX-US data
        if "SUBTLEX-US" in selected_sources:
            us_columns = ["wordform", "source"]
            if "subtlexus_raw_frequency" in selected_fields:
                us_columns.append("raw_frequency")
            if "subtlexus_freq_per_million" in selected_fields:
                us_columns.append("freq_per_million")
            us_query = f"SELECT {', '.join(us_columns)} FROM frequency WHERE source = 'SUBTLEX-US'"
            cursor.execute(us_query)
            us_results = cursor.fetchall()
            for row in us_results:
                row_dict = dict(zip(us_columns, row))
                writer.writerow([row_dict.get(col, '') for col in columns])  # Write US data

        # Fetch and write SUBTLEX-UK data
        if "SUBTLEX-UK" in selected_sources:
            uk_columns = ["wordform", "source"]
            if "subtlexuk_raw_frequency" in selected_fields:
                uk_columns.append("raw_frequency")
            if "subtlexuk_freq_per_million" in selected_fields:
                uk_columns.append("freq_per_million")
            uk_query = f"SELECT {', '.join(uk_columns)} FROM frequency WHERE source = 'SUBTLEX-UK'"
            cursor.execute(uk_query)
            uk_results = cursor.fetchall()
            for row in uk_results:
                row_dict = dict(zip(uk_columns, row))
                writer.writerow([row_dict.get(col, '') for col in columns])  # Write UK data

        # Fetch and write WikiPron-US data
        if "WikiPron-US" in selected_sources:
            wp_us_columns = ["wordform", "source", "pronunciation"]
            wp_us_query = f"SELECT wordform, source, pronunciation FROM pronunciation WHERE source = 'WikiPron US' AND standard = 'IPA'"
            cursor.execute(wp_us_query)
            wp_us_results = cursor.fetchall()
            for row in wp_us_results:
                row_dict = dict(zip(wp_us_columns, row))
                row_dict["IPA_pronunciation"] = row_dict.pop("pronunciation")
                writer.writerow([row_dict.get(col, '') for col in columns])  # Write WikiPron-US data

        # Fetch and write WikiPron-UK data
        if "WikiPron-UK" in selected_sources:
            wp_uk_columns = ["wordform", "source", "pronunciation"]
            wp_uk_query = f"SELECT wordform, source, pronunciation FROM pronunciation WHERE source = 'WikiPron UK' AND standard = 'IPA'"
            cursor.execute(wp_uk_query)
            wp_uk_results = cursor.fetchall()
            for row in wp_uk_results:
                row_dict = dict(zip(wp_uk_columns, row))
                row_dict["IPA_pronunciation"] = row_dict.pop("pronunciation")
                writer.writerow([row_dict.get(col, '') for col in columns])  # Write WikiPron-UK data

        output.seek(0)  # Move the cursor to the beginning of the file

        # Send the file as a response
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/tab-separated-values',
            as_attachment=True,
            download_name='citylex_data.tsv'
            )


if __name__ == "__main__":
    app.run()