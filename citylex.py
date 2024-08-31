#!/usr/bin/env python
"""Creates a CityLex lexicon.

For more information on CityLex, see:

https://github.com/kylebgorman/citylex
"""

import argparse
import csv
import io
import logging
import os
import unicodedata
import zipfile
import sqlite3

from typing import Dict, Iterator, List

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


def _celex(conn: str, celex_path: str) -> None:
    """Collects Celex data and inserts it into database."""
    cursor = conn.cursor()
    # Frequencies
    counter = 0
    path = os.path.join(celex_path, "english/efw/efw.cd")
    total_freq = 0
    # Sum frequency of all words
    with open(path, "r") as file:
        for line in file:
            row = _parse_celex_row(line)
            wordform = _normalize(row[1])
            # Skip multiword entries
            if " " in wordform:
                continue
            freq = int(row[3])
            total_freq += freq
    if total_freq <= 0:
        raise ValueError("Total frequency is zero or negative. Cannot compute frequency per million.")
    # Insert fields into database
    with open(path, "r") as file:
        for line in file:
            row = _parse_celex_row(line)
            wordform = _normalize(row[1])
            # Throws out multiword entries.
            if " " in wordform:
                continue
            freq = int(row[3])
            freq_per_million = round((freq / total_freq) * 1_000_000, 2)
            cursor.execute("INSERT INTO frequency (wordform, source, raw_frequency, freq_per_million) VALUES (?, ?, ?, ?)", (wordform, "CELEX", freq, freq_per_million))
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX frequencies")
    # Morphology
    # Reads lemma information
    path = os.path.join(celex_path, "english/eml/eml.cd")
    lemma_info: Dict[int, str] = {}
    counter = 0
    with open(path, "r") as file:
        for line in file:
            row = _parse_celex_row(line)
            li = int(row[0])
            lemma = _normalize(row[1])
            if " " in lemma:
                continue
            lemma_info[li] = lemma
            counter += 1
    # Reads wordform information
    counter = 0
    path = os.path.join(celex_path, "english/emw/emw.cd")
    with open(path, "r") as file:
        for line in file:
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
            features = row[4]
            try:
                features = CELEX_FEATURE_MAP[row[4]]
            except KeyError:
                logging.debug(
                    "Ignoring wordform feature bundle: %s (%s)",
                    wordform,
                    features,
                )
                continue
            cursor.execute("INSERT INTO morphology (wordform, source, lemma, features) VALUES (?, ?, ?, ?)", (wordform, "CELEX", lemma, features))
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX analyses")
    # Pronunciations.
    counter = 0
    path = os.path.join(celex_path, "english/epw/epw.cd")
    with open(path, "r") as file:
        for line in file:
            row = _parse_celex_row(line)
            wordform = _normalize(row[1])
            # Throws out multiword entries.
            if " " in wordform:
                continue
            # Eliminates syllable boundaries, known to be inconsistent.
            pron = row[6].replace("-", "")
            cursor.execute("INSERT INTO pronunciation (wordform, dialect, source, standard, pronunciation, is_observed) VALUES (?, ?, ?, ?, ?, ?)", (wordform, "UK", "CELEX", "DISC", pron, 1))
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX pronunciations")


# ELP.


def _elp(conn: str) -> None:
    """Collects ELP analyses and inserts them into database."""
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
        cursor.execute("INSERT INTO segmentation (wordform, source, nmorph, segmentation) VALUES (?, ?, ?, ?)", (wordform, "ELP", nmorph, morph_sp))
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} ELP analyses")


# SUBTLEX-UK


