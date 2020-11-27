#!/usr/bin/env python
"""Summary statistics for CityLex."""

# NB: This is not normally distributed with the CityLex package.


import argparse

import citylex  # type: ignore


OPTIONAL_FIELDS = [
    "celex_freq",
    "elp_morph_sp",
    "elp_nmorph",
    "subtlex_uk_freq",
    "subtlex_uk_cd",
    "subtlex_us_freq",
    "subtlex_us_cd",
]
REPEATED_FIELDS = [
    "celex_morph",
    "udlexicons_morph",
    "unimorph_morph",
    "wikipron_uk_pron",
    "wikipron_us_pron",
    "celex_pron",
    "cmudict_pron",
]
FIELDS = OPTIONAL_FIELDS + REPEATED_FIELDS


def main(args: argparse.Namespace) -> None:
    # Reads in lexicon textproto.
    lexicon = citylex.read_textproto(args.textproto_path)
    # Collects counts.
    field_counts = dict.fromkeys(FIELDS, 0)
    unique_counts = dict.fromkeys(FIELDS, 0)
    for (wordform, entry) in lexicon.entry.items():
        for field in OPTIONAL_FIELDS:
            if entry.HasField(field):
                field_counts[field] += 1
                unique_counts[field] += 1
        for field in REPEATED_FIELDS:
            elem = getattr(entry, field, [])
            if elem:
                field_counts[field] += len(elem)
                unique_counts[field] += 1
    # Prints counts.
    print("Counts:\n")
    for (field, count) in sorted(field_counts.items()):
        unique_count = unique_counts[field]
        if count == unique_count:
            print(f"\t{field}:\t{count:,}")
        else:
            print(f"\t{field}:\t{count:,}\t({unique_count:,})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--textproto_path",
        default="../citylex.textproto",
        help="textproto path (default: %(default)s)",
    )
    main(parser.parse_args())
