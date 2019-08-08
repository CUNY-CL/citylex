#!/usr/bin/env python
"""Creates textproto CityLex lexicon."""

import argparse
import csv
import io
import logging
import re
import zipfile

from typing import Iterator, List

from google.protobuf import text_format

import pandas
import requests

import citylex_pb2

## Paths to data resources that have to be local.
# TODO(kbg): Make these into flags.

CELEX_FREQ_PATH = "data/celex2/english/efw/efw.cd"
CELEX_MORPH_LEMMA_PATH = "data/celex2/english/eml/eml.cd"
CELEX_PRON_PATH = "data/celex2/english/epw/epw.cd"
ELP_PATH = "data/ELP.csv"

## URLs to automatically downloadable data.
CMU_PRON_URL = (
    "http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b"
)
SUBTLEX_UK_URL = "http://crr.ugent.be/papers/SUBTLEX-UK.xlsx"
SUBTLEX_US_URL = "http://crr.ugent.be/papers/SUBTLEX-US_frequency_list_with_PoS_information_final_text_version.zip"
SUBTLEX_US_PATH = (
    "SUBTLEX-US frequency list with PoS information text version.txt"
)
UNIMORPH_URL = "http://github.com/unimorph/eng/raw/master/eng"
UDLEXICONS_URL = "http://atoll.inria.fr/~sagot/UDLexicons.0.2.zip"
UDLEXICONS_PATH = "UDLexicons.0.2/UDLex_English-Apertium.conllul"

## Fieldnames.

# Fieldnames which require simple deduplication and joining.
REPEATED_STRING_FIELDNAMES = frozenset(["celex_pron", "cmu_pron"])

# Fieldnames which require complex deduplication and joining.
MORPHENTRY_FIELDNAMES = frozenset(["udlexicons", "unimorph"])


def _parse_celex_row(line: str) -> List[str]:
    """Parses a single line of CELEX."""
    return line.rstrip().split("\\")


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
    # Opens the ZIP file, and then the specific enclosed file.
    with zipfile.ZipFile(mock_zip_file, "r").open(path, "r") as source:
        for line in source:
            yield line.decode("utf8")


