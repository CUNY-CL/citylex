"""Populates and prepares the CityLex SQLite database.

After downloading and inserting all requested data sources, this script
also prepares the database for static deployment via sql.js-httpvfs by:

  1. Adding indexes on wordform/source for every table.
  2. Switching the journal mode to DELETE and running VACUUM so the file
     is a single clean blob with no -wal/-shm sidecar files.
  3. Writing a citylex.db.json config file for sql.js-httpvfs.

Usage examples:
    python populate.py --all-free
    python populate.py --all-free --celex
    python populate.py --subtlex-uk --subtlex-us
"""

import argparse
import csv
import io
import json
import logging
import os
import sqlite3
import struct
import tarfile
import unicodedata
import zipfile

from typing import Dict, Iterator, List

import pandas  # type: ignore
import requests

SERVER_ROOT = "app"
DB_PATH = "citylex.db"  # Relative to SERVER_ROOT.

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,"
    "application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.6 Safari/605.1.15 Ddg/17.6",
}


class Error(Exception):
    pass


# Helpers.


def _normalize(field: str) -> str:
    """Performs basic Unicode normalization and casefolding on field."""
    return unicodedata.normalize("NFC", field).casefold()


def _request_url_file_resource(url: str) -> io.BytesIO:
    """Requests a URL and returns a mock file."""
    logging.info("Requesting URL: %s", url)
    with requests.get(url, headers=HEADERS, stream=True) as response:
        response.raise_for_status()
        return io.BytesIO(response.content)


def _request_url_text_resource(url: str) -> Iterator[str]:
    """Requests a URL and returns text."""
    logging.info("Requesting URL: %s", url)
    with requests.get(url, headers=HEADERS, stream=True) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            yield line.decode("utf8", "ignore")


def _request_url_tar_resource(url: str) -> tarfile.TarFile:
    """Requests a tar.gz file by URL."""
    mock_file = _request_url_file_resource(url)
    return tarfile.open(fileobj=mock_file, mode="r:")


def _request_url_zip_resource(url: str) -> zipfile.ZipFile:
    """Requests a zip file by URL."""
    mock_file = _request_url_file_resource(url)
    return zipfile.ZipFile(mock_file, "r")


def _tar_lines(tar: tarfile.TarFile, path: str) -> Iterator[str]:
    """Yields lines of a file extracted from a TAR archive."""
    with tar.extractfile(path) as source:  # type: ignore
        for line in source:
            yield line.decode("utf8", "ignore")


def _zip_lines(myzip: zipfile.ZipFile, path: str) -> Iterator[str]:
    """Yields lines of a file extracted from a ZIP archive."""
    with myzip.open(path, "r") as source:
        for line in source:
            yield line.decode("utf8", "ignore")


# CELEX.


def _parse_celex_row(line: str) -> List[str]:
    """Parses a single line of CELEX."""
    return line.rstrip().split("\\")