def _subtlex_uk(conn: str) -> None:
    """Collects SUBTLEX-UK frequencies and inserts them into database."""
    counter = 0
    url = (
        "https://web.archive.org/web/20211125032415/"
        "http://crr.ugent.be/papers/SUBTLEX-UK.xlsx"
    )
    mock_zip_file = _request_url_mock_file(url)
    cursor = conn.cursor()
    with pandas.ExcelFile(mock_zip_file, engine="openpyxl") as file:
        sheet = file.sheet_names[0]
        # Disables parsing "nan" as, well, `nan`.
        df = file.parse(sheet, na_values=[], keep_default_na=False)
        gen = zip(df.Spelling, df.FreqCount, df.CD_count)
        total_freq = df.FreqCount.sum()
        if total_freq <= 0:
            raise ValueError("Total frequency is zero or negative. Cannot compute frequency per million.")
        for wordform, freq, cd in gen:
            wordform = _normalize(wordform)
            freq_per_million = round((freq / total_freq) * 1_000_000, 2)
            cursor.execute("INSERT INTO frequency (wordform, source, raw_frequency, freq_per_million) VALUES (?, ?, ?, ?)", (wordform, "SUBTLEX-UK", freq, freq_per_million))
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} SUBTLEX-UK frequencies")


# SUBTLEX-US


def _subtlex_us(conn: str) -> None:
    """Collects SUBTLEX-US frequencies and inserts them into database."""
    counter = 0
    url = (
        "https://web.archive.org/web/20211125032415/"
        "http://crr.ugent.be/papers/"
        "SUBTLEX-US_frequency_list_with_PoS_information_"
        "final_text_version.zip"
    )
    path = "SUBTLEX-US frequency list with PoS information text version.txt"
    file = _request_url_zip_resource(url, path)
    cursor = conn.cursor()
    total_freq = 0
    data = []
    for drow in csv.DictReader(file, delimiter="\t"):
        freq = int(drow["FREQcount"])
        total_freq += freq
        data.append((drow["Word"], freq))
    if total_freq <= 0:
        raise ValueError("Total frequency is zero or negative. Cannot compute frequency per million.")
    for wordform, freq in data:
        wordform = _normalize(wordform)
        freq_per_million = round((freq / total_freq) * 1_000_000, 2)
        cursor.execute("INSERT INTO frequency (wordform, source, raw_frequency, freq_per_million) VALUES (?, ?, ?, ?)", (wordform, "SUBTLEX-US", freq, freq_per_million))
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} SUBTLEX-US frequencies")


# UDLexicons.

# These transformations are based on the mappings used by McCarthy et al.
# (2018) and listed here:
#
# https://github.com/unimorph/ud-compatibility/blob/master/UD_UM/UD-UniMorph.tsv
#
# It covers four main parts of speech: adjectives, adverbs, nouns, and verbs.
UDLEXICONS_FEATURE_MAP = {
    "ADJ|_": "ADJ",  # We don't mark positive adjectives in UniMorph
    "ADJ|Degree=Cmp": "ADJ;CMPR",
    "ADJ|Degree=Sup": "ADJ;RL",  # English superlatives are "relative" ones.
    "ADV|_": "ADV",
    "NOUN|Number=Sing": "N;SG",
    "NOUN|Number=Plur": "N;PL",
    "PROPN|Number=Sing": "N;SG",
    "PROPN|Number=Plur": "N;PL",
    "PROPN|Gender=Fem|Number=Sing": "N;SG",
    "PROPN|Gender=Fem|Number=Plur": "N;PL",
    "PROPN|Gender=Masc|Number=SG": "N;SG",
    "PROPN|Gender=Masc|Number=Plur": "N;PL",
    "VERB|VerbForm=Inf": "V;NFIN",
    "VERB|Number=Sing|Person=3|Tense=Pres": "V;SG;3;PRS",
    "VERB|Tense=Past": "V;PST",
    "VERB|Tense=Pres|VerbForm=Part": "V;PTCP;PRS",
    "VERB|Tense=Past|VerbForm=Part": "V.PTCP;PST",
}
# Deliberately excluded:
# * imperatives ("VERB|Mood=Imp")
# * 1/2 present forms
# * "VERB|VerbForm=Ger"

