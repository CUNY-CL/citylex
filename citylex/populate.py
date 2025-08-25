"""Populates the CityLex database."""

import argparse
import csv
import io
import logging
import os
import sqlite3
import tarfile
import unicodedata
import zipfile

from typing import Dict, Iterator, List

import pandas  # type: ignore
import requests

DB_PATH = "citylex.db"

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


# Helper methods.


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
    """Yields an iterator over lines of a file extracted from a TAR archive."""
    with tar.extractfile(path) as source:  # type: ignore
        for line in source:
            yield line.decode("utf8", "ignore")


def _zip_lines(myzip: zipfile.ZipFile, path: str) -> Iterator[str]:
    """Yields an iterator over lines of a file extracted from a ZIP archive."""
    with myzip.open(path, "r") as source:
        for line in source:
            yield line.decode("utf8", "ignore")


# CELEX.


def _parse_celex_row(line: str) -> List[str]:
    """Parses a single line of CELEX."""
    return line.rstrip().split("\\")


# This is original work, based on my reading of the CELEX2 English and UniMorph
# guidelines. It covers four main parts of speech: adjectives, adverbs, nouns,
# and verbs.
CELEX_FEATURE_MAP = {
    "b": "ADJ",  # We don't mark positive adjectives in UniMorph.
    "c": "ADJ;CMPR",
    "s": "ADJ;RL",  # English superlatives are "relative" ones.
    "B": "ADV",
    "S": "N;SG",
    "P": "N;PL",
    "i": "V;NFIN",
    "e3S": "V;SG;3;PRS",
    "a1S": "V;PST",
    "pe": "V.PTCP;PRS",
    "pa": "V.PTCP;PST",
}
# Deliberately excluded:
# * "e[123]S": no need to distinguish this from the non-finite.
# * "a2S" and "a3S": no need to distinguish between this and "a1S".


def _celex(conn: sqlite3.Connection) -> None:
    """Collects CELEX data and inserts it into database.

    We get the path to the CELEX data from an environmental variable, namely
    CELEX_PATH.
    """
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
        # Skips multiword entries.
        if " " in wordform:
            continue
        freq = int(row[3])
        # Inserts data with a placeholder for freq_per_million.
        cursor.execute(
            """
            INSERT INTO frequency (
                wordform,
                source,
                raw_frequency,
                freq_per_million
                ) VALUES (?, ?, ?, ?)
            """,
            (wordform, "CELEX", freq, 0),
        )
        counter += 1
    assert counter, "No data read"
    cursor.execute(
        "SELECT SUM(raw_frequency) FROM frequency WHERE source = 'CELEX'"
    )
    total_freq = cursor.fetchone()[0]
    assert total_freq > 0, "Total frequency must be greater than zero."
    # Updates freq_per_million for all entries.
    cursor.execute(
        """
        UPDATE frequency
            SET freq_per_million =
            ROUND(CAST(raw_frequency AS REAL) * 1000000 / ?, 2)
            WHERE source = 'CELEX'
        """,
        (total_freq,),
    )
    logging.info(f"Collected {counter:,} CELEX frequencies")
    # Morphology.
    # Reads lemma information.
    lemma_info: Dict[int, str] = {}
    counter = 0
    for line in _tar_lines(archive, "celex2/english/eml/eml.cd"):
        row = _parse_celex_row(line)
        li = int(row[0])
        lemma = _normalize(row[1])
        if " " in lemma:
            continue
        # Previous attempts to insert partial rows resulted in slow
        # performance, so lemmas are loaded into Python memory
        # for efficiency.
        lemma_info[li] = lemma
        counter += 1
    # Reads wordform information.
    counter = 0
    for line in _tar_lines(archive, "celex2/english/emw/emw.cd"):
        row = _parse_celex_row(line)
        wordform = _normalize(row[1])
        if " " in wordform:
            continue
        li = int(row[3])
        # There are a few wordforms whose lemma IDs point to nothing. This
        # catches it.
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
            INSERT INTO features (
                wordform,
                source,
                lemma,
                tags
                ) VALUES (?, ?, ?, ?)
            """,
            (wordform, "CELEX", lemma, celex_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX analyses")
    # Pronunciations.
    counter = 0
    for line in _tar_lines(archive, "celex2/english/epw/epw.cd"):
        row = _parse_celex_row(line)
        wordform = _normalize(row[1])
        # Throws out multiword entries.
        if " " in wordform:
            continue
        # Eliminates syllable boundaries, known to be inconsistent.
        pron = row[6].replace("-", "")
        cursor.execute(
            """
            INSERT INTO pronunciation (
                wordform,
                dialect,
                source,
                standard,
                pronunciation,
                is_observed
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "UK", "CELEX", "DISC", pron, True),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX pronunciations")
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
        # Skips lines without a morphological analysis.
        if morph_sp == "NULL" or morph_sp is None:
            continue
        if nmorph == "NULL" or nmorph is None:
            continue
        cursor.execute(
            """
            INSERT INTO segmentation (
                wordform,
                source,
                nmorph,
                segmentation
                ) VALUES (?, ?, ?, ?)
            """,
            (wordform, "ELP", nmorph, morph_sp),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} ELP analyses")
    conn.commit()


