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

def _subtlex_us(conn: sqlite3.Connection) -> None:
    """Collects SUBTLEX-US frequencies."""
    counter = 0
    url = (
        "https://web.archive.org/web/20211125032415/"
        "http://crr.ugent.be/papers/"
        "SUBTLEX-US_frequency_list_with_PoS_information_"
        "final_text_version.zip"
    )
    path = "SUBTLEX-US frequency list with PoS information text version.txt"
    source = _request_url_zip_resource(url, path)
    cursor = conn.cursor()
    for drow in csv.DictReader(source, delimiter="\t"):
        wordform = _normalize(drow["Word"])
        freq = int(drow["FREQcount"])
        cursor.execute(
            """
            INSERT INTO frequency (
                wordform,
                source,
                raw_frequency,
                freq_per_million
                ) VALUES (?, ?, ?, ?)
            """,
            (wordform, "SUBTLEX-US", freq, 0),
        )
        counter += 1
    assert counter, "No data read"
    cursor.execute("SELECT SUM(raw_frequency) FROM frequency")
    total_freq = cursor.fetchone()[0]
    assert total_freq > 0, "Total frequency must be greater than zero."
    cursor.execute(
        """
        UPDATE frequency
            SET freq_per_million =
            ROUND(CAST(raw_frequency AS REAL) * 1000000 / ?, 2)
        """,
        (total_freq,),
    )
    logging.info(f"Collected {counter:,} SUBTLEX-US frequencies")
    conn.commit()

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    db_path = "citylex.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    logging.info("Dropping existing tables if they exist...")
    for table in ["frequency", "pronunciation", "features", "segmentation"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    logging.info("Creating tables...")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS frequency (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            raw_frequency INTEGER NOT NULL,
            freq_per_million DECIMAL(5, 2) NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pronunciation (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            dialect TEXT NOT NULL,
            source TEXT NOT NULL,
            standard TEXT NOT NULL,
            pronunciation TEXT NOT NULL,
            is_observed BOOLEAN NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            lemma TEXT NOT NULL,
            features TEXT NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS segmentation (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            nmorph TEXT NOT NULL,
            segmentation TEXT NOT NULL
        )
    """
    )
    conn.commit()


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

        if "SUBTLEX-US" in selected_sources:
            _subtlex_us(conn)
            columns = ["wordform", "source"]
            if "subtlexus_raw_frequency" in selected_fields:
                columns.append("raw_frequency")
            if "subtlexus_freq_per_million" in selected_fields:
                columns.append("freq_per_million")
            query = f"SELECT {', '.join(columns)} FROM frequency WHERE source = 'SUBTLEX-US'"
            cursor.execute(query)
            results = cursor.fetchall()

            # Create a TSV file in memory
            output = io.StringIO()
            writer = csv.writer(output, delimiter='\t')
            writer.writerow(columns)  # Write header
            writer.writerows(results)  # Write data
            
            output.seek(0)  # Move the cursor to the beginning of the file
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/tab-separated-values',
                as_attachment=True,
                download_name='subtlex_us_data.tsv'
            )
        
        return "Success! Your file has been downloaded"


if __name__ == "__main__":
    app.run()