def _udlexicons(conn: str) -> None:
    """Collects UDLexicons analyses."""
    counter = 0
    cursor = conn.cursor()
    url = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
    path = "UDLexicons.0.2/UDLex_English-Apertium.conllul"
    file = _request_url_zip_resource(url, path)
    for line in file:
        tags = line.rstrip().split("\t")
        # Skips multiword expressions.
        if tags[0].startswith("0-"):
                continue
        wordform = _normalize(tags[2])
        lemma = _normalize(tags[3])
        if lemma == "_":
            continue
        features = f"{tags[4]}|{tags[6]}"
        try:
                features = UDLEXICONS_FEATURE_MAP[features]
        except KeyError:
                logging.debug(
                    "Ignoring wordform feature bundle: %s (%s)", wordform, features
                )
                continue
        cursor.execute("INSERT INTO morphology (wordform, source, lemma, features) VALUES (?, ?, ?, ?)", (wordform, "UDLexicons", lemma, features))
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UDLexicon analyses")


# UniMorph.


def _unimorph(conn: str) -> None:
    """Collects UniMorph analyses and inserts them into the database."""
    counter = 0
    cursor = conn.cursor()
    url = "https://raw.githubusercontent.com/unimorph/eng/master/eng"
    for line in _request_url_resource(url):
        line = line.rstrip()
        if not line:
            continue
        (lemma, wordform, features) = line.split("\t", 2)
        wordform = _normalize(wordform)
        lemma = _normalize(lemma)
        cursor.execute("INSERT INTO morphology (wordform, source, lemma, features) VALUES (?, ?, ?, ?)", (wordform, "UniMorph", lemma, features))
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UniMorph analyses")


# WikiPron-UK.


def _wikipron_uk(conn: str) -> None:
    """Collects WikiPron UK pronunciations and inserts them into the database."""
    counter = 0
    cursor = conn.cursor()
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/scrape/tsv/eng_latn_uk_broad_filtered.tsv"
    )
    for line in _request_url_resource(url):
        (wordform, pron, *_) = line.rstrip().split("\t")
        wordform = _normalize(wordform)
        cursor.execute("INSERT INTO pronunciation (wordform, dialect, source, standard, pronunciation, is_observed) VALUES (?, ?, ?, ?, ?, ?)", (wordform, "UK", "WikiPron UK", "IPA", pron, 1))
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron UK pronunciations")


# WikiPron-US.


def _wikipron_us(conn: str) -> None:
    """Collects WikiPron US pronunciations and inserts them into the database."""
    counter = 0
    cursor = conn.cursor()
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/scrape/tsv/eng_latn_us_broad_filtered.tsv"
    )
    for line in _request_url_resource(url):
        (wordform, pron, *_) = line.rstrip().split("\t")
        wordform = _normalize(wordform)
        cursor.execute("INSERT INTO pronunciation (wordform, dialect, source, standard, pronunciation, is_observed) VALUES (?, ?, ?, ?, ?, ?)", (wordform, "US", "WikiPron US", "IPA", pron, 1))
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron US pronunciations")


def main():
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description="Creates a CityLex lexicon")

    parser.add_argument(
        "--db_path",
        default="citylex.db",
        help="path to database file (default: %(default)s)",
    )
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

    conn = sqlite3.connect(args.db_path)
    cursor = conn.cursor()

    logging.info("Dropping existing tables if they exist...")
    cursor.execute("DROP TABLE IF EXISTS frequency;")
    cursor.execute("DROP TABLE IF EXISTS pronunciation;")
    cursor.execute("DROP TABLE IF EXISTS morphology;")
    cursor.execute("DROP TABLE IF EXISTS segmentation;")

    logging.info("Creating tables...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS frequency (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            raw_frequency INTEGER NOT NULL,
            freq_per_million DECIMAL(5, 2) NOT NULL
        );
    """)
    cursor.execute("""    
        CREATE TABLE IF NOT EXISTS pronunciation (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            dialect TEXT NOT NULL,
            source TEXT NOT NULL,
            standard TEXT NOT NULL,
            pronunciation TEXT NOT NULL,
            is_observed BOOLEAN NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS morphology (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            lemma TEXT NOT NULL,
            features TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS segmentation (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            wordform TEXT NOT NULL,
            source TEXT NOT NULL,
            nmorph TEXT NOT NULL,
            segmentation TEXT NOT NULL
        );
    """)

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
    conn.commit()
    conn.close()

    logging.info("Success!")

main()