# SUBTLEX-UK.


def _subtlex_uk(conn: sqlite3.Connection) -> None:
    """Collects SUBTLEX-UK frequencies."""
    cursor = conn.cursor()
    counter = 0
    url = "https://osf.io/download/d3jbg/"
    xlsx = _request_url_file_resource(url)
    # Disables parsing "nan" as, well, `nan`.
    data = pandas.read_excel(
        xlsx, engine="openpyxl", keep_default_na=False, na_values=[]
    )
    for wordform, freq in zip(data.Spelling, data.FreqCount):
        wordform = _normalize(wordform)
        # Inserts data with a placeholder for freq_per_million.
        cursor.execute(
            """
                INSERT INTO frequency (
                    wordform,
                    source,
                    raw_frequency,
                    freq_per_million
                    ) VALUES (?, ?, ?, ?)
                """,
            (wordform, "SUBTLEX-UK", freq, 0),
        )
        counter += 1
    assert counter, "No data read"
    cursor.execute(
        "SELECT SUM(raw_frequency) FROM frequency WHERE source='SUBTLEX-UK'"
    )
    total_freq = cursor.fetchone()[0]
    assert total_freq > 0, "Total frequency must be greater than zero."
    cursor.execute(
        """
        UPDATE frequency
            SET freq_per_million =
            ROUND(CAST(raw_frequency AS REAL) * 1000000 / ?, 2)
            WHERE source = 'SUBTLEX-UK'
        """,
        (total_freq,),
    )
    logging.info(f"Collected {counter:,} SUBTLEX-UK frequencies")
    conn.commit()


# SUBTLEX-US.


def _subtlex_us(conn: sqlite3.Connection) -> None:
    """Collects SUBTLEX-US frequencies."""
    cursor = conn.cursor()
    counter = 0
    url = "https://osf.io/download/7wx25/"
    xlsx = _request_url_file_resource(url)
    # Disables parsing "nan" as, well, `nan`.
    data = pandas.read_excel(
        xlsx, engine="openpyxl", keep_default_na=False, na_values=[]
    )
    for wordform, freq in zip(data.Word, data.FREQcount):
        wordform = _normalize(wordform)
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
    cursor.execute(
        "SELECT SUM(raw_frequency) FROM frequency WHERE source = 'SUBTLEX-US'"
    )
    total_freq = cursor.fetchone()[0]
    assert total_freq > 0, "Total frequency must be greater than zero."
    cursor.execute(
        """
        UPDATE frequency
            SET freq_per_million =
            ROUND(CAST(raw_frequency AS REAL) * 1000000 / ?, 2)
            WHERE source = 'SUBTLEX-US'
        """,
        (total_freq,),
    )
    logging.info(f"Collected {counter:,} SUBTLEX-US frequencies")
    conn.commit()


# UDLexicons.


