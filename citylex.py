#!/usr/bin/env python
"""Creates a CityLex lexicon.

For more information on CityLex, see:

https://github.com/kylebgorman/citylex
"""

import argparse
import csv
import datetime
import io
import logging
import os
import pkg_resources
import re
import sys
import unicodedata
import zipfile

from typing import Dict, Iterator, List

from google.protobuf import text_format  # type: ignore

import pandas  # type: ignore
import requests

import citylex_pb2   # type: ignore


def read_textproto(path: str) -> citylex_pb2.Lexicon:
    """Parses textproto."""
    lexicon = citylex_pb2.Lexicon()
    with open(path, "r") as source:
        text_format.ParseLines(source, lexicon)
    return lexicon


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


def _request_url_zip_resource(url: str, path: str) -> Iterator[str]:
    """Requests a zip file by URL and the path to the desired file."""
    logging.info("Requesting URL: %s", url)
    response = requests.get(url)
    response.raise_for_status()
    # Pretends to be a local zip file.
    mock_zip_file = io.BytesIO(response.content)
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


def _celex(celex_path: str, lexicon: citylex_pb2.Lexicon) -> None:
    """Collects CELEX data."""
    # Frequencies.
    counter = 0
    path = os.path.join(celex_path, "english/efw/efw.cd")
    with open(path, "r") as source:
        for line in source:
            row = _parse_celex_row(line)
            wordform = _normalize(row[1])
            # Throws out multiword entries.
            if " " in wordform:
                continue
            freq = int(row[3])
            lexicon.entry[wordform].celex_freq += freq
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX frequencies")
    # Morphology.
    # Reads lemmata information.
    path = os.path.join(celex_path, "english/eml/eml.cd")
    lemma_info: Dict[int, str] = {}
    with open(path, "r") as source:
        for line in source:
            row = _parse_celex_row(line)
            li = int(row[0])
            lemma = _normalize(row[1])
            if " " in lemma:
                continue
            lemma_info[li] = lemma
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
            # TODO: Avoid duplication.
            entry = lexicon.entry[wordform].celex_morph.add()
            entry.lemma = lemma
            entry.features = features
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
            # We check for duplicates.
            celex_pron = lexicon.entry[wordform].celex_pron
            if pron not in celex_pron:
                celex_pron.append(pron)
                counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX pronunciations")


# CMUDict.


def _cmudict(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects CMUdict pronuciations."""
    counter = 0
    url = "http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b"
    for line in _request_url_resource(url):
        if line.startswith(";"):
            continue
        (wordform, pron) = line.rstrip().split("  ", 1)
        wordform = _normalize(wordform)
        # Removes "numbering" on wordforms like `BASS(1)`.
        wordform = re.sub(r"\(\d+\)$", "", wordform)
        lexicon.entry[wordform].cmudict_pron.append(pron)
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CMUdict pronunciations")


# ELP.


def _elp(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects ELP analyses."""
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "ELP-annotations/master/ELP.csv"
    )
    source = _request_url_resource(url)
    for drow in csv.DictReader(source):
        wordform = _normalize(drow["Word"])
        ptr = lexicon.entry[wordform]
        morph_sp = drow["MorphSp"]
        nmorph = drow["NMorph"]
        # Skips lines without a morphological analysis.
        if morph_sp == "NULL" or morph_sp is None:
            continue
        if nmorph == "NULL" or nmorph is None:
            continue
        ptr.elp_morph_sp = morph_sp
        ptr.elp_nmorph = int(nmorph)
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} ELP analyses")


# SUBTLEX-UK.