def _celex(conn: sqlite3.Connection) -> None:
    """Collects CELEX data and inserts it into the database."""
    cursor = conn.cursor()
    try:
        url = os.environ["CELEX_PATH"]
    except KeyError:
        raise Error("--celex requested but $CELEX_PATH not set")
    archive = _request_url_tar_resource(url)
    # Frequencies.
    counter = 0
    for line in _tar_lines(archive, "celex2/english/efw/efw.cd"):
        row = _parse_celex_row(line)
        wordform = _normalize(row[1])
        if " " in wordform:
            continue
        freq = int(row[3])
        cursor.execute(
            """
            INSERT INTO frequency
            (wordform, source, raw_frequency, freq_per_million)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "CELEX", freq, 0),
        )
        counter += 1
    assert counter, "No data read"
    cursor.execute(
        "SELECT SUM(raw_frequency) FROM frequency WHERE source = 'CELEX'"
    )
    total_freq = cursor.fetchone()[0]
    assert total_freq > 0
    cursor.execute(
        """
        UPDATE frequency
        SET freq_per_million =
        ROUND(CAST(raw_frequency AS REAL) * 1000000 / ?, 2)
        WHERE source = 'CELEX'
        """,
        (total_freq,),
    )
    logging.info("Collected %d CELEX frequencies", counter)
    # Morphology.
    lemma_info: Dict[int, str] = {}
    for line in _tar_lines(archive, "celex2/english/eml/eml.cd"):
        row = _parse_celex_row(line)
        li = int(row[0])
        lemma = _normalize(row[1])
        if " " in lemma:
            continue
        lemma_info[li] = lemma
    counter = 0
    for line in _tar_lines(archive, "celex2/english/emw/emw.cd"):
        row = _parse_celex_row(line)
        wordform = _normalize(row[1])
        if " " in wordform:
            continue
        li = int(row[3])
        try:
            lemma = lemma_info[li]
        except KeyError:
            logging.debug(
                "Ignoring wordform missing lemma ID: %s (%d)", wordform, li
            )
            continue
        celex_tag = row[4]
        cursor.execute(
            """
            INSERT INTO features (wordform, source, lemma, tags)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "CELEX", lemma, celex_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d CELEX analyses", counter)
    # Pronunciations.
    counter = 0
    for line in _tar_lines(archive, "celex2/english/epw/epw.cd"):
        row = _parse_celex_row(line)
        wordform = _normalize(row[1])
        if " " in wordform:
            continue
        pron = row[6].replace("-", "")
        cursor.execute(
            """
            INSERT INTO pronunciation
            (wordform, dialect, source, standard, pronunciation, is_observed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "UK", "CELEX", "DISC", pron, True),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d CELEX pronunciations", counter)
    conn.commit()


# ELP.


def _elp(conn: sqlite3.Connection) -> None:
    """Collects ELP analyses."""
    cursor = conn.cursor()
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "ELP-annotations/master/ELP.csv"
    )
    source = _request_url_text_resource(url)
    for drow in csv.DictReader(source):
        wordform = _normalize(drow["Word"])
        morph_sp = drow["MorphSp"]
        nmorph = drow["NMorph"]
        # The CSV uses the string "NULL" for missing values, and some rows
        # have empty strings; skip any row missing either field.
        if (
            not morph_sp
            or morph_sp == "NULL"
            or not nmorph
            or nmorph == "NULL"
        ):
            continue
        cursor.execute(
            """
            INSERT INTO segmentation (wordform, source, nmorph, segmentation)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "ELP", int(nmorph), morph_sp),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d ELP analyses", counter)
    conn.commit()


# SUBTLEX-UK.


def _subtlex_uk(conn: sqlite3.Connection) -> None:
    """Collects SUBTLEX-UK frequencies."""
    cursor = conn.cursor()
    counter = 0
    url = "https://osf.io/download/d3jbg/"
    xlsx = _request_url_file_resource(url)
    df = pandas.read_excel(xlsx)
    total_freq = df["FreqCount"].sum()
    for _, row in df.iterrows():
        wordform = _normalize(str(row["Spelling"]))
        if " " in wordform:
            continue
        freq = int(row["FreqCount"])
        freq_per_million = round(freq * 1_000_000 / total_freq, 2)
        cursor.execute(
            """
            INSERT INTO frequency
            (wordform, source, raw_frequency, freq_per_million)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "SUBTLEX-UK", freq, freq_per_million),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d SUBTLEX-UK frequencies", counter)
    conn.commit()


# SUBTLEX-US.


def _subtlex_us(conn: sqlite3.Connection) -> None:
    """Collects SUBTLEX-US frequencies."""
    cursor = conn.cursor()
    counter = 0
    url = "https://osf.io/download/7wx25/"
    xlsx = _request_url_file_resource(url)
    df = pandas.read_excel(xlsx)
    total_freq = df["FREQcount"].sum()
    for _, row in df.iterrows():
        wordform = _normalize(str(row["Word"]))
        if " " in wordform:
            continue
        freq = int(row["FREQcount"])
        freq_per_million = round(freq * 1_000_000 / total_freq, 2)
        cursor.execute(
            """
            INSERT INTO frequency
            (wordform, source, raw_frequency, freq_per_million)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "SUBTLEX-US", freq, freq_per_million),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d SUBTLEX-US frequencies", counter)
    conn.commit()


# UDLexicons.


def _udlexicons(conn: sqlite3.Connection) -> None:
    """Collects UDLexicons analyses."""
    cursor = conn.cursor()
    counter = 0
    url = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
    myzip = _request_url_zip_resource(url)
    source = _zip_lines(myzip, "UDLexicons.0.2/UDLex_English-Apertium.conllul")
    strict_no_overgeneralize = True
    for line in source:
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        # Shifted indices for the CoNLL-UL layout.
        wordform = _normalize(parts[2])
        if " " in wordform:
            continue
        lemma = _normalize(parts[3])
        upos = parts[4]
        feats_raw = parts[6]
        feats0 = feats_raw.split("|") if feats_raw not in ("_", "") else []
        feats = [f for f in feats0 if not f.startswith("Gender=")]
        feats_sorted = (
            sorted(feats, key=lambda s: s.split("=")[0]) if feats else []
        )
        if feats_sorted:
            ud_tag = f"{upos}|{'|'.join(feats_sorted)}"
        else:
            if feats_raw == "_":
                ud_tag = upos
            elif strict_no_overgeneralize:
                is_propn = upos == "PROPN"
                has_features = bool(feats0)
                all_gender = all(x.startswith("Gender=") for x in feats0)
                only_gender_removed = is_propn and has_features and all_gender
                if only_gender_removed:
                    ud_tag = upos
                else:
                    continue
            else:
                ud_tag = upos
        cursor.execute(
            """
            INSERT INTO features (wordform, source, lemma, tags)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "UDLexicons", lemma, ud_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d UDLexicon analyses", counter)
    conn.commit()


# UniMorph.


def _unimorph(conn: sqlite3.Connection) -> None:
    """Collects UniMorph analyses."""
    cursor = conn.cursor()
    counter = 0
    url = "https://raw.githubusercontent.com/unimorph/eng/master/eng"
    source = _request_url_text_resource(url)
    for lemma, wordform, features in csv.reader(source, delimiter="\t"):
        wordform = _normalize(wordform)
        lemma = _normalize(lemma)
        cursor.execute(
            """
            INSERT INTO features (wordform, source, lemma, tags)
            VALUES (?, ?, ?, ?)
            """,
            (wordform, "UniMorph", lemma, features),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d UniMorph analyses", counter)
    conn.commit()


# WikiPron.


def _wikipron_uk(conn: sqlite3.Connection) -> None:
    """Collects WikiPron UK pronunciations."""
    cursor = conn.cursor()
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/scrape/tsv/eng_latn_uk_broad_filtered.tsv"
    )
    source = _request_url_text_resource(url)
    for wordform, pron in csv.reader(source, delimiter="\t"):
        wordform = _normalize(wordform)
        pron = _normalize(pron)
        cursor.execute(
            """
            INSERT INTO pronunciation
            (wordform, dialect, source, standard, pronunciation, is_observed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "UK", "WikiPron UK", "IPA", pron, True),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d WikiPron UK pronunciations", counter)
    conn.commit()


def _wikipron_us(conn: sqlite3.Connection) -> None:
    """Collects WikiPron US pronunciations."""
    cursor = conn.cursor()
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/scrape/tsv/eng_latn_us_broad_filtered.tsv"
    )
    source = _request_url_text_resource(url)
    for wordform, pron in csv.reader(source, delimiter="\t"):
        wordform = _normalize(wordform)
        pron = _normalize(pron)
        cursor.execute(
            """
            INSERT INTO pronunciation
            (wordform, dialect, source, standard, pronunciation, is_observed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "US", "WikiPron US", "IPA", pron, True),
        )
        counter += 1
    assert counter, "No data read"
    logging.info("Collected %d WikiPron US pronunciations", counter)
    conn.commit()


# DB preparation for static deployment.


def _get_page_size(db_path: str) -> int:
    """Reads the SQLite page size from the file header (bytes 16-17)."""
    with open(db_path, "rb") as fh:
        header = fh.read(100)
    raw = struct.unpack(">H", header[16:18])[0]
    return 65536 if raw == 1 else raw


def _prepare(db_path: str) -> None:
    """Adds indexes, sets journal mode, VACUUMs, writes config JSON.

    This must be called after all data has been committed and the connection
    closed, because VACUUM requires no other connections and rewrites the file.
    """
    logging.info("Creating indexes...")
    conn = sqlite3.connect(db_path)
    indexes = [
        ("idx_frequency_wordform", "frequency", "wordform"),
        ("idx_frequency_source", "frequency", "source"),
        ("idx_features_wordform", "features", "wordform"),
        ("idx_features_source", "features", "source"),
        ("idx_pronunciation_wordform", "pronunciation", "wordform"),
        ("idx_pronunciation_source", "pronunciation", "source"),
        ("idx_segmentation_wordform", "segmentation", "wordform"),
        ("idx_segmentation_source", "segmentation", "source"),
    ]
    for idx_name, table, column in indexes:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"
        )
    conn.commit()
    conn.close()
    logging.info("Vacuuming...")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("VACUUM")
    conn.commit()
    page_size = _get_page_size(db_path)
    config = {
        "serverMode": "full",
        "requestChunkSize": page_size,
        "url": os.path.basename(db_path),
    }
    config_path = db_path.replace(".db", ".db.json")
    with open(config_path, "w", encoding="utf-8") as sink:
        json.dump(config, sink, indent=2)
        print(file=sink)
    logging.info("Wrote %s (page size: %d bytes).", config_path, page_size)


# Main.


def main() -> None:
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-free", action="store_true", help="extract all free data sources"
    )
    parser.add_argument(
        "--celex",
        action="store_true",
        help="extract CELEX data (requires $CELEX_PATH env var): "
        "http://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf",
    )
    parser.add_argument("--elp", action="store_true")
    parser.add_argument("--subtlex-uk", action="store_true")
    parser.add_argument("--subtlex-us", action="store_true")
    parser.add_argument("--udlexicons", action="store_true")
    parser.add_argument("--unimorph", action="store_true")
    parser.add_argument("--wikipron-uk", action="store_true")
    parser.add_argument("--wikipron-us", action="store_true")
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help="output database path relative to --server-root "
        "(default: %(default)s),",
    )
    parser.add_argument(
        "--server-root",
        default=SERVER_ROOT,
        help="URL path prefix where the DB will be served "
        "(default: %(default)s)",
    )
    args = parser.parse_args()
    if not any(
        [
            args.all_free,
            args.celex,
            args.elp,
            args.subtlex_uk,
            args.subtlex_us,
            args.udlexicons,
            args.unimorph,
            args.wikipron_uk,
            args.wikipron_us,
        ]
    ):
        parser.error(
            "No data sources selected. Use --all-free or specific flags."
        )
    db_path = os.path.join(args.server_root, args.db)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    logging.info("Dropping existing tables...")
    for table in ["frequency", "pronunciation", "features", "segmentation"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    logging.info("Creating tables...")
    cursor.executescript("""
        CREATE TABLE frequency (
            id              INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform        TEXT    NOT NULL,
            source          TEXT    NOT NULL,
            raw_frequency   INTEGER NOT NULL,
            freq_per_million DECIMAL(5,2) NOT NULL
        );
        CREATE TABLE pronunciation (
            id           INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform     TEXT    NOT NULL,
            dialect      TEXT    NOT NULL,
            source       TEXT    NOT NULL,
            standard     TEXT    NOT NULL,
            pronunciation TEXT   NOT NULL,
            is_observed  BOOLEAN NOT NULL
        );
        CREATE TABLE features (
            id       INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT    NOT NULL,
            source   TEXT    NOT NULL,
            lemma    TEXT    NOT NULL,
            tags     TEXT    NOT NULL
        );
        CREATE TABLE segmentation (
            id           INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform     TEXT    NOT NULL,
            source       TEXT    NOT NULL,
            nmorph       INTEGER NOT NULL,
            segmentation TEXT    NOT NULL
        );
    """)
    conn.commit()
    if args.celex:
        _celex(conn)
    if args.all_free or args.elp:
        _elp(conn)
    if args.all_free or args.subtlex_uk:
        _subtlex_uk(conn)
    if args.all_free or args.subtlex_us:
        _subtlex_us(conn)
    if args.all_free or args.udlexicons:
        _udlexicons(conn)
    if args.all_free or args.unimorph:
        _unimorph(conn)
    if args.all_free or args.wikipron_uk:
        _wikipron_uk(conn)
    if args.all_free or args.wikipron_us:
        _wikipron_us(conn)
    conn.close()
    logging.info("Data collection complete.")
    _prepare(db_path)
    logging.info(
        "Deploy %s and %s.json to your static host.", db_path, db_path
    )


if __name__ == "__main__":
    main()