def _udlexicons(conn: sqlite3.Connection) -> None:
    """Collects UDLexicons analyses."""
    cursor = conn.cursor()
    counter = 0
    url = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
    path = "UDLexicons.0.2/UDLex_English-Apertium.conllul"
    archive = _request_url_zip_resource(url)
    # This is complicated enough we'll do it by index.
    for tags in csv.reader(_zip_lines(archive, path), delimiter="\t"):
        # Skips multiword expressions.
        if tags[0].startswith("0-"):
            continue
        wordform = _normalize(tags[2])
        lemma = _normalize(tags[3])
        if lemma == "_":
            continue
        ud_tag = f"{tags[4]}|{tags[6]}"
        cursor.execute(
            """
            INSERT INTO features (
                wordform,
                source,
                lemma,
                tags
                ) VALUES (?, ?, ?, ?)
            """,
            (wordform, "UDLexicons", lemma, ud_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UDLexicon analyses")
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
        um_tag = _normalize(features)
        cursor.execute(
            """
            INSERT INTO features (
                wordform,
                source,
                lemma,
                tags
                ) VALUES (?, ?, ?, ?)
            """,
            (wordform, "UniMorph", lemma, um_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UniMorph analyses")
    conn.commit()


# WikiPron-UK.


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
            """INSERT INTO pronunciation (
                wordform,
                dialect,
                source,
                standard,
                pronunciation,
                is_observed
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
            (wordform, "UK", "WikiPron UK", "IPA", pron, True),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron UK pronunciations")
    conn.commit()


# WikiPron-US.


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
            INSERT INTO pronunciation (
                wordform,
                dialect,
                source,
                standard,
                pronunciation,
                is_observed
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "US", "WikiPron US", "IPA", pron, True),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron US pronunciations")
    conn.commit()


def main():
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description="Creates a CityLex lexicon")
    parser.add_argument(
        "--all-free", action="store_true", help="extract all free data sources"
    )
    parser.add_argument(
        "--celex",
        action="store_true",
        help="extract CELEX data (proprietary use agreement): "
        "http://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf",
    )
    parser.add_argument(
        "--elp",
        action="store_true",
        help="extract ELP data (CC BY-NC 4.0): "
        "http://creativecommons.org/licenses/by-nc/4.0/",
    )
    parser.add_argument(
        "--subtlex-uk",
        action="store_true",
        help="extract SUBTLEX-UK data (CC BY-NC-ND 2.0): "
        "http://creativecommons.org/licenses/by-nc-nd/2.0/",
    )
    parser.add_argument(
        "--subtlex-us",
        action="store_true",
        help="extract SUBTLEX-US data (CC BY-NC-ND 2.0): "
        "http://creativecommons.org/licenses/by-nc-nd/2.0/",
    )
    parser.add_argument(
        "--udlexicons",
        action="store_true",
        help="extract Apertium UDLexicons data (GPL 3.0): "
        "https://opensource.org/licenses/GPL-3.0",
    )
    parser.add_argument(
        "--unimorph",
        action="store_true",
        help="extract UniMorph data (CC BY-SA 2.0): "
        "http://creativecommons.org/licenses/by-sa/2.0/",
    )
    parser.add_argument(
        "--wikipron-uk",
        action="store_true",
        help="extract WikiPron UK data (CC BY-SA 3.0 Unported): "
        "http://creativecommons.org/licenses/by-sa/3.0/",
    )
    parser.add_argument(
        "--wikipron-us",
        action="store_true",
        help="extract WikiPron US data (CC BY-SA 3.0 Unported): "
        "http://creativecommons.org/licenses/by-sa/3.0/",
    )
    args = parser.parse_args()
    conn = sqlite3.connect(DB_PATH)
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
            tags TEXT NOT NULL
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS segmentation (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            nmorph INTEGER NOT NULL,
            segmentation TEXT NOT NULL
        )
    """
    )
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
    if not args:
        logging.error("No data sources selected")
        logging.error("Run `citylex --help` for more information")
        exit(1)
    conn.close()
    logging.info("Success!")


if __name__ == "__main__":
    main()