def _subtlex_uk(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects SUBTLEX-UK frequencies."""
    counter = 0
    url = "http://crr.ugent.be/papers/SUBTLEX-UK.xlsx"
    logging.info("Requesting URL: %s", url)
    with pandas.ExcelFile(url) as source:
        sheet = source.sheet_names[0]
        # Disables parsing "nan" as, well, `nan`.
        df = source.parse(sheet, na_values=[], keep_default_na=False)
        gen = zip(df.Spelling, df.FreqCount, df.CD_count)
        for (wordform, freq, cd) in gen:
            wordform = _normalize(wordform)
            ptr = lexicon.entry[wordform]
            ptr.subtlex_uk_freq = freq
            ptr.subtlex_uk_cd = cd
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} SUBTLEX-UK frequencies")


# SUBTLEX-US.


def _subtlex_us(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects SUBTLEX-US frequencies."""
    counter = 0
    url = (
        "http://crr.ugent.be/papers/SUBTLEX-US_frequency_list_with_PoS_"
        "information_final_text_version.zip"
    )
    path = "SUBTLEX-US frequency list with PoS information text version.txt"
    source = _request_url_zip_resource(url, path)
    for drow in csv.DictReader(source, delimiter="\t"):
        wordform = _normalize(drow["Word"])
        ptr = lexicon.entry[wordform]
        ptr.subtlex_us_freq = int(drow["FREQcount"])
        ptr.subtlex_us_cd = int(drow["CDcount"])
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


def _udlexicons(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects UDLexicons analyses."""
    counter = 0
    # TODO: We do not use the EnLex data here, which looks quite messy by
    # comparison; maybe revisit this decision someday.
    url = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
    path = "UDLexicons.0.2/UDLex_English-Apertium.conllul"
    source = _request_url_zip_resource(url, path)
    for line in source:
        tags = line.rstrip().split("\t")
        # Skips multiword expressions.
        # TODO: Is there a more elegant way to do this?
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
        # TODO: Avoid duplication.
        entry = lexicon.entry[wordform].udlexicons_morph.add()
        entry.lemma = lemma
        entry.features = features
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UDLexicon analyses")


# UniMorph.


def _unimorph(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects UniMorph analyses."""
    counter = 0
    url = "https://raw.githubusercontent.com/unimorph/eng/master/eng"
    for line in _request_url_resource(url):
        line = line.rstrip()
        if not line:
            continue
        (lemma, wordform, features) = line.split("\t", 2)
        wordform = _normalize(wordform)
        lemma = _normalize(lemma)
        # TODO: Avoid duplication.
        entry = lexicon.entry[wordform].unimorph_morph.add()
        entry.lemma = lemma
        entry.features = features
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UniMorph analyses")


# WikiPron-UK.


def _wikipron_uk(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects WikiPron US pronunciations."""
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/wikipron/tsv/eng_uk_phonemic.tsv"
    )
    for line in _request_url_resource(url):
        (wordform, pron, *_) = line.rstrip().split("\t")
        wordform = _normalize(wordform)
        lexicon.entry[wordform].wikipron_uk_pron.append(pron)
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron UK pronunciations")


# WikiPron-US.


def _wikipron_us(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects WikiPron US pronunciations."""
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/data/wikipron/tsv/eng_us_phonemic.tsv"
    )
    for line in _request_url_resource(url):
        (wordform, pron, *_) = line.rstrip().split("\t")
        wordform = _normalize(wordform)
        lexicon.entry[wordform].wikipron_us_pron.append(pron)
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron US pronunciations")


def main() -> None:
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description="Creates a CityLex lexicon")
    # Output paths.
    parser.add_argument(
        "--output_textproto_path",
        default="citylex.textproto",
        help="output textproto path (default: %(default)s)",
    )
    parser.add_argument(
        "--output_tsv_path",
        default="citylex.tsv",
        help="output TSV path (default: %(default)s)",
    )
    # Enables specific data sources.
    parser.add_argument(
        "--all-free",
        action="store_true",
        help="extracts all free data sources"
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
        "--cmudict",
        action="store_true",
        help="extract CMUdict data (BSD 2-clause): "
        "http://opensource.org/licenses/BSD-2-Clause",
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
        help="extract UniMorph data (C BY-SA 2.0): "
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

    # Builds TSV fieldnames and lexicon.
    lexicon = citylex_pb2.Lexicon()
    fieldnames = []
    if args.celex:
        if not args.celex_path:
            logging.error("CELEX requested but --celex_path was not specified")
            exit(1)
        _celex(args.celex_path, lexicon)
        fieldnames.extend(["celex_freq", "celex_pron"])
    if args.all_free or args.cmudict:
        _cmudict(lexicon)
        fieldnames.append("cmudict_pron")
    if args.all_free or args.elp:
        _elp(lexicon)
        fieldnames.extend(["elp_morph_sp", "elp_nmorph"])
    if args.all_free or args.subtlex_uk:
        _subtlex_uk(lexicon)
        fieldnames.extend(["subtlex_uk_freq", "subtlex_uk_cd"])
    if args.all_free or args.subtlex_us:
        _subtlex_us(lexicon)
        fieldnames.extend(["subtlex_us_freq", "subtlex_us_cd"])
    if args.all_free or args.udlexicons:
        _udlexicons(lexicon)
        fieldnames.append("udlexicons_morph")
    if args.all_free or args.unimorph:
        _unimorph(lexicon)
        fieldnames.append("unimorph_morph")
    if args.all_free or args.wikipron_uk:
        _wikipron_uk(lexicon)
        fieldnames.append("wikipron_uk_pron")
    if args.all_free or args.wikipron_us:
        _wikipron_us(lexicon)
        fieldnames.append("wikipron_us_pron")
    if not fieldnames:
        logging.error("No data sources selected")
        logging.error("Run `citylex --help` for more information")
        exit(1)

    logging.info("Writing out textproto...")
    version = pkg_resources.get_distribution("citylex").version
    with open(args.output_textproto_path, "w") as sink:
        print(f"# CityLex ({version}) lexicon:", file=sink)
        print(f"#   date: {datetime.date.today()}", file=sink)
        print(f"#   command: {' '.join(sys.argv)}", file=sink)
        text_format.PrintMessage(lexicon, sink, as_utf8=True)
        logging.debug("Wrote %d entries", len(lexicon.entry))

    logging.info("Writing out TSV...")
    with open(args.output_tsv_path, "w") as sink:
        tsv_writer = csv.DictWriter(
            sink,
            delimiter="\t",
            fieldnames=["wordform"] + fieldnames,
            restval="NA",
            lineterminator="\n",
        )
        tsv_writer.writeheader()
        # Sorting for stability.
        for (wordform, entry) in sorted(lexicon.entry.items()):
            drow = {"wordform": wordform}
            for field in fieldnames:
                attr = getattr(entry, field)
                if not attr:
                    continue
                if field.endswith("_pron"):
                    # Join on '^'.
                    drow[field] = "^".join(attr)
                elif field.endswith("_morph"):
                    # Make pairs and join on '^'.
                    pairs = [f"{pair.lemma}_{pair.features}" for pair in attr]
                    drow[field] = "^".join(pairs)
                elif entry.HasField(field):
                    drow[field] = attr
            tsv_writer.writerow(drow)

    logging.info("Success!")
