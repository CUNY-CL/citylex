#!/usr/bin/env python
"""Converts textproto CityLex lexicon to a TSV file."""

import argparse
import csv
import logging
import sys

from google.protobuf import text_format

import pandas

import citylex_pb2


# TODO(kbg): this just supports frequencies.
FIELDNAMES = [
    "wordform",
    "celex_freq",
    "subtlex_uk_freq",
    "subtlex_uk_cd",
    "subtlex_us_freq",
    "subtlex_us_cd",
]


def main(args: argparse.Namespace) -> None:
    # Reads lexicon.
    lexicon = citylex_pb2.Lexicon()
    with open(args.input_textproto_path, "r") as source:
        text_format.ParseLines(source, lexicon)
    logging.debug("Read %d entries", len(lexicon.entry))

    # Writes TSV.
    with open(args.output_tsv_path, "w") as sink:
        tsv_writer = csv.DictWriter(
            sink,
            delimiter="\t",
            fieldnames=["wordform"] + FIELDNAMES,
            restval="NA",
            lineterminator="\n",
        )
        tsv_writer.writeheader()
        for (wordform, entry) in lexicon.entry.items():
            row = {"wordform": wordform}
            for field in FIELDNAMES[1:]:
                if entry.HasField(field):
                    row[field] = getattr(entry, field)
            tsv_writer.writerow(row)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s: %(message)s", level="INFO")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_textproto_path")
    parser.add_argument("output_tsv_path")
    main(parser.parse_args())
