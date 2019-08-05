#!/usr/bin/env python
"""Creates textproto CityLex lexicon."""

## TODO(kbg): Add CELEX morphology to the best of your ability.

## TODO: Adds downloading support.
## TODO: Adds licensing support.

import argparse
import csv
import logging
import re
import string

from typing import List

from google.protobuf import text_format

import pandas

import citylex_pb2

## Paths to data resource and the associated licenses.

CELEX_FREQ = ("data/celex2/english/efw/efw.cd", "PROPRIETARY")
CELEX_MORPH_LEMMA = ("data/celex2/english/eml/eml.cd", "PROPRIETARY")
# CELEX_MORPH = ("data/celex2/english/emw/emw.cd", "PROPRIETARY")
CELEX_PRON = ("data/celex2/english/epw/epw.cd", "PROPRIETARY")
CMU_PRON = ("data/cmudict-0.7b", "BSD-2-CLAUSE")
ELP_MORPH = ("data/ELP.csv", "NONCOMMERCIAL")
SUBTLEX_UK = ("data/SUBTLEX-UK.xlsx", "CC-BY-NC-ND")
SUBTLEX_US = (
    "data/SUBTLEX-US frequency list with PoS information text version.txt",
    "CC-BY-NC-ND",
)
UDLEXICONS_APERTIUM = (
    "data/UDLexicons.0.2/UDLex_English-Apertium.conllul",
    "GPL",
)
UNIMORPH = ("data/eng", "CC_BY_SA")

## Fieldnames.
# TODO(kbg): Add support for all fields.
FIELDNAMES = [
    "wordform",
    "celex_freq",
    "celex_pron",
    "cmu_pron",
    "elp_morph_sp",
    "elp_nmorph",
    "subtlex_uk_freq",
    "subtlex_uk_cd",
    "subtlex_us_freq",
    "subtlex_us_cd",
]

# Fieldnames which require simple deduplication and joining.
REPEATED_STRING_FIELDNAMES = frozenset(["celex_pron", "cmu_pron"])

# def _parse_license(license: str) -> citylex_pb2.Source.License:
#    return citylex_pb2.Source.License.Value(license)


def _parse_celex_row(line: str) -> List[str]:
    return line.rstrip().split("\\")


def main(args: argparse.Namespace) -> None:
    lexicon = citylex_pb2.Lexicon()

    # CELEX frequency.
    (path, license) = CELEX_FREQ
    with open(path, "r") as source:
        for line in source:
            row = _parse_celex_row(line)
            wordform = row[1].casefold()
            # Throws out multiword entries.
            if " " in wordform:
                continue
            freq = int(row[3])
            lexicon.entry[wordform].celex_freq = freq

    """
    # CELEX wordform morphology.
    (path, license) = CELEX_MORPH_LEMMA
    with open(path, "r") as source:
        for line in source:
            row = _parse_celex_row(line)
            print(row)
    """

    # CELEX pronunciation.
    (path, license) = CELEX_PRON
    with open(path, "r") as source:
        for line in source:
            row = _parse_celex_row(line)
            wordform = row[1].casefold()
            # Throws out multiword entries.
            if " " in wordform:
                continue
            # FIXME(kbg): what ought to be done here?
            pron = row[6].replace("-", "")  # Eliminates syllable boundaries.
            ptr = lexicon.entry[wordform]
            ptr.celex_pron.append(pron)

    # CMU pronunciation dictionary.
    (path, license) = CMU_PRON
    # There is exactly one misencoded line, which we "ignore".
    with open(path, "r", errors="ignore") as source:
        for line in source:
            if line.startswith(";"):
                continue
            (wordform, pron) = line.rstrip().split("  ", 1)
            wordform = wordform.casefold()
            # Removes "numbering" on wordforms like `BASS(1)`.
            wordform = re.sub(r"\(\d+\)$", "", wordform)
            ptr = lexicon.entry[wordform]
            ptr.cmu_pron.append(pron)

    # ELP morphological analyses.
    (path, license) = ELP_MORPH
    with open(path, "r") as source:
        for drow in csv.DictReader(source):
            wordform = drow["Word"].casefold()
            ptr = lexicon.entry[wordform]
            morph_sp = drow["MorphSp"]
            # Skips lines without a morphological analysis.
            if morph_sp == "NULL":
                continue
            ptr.elp_morph_sp = morph_sp
            ptr.elp_nmorph = int(drow["NMorph"])

    # SUBTLEX-US.
    (path, license) = SUBTLEX_US
    with open(path, "r") as source:
        for drow in csv.DictReader(source, delimiter="\t"):
            wordform = drow["Word"].casefold()
            ptr = lexicon.entry[wordform]
            ptr.subtlex_us_freq = int(drow["FREQcount"])
            ptr.subtlex_us_cd = int(drow["CDcount"])

    # SUBTLEX-UK.
    (path, license) = SUBTLEX_UK
    with pandas.ExcelFile(path) as source:
        sheet = source.sheet_names[0]
        # Disables parsing "nan" as, well, `nan`.
        df = source.parse(sheet, na_values=[], keep_default_na=False)
        gen = zip(df.Spelling, df.FreqCount, df.CD_count)
        for (wordform, freq, cd) in gen:
            wordform = wordform.casefold()
            ptr = lexicon.entry[wordform]
            ptr.subtlex_uk_freq = freq
            ptr.subtlex_uk_cd = cd

    # UDLexicon from Apertium.
    (path, license) = UDLEXICONS_APERTIUM
    with open(path, "r") as source:
        for line in source:
            line = line.rstrip()
            pieces = line.split("\t")
            # Skips complex expressions.
            if pieces[0].startswith("0-"):
                continue
            wordform = pieces[2].casefold()
            ptr = lexicon.entry[wordform]
            entry = ptr.udlexicons_apertium.add()
            lemma = pieces[3].casefold()
            # Ignores unspecified lemmata.
            if lemma != "_":
                entry.lemma = lemma
            entry.pos = pieces[4]
            features = pieces[6]
            # Ignores unspecified feature bundles.
            if features != "_":
                entry.features = features

    # Unimorph.
    (path, license) = UNIMORPH
    with open(path, "r") as source:
        for line in source:
            (lemma, wordform, features) = line.rstrip().split("\t", 2)
            wordform = wordform.casefold()
            lemma = lemma.casefold()
            ptr = lexicon.entry[wordform]
            entry = ptr.unimorph.add()
            entry.lemma = lemma
            entry.features = features

    # Writes it out as a textproto.
    with open(args.output_textproto_path, "w") as sink:
        text_format.PrintMessage(lexicon, sink, as_utf8=True)
        logging.debug("Wrote %d entries", len(lexicon.entry))

    # Writes it out as a TSV file.
    # TODO(kbg): Not all fields yet supported.
    with open(args.output_tsv_path, "w") as sink:
        tsv_writer = csv.DictWriter(
            sink,
            delimiter="\t",
            fieldnames=FIELDNAMES,
            restval="NA",
            lineterminator="\n",
        )
        tsv_writer.writeheader()
        # Sorting for stability.
        for (wordform, entry) in sorted(lexicon.entry.items()):
            row = {"wordform": wordform}
            for field in FIELDNAMES[1:]:
                if field in REPEATED_STRING_FIELDNAMES:
                    # Deduplicate and join on '^'.
                    row[field] = "^".join(frozenset(getattr(entry, field)))
                elif entry.HasField(field):
                    row[field] = getattr(entry, field)
            tsv_writer.writerow(row)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output_textproto_path", default="citylex.textproto")
    parser.add_argument("--output_tsv_path", default="citylex.tsv")
    main(parser.parse_args())
