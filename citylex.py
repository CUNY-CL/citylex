#!/usr/bin/env python
"""Creates a CityLex lexicon."""

import argparse
import csv
import io
import logging
import os
import pkg_resources
import re
import sys
import unicodedata
import zipfile

from typing import Iterator, List

from google.protobuf import text_format

import pandas
import requests

import citylex_pb2



def _normalize(field: str) -> str:
    """Performs basic Unicode normalization and casefolding on field."""
    return unicodedata.normalize("NFC", field).casefold()


# Helpers for downloading from URLs.


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


def _parse_celex_row(line: str) -> List[str]:
    """Parses a single line of CELEX."""
    return line.rstrip().split("\\")


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
            ptr = lexicon.entry[wordform]
            # Add to the sum if it's already defined.
            ptr.celex_freq += freq
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX frequencies")
    # TODO: Add morphology.
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
            # TODO: what ought to be done here?
            # Eliminates inconsistent syllable boundaries.
            pron = row[6].replace("-", "")
            ptr = lexicon.entry[wordform]
            ptr.celex_pron.append(pron)
            counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CELEX pronunciations")


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
        ptr = lexicon.entry[wordform]
        ptr.cmudict_pron.append(pron)
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} CMUdict pronunciations")


def _elp(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects ELP analyses."""
    counter = 0
    url = "https://github.com/kylebgorman/ELP-annotations/raw/master/ELP.csv"
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


def _udlexicons(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects UDLexicons analyses."""
    counter = 0
    # TODO: We chose not to use the EnLex data here, which looks quite
    # messy by comparison; maybe revisit this decision someday.
    url = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
    path = "UDLexicons.0.2/UDLex_English-Apertium.conllul"
    source = _request_url_zip_resource(url, path)
    for line in source:
        pieces = line.rstrip().split("\t")
        # Skips multiword expressions.
        # TODO: Is there a more elegant way to do this?
        if pieces[0].startswith("0-"):
            continue
        wordform = _normalize(pieces[2])
        ptr = lexicon.entry[wordform]
        lemma = _normalize(pieces[3])
        entry = ptr.udlexicons_morph.add()
        # Ignores unspecified lemmata.
        if lemma != "_":
            entry.lemma = lemma
        entry.pos = pieces[4]
        features = pieces[6]
        # Ignores unspecified feature bundles.
        if features != "_":
            entry.features = features
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UDLexicon analyses")


def _unimorph(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects UniMorph analyses."""
    counter = 0
    unimorph_url = "http://github.com/unimorph/eng/raw/master/eng"
    for line in _request_url_resource(unimorph_url):
        line = line.rstrip()
        if not line:
            continue
        (lemma, wordform, features) = line.split("\t", 2)
        wordform = _normalize(wordform)
        lemma = _normalize(lemma)
        ptr = lexicon.entry[wordform]
        entry = ptr.unimorph_morph.add()
        entry.lemma = lemma
        entry.features = features
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} UniMorph analyses")


def _wikipron(lexicon: citylex_pb2.Lexicon) -> None:
    """Collects WikiPron pronunciations."""
    counter = 0
    url = (
        "https://raw.githubusercontent.com/kylebgorman/"
        "wikipron/master/languages/wikipron/tsv/eng_phonemic.tsv"
    )
    for line in _request_url_resource(url):
        (wordform, pron) = line.rstrip().split("\t", 1)
        wordform = _normalize(wordform)
        ptr = lexicon.entry[wordform]
        ptr.wikipron_pron.append(pron)
        counter += 1
    assert counter, "No data read"
    logging.info(f"Collected {counter:,} WikiPron pronunciations")


def main() -> None:
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description=__doc__)
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
        "--celex",
        action="store_true",
        help="extract CELEX data (proprietary use agreement): "
        "http://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf",
    )
    parser.add_argument(
        "--celex_path",
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
        "--subtlex_uk",
        action="store_true",
        help="extract SUBTLEX-UK data (CC BY-NC-ND 2.0): "
        "http://creativecommons.org/licenses/by-nc-nd/2.0/",
    )
    parser.add_argument(
        "--subtlex_us",
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
        "--wikipron",
        action="store_true",
        help="extract WikiPron data (CC BY-SA 3.0 Unported): "
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
    if args.cmudict:
        _cmudict(lexicon)
        fieldnames.append("cmudict_pron")
    if args.elp:
        _elp(lexicon)
        fieldnames.extend(["elp_morph_sp", "elp_nmorph"])
    if args.subtlex_uk:
        _subtlex_uk(lexicon)
        fieldnames.extend(["subtlex_uk_freq", "subtlex_uk_cd"])
    if args.subtlex_us:
        _subtlex_us(lexicon)
        fieldnames.extend(["subtlex_us_freq", "subtlex_us_cd"])
    if args.udlexicons:
        _udlexicons(lexicon)
        fieldnames.append("udlexicons_morph")
    if args.unimorph:
        _unimorph(lexicon)
        fieldnames.append("unimorph_morph")
    if args.wikipron:
        _wikipron(lexicon)
        fieldnames.append("wikipron_pron")
    if not fieldnames:
        logging.error("No data sources selected")
        logging.error("Run `citylex --help` for more information")
        exit(1)

    logging.info("Writing out textproto")
    version = pkg_resources.get_distribution("citylex").version
    with open(args.output_textproto_path, "w") as sink:
        print(f"# CityLex ({version}) lexicon generated using:", file=sink)
        print(f"#     {' '.join(sys.argv)}", file=sink)
        text_format.PrintMessage(lexicon, sink, as_utf8=True)
        logging.debug("Wrote %d entries", len(lexicon.entry))

    logging.info("Writing out TSV")
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
                if field.endswith("_pron"):
                    # Deduplicate and join on '^'.
                    drow[field] = "^".join(frozenset(attr))
                elif field.endswith("_morph"):
                    # Make triples and join on '^'.
                    triples = [
                        f"{triple.lemma}_{triple.pos}_{triple.features}"
                        for triple in attr
                    ]
                    drow[field] = "^".join(triples)
                elif entry.HasField(field):
                    drow[field] = attr
            tsv_writer.writerow(drow)

    logging.info("Success!")
