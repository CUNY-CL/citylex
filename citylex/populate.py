"""Populates the CityLex database."""

import argparse
import csv
import io
import logging
import os
import sqlite3
import unicodedata
import zipfile

from typing import Dict, Iterator, List

import pandas  # type: ignore
import requests

from citylex import features

DB_PATH = "citylex.db"

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


def _celex(conn: sqlite3.Connection, celex_path: str) -> None:
    """Collects CELEX data and inserts it into database."""
    cursor = conn.cursor()
    # Frequencies.
    counter = 0
    path = os.path.join(celex_path, "english/efw/efw.cd")
    with open(path, "r") as source:
        for line in source:
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
    cursor.execute("SELECT SUM(raw_frequency) FROM frequency")
    total_freq = cursor.fetchone()[0]
    assert total_freq > 0, "Total frequency must be greater than zero."
    # Updates freq_per_million for all entries.
    cursor.execute(
        """
        UPDATE frequency
            SET freq_per_million =
            ROUND(CAST(raw_frequency AS REAL) * 1000000 / ?, 2)
        """,
        (total_freq,),
    )
    logging.info(f"Collected {counter:,} CELEX frequencies")
    # Morphology.
    # Reads lemma information.
    path = os.path.join(celex_path, "english/eml/eml.cd")
    lemma_info: Dict[int, str] = {}
    counter = 0
    with open(path, "r") as source:
        for line in source:
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
    path = os.path.join(celex_path, "english/emw/emw.cd")
    with open(path, "r") as source:
        for line in source:
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
            ud_tag = features.tag_to_tag("CELEX", "UD", celex_tag)
            um_tag = features.tag_to_tag("CELEX", "UniMorph", celex_tag)
            cursor.execute(
                """
                INSERT INTO features (
                    wordform,
                    source,
                    lemma,
                    celex_tags,
                    ud_tags,
                    um_tags
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                (wordform, "CELEX", lemma, celex_tag, ud_tag, um_tag),
            )
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX analyses")
    # Pronunciations.
    counter = 0
    path = os.path.join(celex_path, "english/epw/epw.cd")
    with open(path, "r") as source:
        for line in source:
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
    source = _request_url_resource(url)
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
    counter = 0
    url = (
        "https://web.archive.org/web/20211125032415/"
        "http://crr.ugent.be/papers/SUBTLEX-UK.xlsx"
    )
    mock_zip_file = _request_url_mock_file(url)
    cursor = conn.cursor()
    with pandas.ExcelFile(mock_zip_file, engine="openpyxl") as source:
        sheet = source.sheet_names[0]
        # Disables parsing "nan" as, well, `nan`.
        df = source.parse(sheet, na_values=[], keep_default_na=False)
        gen = zip(df.Spelling, df.FreqCount, df.CD_count)
        for wordform, freq, cd in gen:
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
    logging.info(f"Collected {counter:,} SUBTLEX-UK frequencies")
    conn.commit()


# SUBTLEX-US.


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


# UDLexicons.


def _udlexicons(conn: sqlite3.Connection) -> None:
    """Collects UDLexicons analyses."""
    counter = 0
    cursor = conn.cursor()
    url = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
    path = "UDLexicons.0.2/UDLex_English-Apertium.conllul"
    source = _request_url_zip_resource(url, path)
    for line in source:
        tags = line.rstrip().split("\t")
        # Skips multiword expressions.
        if tags[0].startswith("0-"):
            continue
        wordform = _normalize(tags[2])
        lemma = _normalize(tags[3])
        if lemma == "_":
            continue
        ud_tag = f"{tags[4]}|{tags[6]}"
        celex_tag = features.tag_to_tag("UD", "CELEX", ud_tag)
        um_tag = features.tag_to_tag("UD", "UniMorph", ud_tag)
        cursor.execute(
            """
            INSERT INTO features (
                wordform,
                source,
                lemma,
                celex_tags,
                ud_tags,
                um_tags
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "UDLexicons", lemma, celex_tag, ud_tag, um_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UDLexicon analyses")
    conn.commit()


# UniMorph.


def _unimorph(conn: sqlite3.Connection) -> None:
    """Collects UniMorph analyses."""
    counter = 0
    cursor = conn.cursor()
    url = "https://raw.githubusercontent.com/unimorph/eng/master/eng"
    source = _request_url_resource(url)
    for drow in csv.DictReader(
        source, fieldnames=["lemma", "wordform", "features"], delimiter="\t"
    ):
        wordform = _normalize(drow["wordform"])
        lemma = _normalize(drow["lemma"])
        um_tag = drow["features"]
        # Skips lines without features.
        if not um_tag or um_tag == "NULL":
            continue
        celex_tag = features.tag_to_tag("UniMorph", "CELEX", um_tag)
        ud_tag = features.tag_to_tag("UniMorph", "UD", um_tag)
        cursor.execute(
            """
            INSERT INTO features (
                wordform,
                source,
                lemma,
                celex_tags,
                ud_tags,
                um_tags
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (wordform, "UniMorph", lemma, celex_tag, ud_tag, um_tag),
        )
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UniMorph analyses")
    conn.commit()


# WikiPron-UK.


def _wikipron_uk(conn: sqlite3.Connection) -> None:
    """Collects WikiPron UK pronunciations."""
    counter = 0
    cursor = conn.cursor()
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/scrape/tsv/eng_latn_uk_broad_filtered.tsv"
    )
    source = _request_url_resource(url)
    for drow in csv.DictReader(
        source, fieldnames=["wordform", "pronunciation"], delimiter="\t"
    ):
        wordform = _normalize(drow["wordform"])
        pron = drow["pronunciation"]
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
    counter = 0
    cursor = conn.cursor()
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/scrape/tsv/eng_latn_us_broad_filtered.tsv"
    )
    source = _request_url_resource(url)
    for drow in csv.DictReader(
        source, fieldnames=["wordform", "pronunciation"], delimiter="\t"
    ):
        wordform = _normalize(drow["wordform"])
        pron = drow["pronunciation"]
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
        "--celex-path",
        help="path to CELEX directory (usually ends in `celex2`)",
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
            celex_tags TEXT,
            ud_tags TEXT,
            um_tags TEXT
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
    if args.celex:
        if not args.celex_path:
            logging.error("CELEX requested but --celex_path was not specified")
            exit(1)
        _celex(conn, args.celex_path)
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