def main(args: argparse.Namespace) -> None:

    # Builds TSV fieldnames.
    fieldnames = []
    if args.enable_celex:
        fieldnames.extend(["celex_freq", "celex_pron"])
    if args.enable_cmu:
        fieldnames.append("cmu_pron")
    if args.enable_elp:
        fieldnames.extend(["elp_morph_sp", "elp_nmorph"])
    if args.enable_subtlex:
        fieldnames.extend(
            [
                "subtlex_uk_freq",
                "subtlex_uk_cd",
                "subtlex_us_freq",
                "subtlex_us_cd",
            ]
        )
    if args.enable_udlexicons:
        fieldnames.append("udlexicons")
    if args.enable_unimorph:
        fieldnames.append("unimorph")
    if not fieldnames:
        logging.error("No data sources selected: use --enable_* flags")
        exit(1)

    lexicon = citylex_pb2.Lexicon()

    if args.enable_celex:
        # CELEX/COBUILD frequencies.
        counter = 0
        with open(CELEX_FREQ_PATH, "r") as source:
            for line in source:
                row = _parse_celex_row(line)
                wordform = row[1].casefold()
                # Throws out multiword entries.
                if " " in wordform:
                    continue
                freq = int(row[3])
                ptr = lexicon.entry[wordform]
                # Add to the sum if it's already defined.
                ptr.celex_freq += freq
                counter += 1
        logging.info(f"Collected {counter:,} CELEX frequencies")

        # TODO: Add CELEX morphology.

        # CELEX pronunciations.
        counter = 0
        with open(CELEX_PRON_PATH, "r") as source:
            for line in source:
                row = _parse_celex_row(line)
                wordform = row[1].casefold()
                # Throws out multiword entries.
                if " " in wordform:
                    continue
                # FIXME(kbg): what ought to be done here?
                pron = row[6].replace(
                    "-", ""
                )  # Eliminates syllable boundaries.
                ptr = lexicon.entry[wordform]
                ptr.celex_pron.append(pron)
                counter += 1
        logging.info(f"Collected {counter:,} CELEX pronunciations")

    if args.enable_cmu:
        # CMU pronunciations.
        counter = 0
        for line in _request_url_resource(CMU_PRON_URL):
            if line.startswith(";"):
                continue
            (wordform, pron) = line.rstrip().split("  ", 1)
            wordform = wordform.casefold()
            # Removes "numbering" on wordforms like `BASS(1)`.
            wordform = re.sub(r"\(\d+\)$", "", wordform)
            ptr = lexicon.entry[wordform]
            ptr.cmu_pron.append(pron)
            counter += 1
        logging.info(f"Collected {counter:,} CMU pronunciations")

    if args.enable_elp:
        # ELP morphology.
        counter = 0
        with open(ELP_PATH, "r") as source:
            for drow in csv.DictReader(source):
                wordform = drow["Word"].casefold()
                ptr = lexicon.entry[wordform]
                morph_sp = drow["MorphSp"]
                # Skips lines without a morphological analysis.
                if morph_sp == "NULL":
                    continue
                ptr.elp_morph_sp = morph_sp
                ptr.elp_nmorph = int(drow["NMorph"])
                counter += 1
        logging.info(f"Collected {counter:,} ELP analyses")

    if args.enable_subtlex:

        # SUBTLEX-UK frequencies.
        counter = 0
        # Pandas can magically grab URLs.
        with pandas.ExcelFile(SUBTLEX_UK_URL) as source:
            sheet = source.sheet_names[0]
            # Disables parsing "nan" as, well, `nan`.
            df = source.parse(sheet, na_values=[], keep_default_na=False)
            gen = zip(df.Spelling, df.FreqCount, df.CD_count)
            for (wordform, freq, cd) in gen:
                wordform = wordform.casefold()
                ptr = lexicon.entry[wordform]
                ptr.subtlex_uk_freq = freq
                ptr.subtlex_uk_cd = cd
                counter += 1
        logging.info(f"Collected {counter:,} SUBTLEX-UK frequencies")

        # SUBTLEX-US frequencies.
        counter = 0
        source = _request_url_zip_resource(SUBTLEX_US_URL, SUBTLEX_US_PATH)
        for drow in csv.DictReader(source, delimiter="\t"):
            wordform = drow["Word"].casefold()
            ptr = lexicon.entry[wordform]
            ptr.subtlex_us_freq = int(drow["FREQcount"])
            ptr.subtlex_us_cd = int(drow["CDcount"])
            counter += 1
        logging.info(f"Collected {counter:,} SUBTLEX-US frequencies")

    if args.enable_udlexicons:
        # UDLexicon morphology.
        # TODO(kbg): We chose not to use the EnLex data here, which looks quite
        # messy by comparison; maybe revisit this decision someday.
        counter = 0
        source = _request_url_zip_resource(UDLEXICONS_URL, UDLEXICONS_PATH)
        for line in source:
            pieces = line.rstrip().split("\t")
            # Skips complex expressions.
            # TODO(kbg): Is there a more elegant way to do this?
            if pieces[0].startswith("0-"):
                continue
            wordform = pieces[2].casefold()
            ptr = lexicon.entry[wordform]
            lemma = pieces[3].casefold()
            entry = ptr.udlexicons.add()
            # Ignores unspecified lemmata.
            if lemma != "_":
                entry.lemma = lemma
            entry.pos = pieces[4]
            features = pieces[6]
            # Ignores unspecified feature bundles.
            if features != "_":
                entry.features = features
            counter += 1
        logging.info(f"Collected {counter:,} UDLexicon analyses")

    if args.enable_unimorph:
        # Unimorph.
        counter = 0
        for line in _request_url_resource(UNIMORPH_URL):
            line = line.rstrip()
            if not line:
                continue
            (lemma, wordform, features) = line.split("\t", 2)
            wordform = wordform.casefold()
            lemma = lemma.casefold()
            ptr = lexicon.entry[wordform]
            entry = ptr.unimorph.add()
            entry.lemma = lemma
            entry.features = features
            counter += 1
        logging.info(f"Collected {counter:,} UniMorph analyses")

    logging.info("Writing out textproto")
    with open(args.output_textproto_path, "w") as sink:
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
                if field in REPEATED_STRING_FIELDNAMES:
                    # Deduplicate and join on '^'.
                    drow[field] = "^".join(frozenset(getattr(entry, field)))
                elif field in MORPHENTRY_FIELDNAMES:
                    # Make triples and join on '^'.
                    triples = [
                        f"{triple.lemma}_{triple.pos}_{triple.features}"
                        for triple in getattr(entry, field)
                    ]
                    drow[field] = "^".join(triples)
                elif entry.HasField(field):
                    drow[field] = getattr(entry, field)
            tsv_writer.writerow(drow)

    logging.info("Success!")


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description=__doc__)
    # Output paths.
    parser.add_argument("--output_textproto_path", default="citylex.textproto")
    parser.add_argument("--output_tsv_path", default="citylex.tsv")
    # Enable particular data sources.
    parser.add_argument(
        "--enable_celex",
        action="store_true",
        help="Extracts CELEX data, under a proprietary use agreement: "
        "https://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf",
    )
    parser.add_argument(
        "--enable_cmu",
        action="store_true",
        help="Extracts CMU data, under BSD 2-clause license: "
        "https://opensource.org/licenses/BSD-2-Clause",
    )
    parser.add_argument(
        "--enable_elp",
        action="store_true",
        help="Extracts ELP data, under noncommercial use agreement",
    )
    parser.add_argument(
        "--enable_subtlex",
        action="store_true",
        help="Extracts SUBTLEX data, under CC BY-NC-ND 2.0 license: "
        "https://creativecommons.org/licenses/by-nc-nd/2.0/",
    )
    parser.add_argument(
        "--enable_udlexicons",
        action="store_true",
        help="Extracts Apertium UDLexicons data, under GPL 3.0 license: "
        "https://www.gnu.org/licenses/gpl-3.0.en.html",
    )
    parser.add_argument(
        "--enable_unimorph",
        action="store_true",
        help="Extracts UniMorph data, under CC BY-SA 2.0 license: "
        "https://creativecommons.org/licenses/by-sa/2.0/",
    )
    main(parser.parse_args())
