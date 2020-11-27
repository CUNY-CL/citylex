#!/usr/bin/env python
"""Frequencies correlations for CityLex."""

# NB: This is not normally distributed with the CityLex package.


import argparse
import csv
import itertools

from typing import Dict, List

import citylex  # type: ignore
import scipy.stats  # type: ignore


FREQUENCIES = ["celex_freq", "subtlex_uk_freq", "subtlex_us_freq"]


def main(args: argparse.Namespace) -> None:
    # Reads in data.
    lexicon = citylex.read_textproto(args.textproto_path)
    elp_latency: Dict[str, float] = {}
    with open(args.latencies_path, "r") as source:
        for (word, latency) in csv.reader(source, delimiter="\t"):
            elp_latency[word.casefold()] = float(latency)
    # Correlations between the frequency bands.
    print("Frequency-frequency correlations")
    for (f1, f2) in itertools.combinations(FREQUENCIES, 2):
        f1_list: List[int] = []
        f2_list: List[int] = []
        for entry in lexicon.entry.values():
            if entry.HasField(f1) and entry.HasField(f2):
                f1_list.append(getattr(entry, f1))
                f2_list.append(getattr(entry, f2))
        r = scipy.stats.pearsonr(f1_list, f2_list)[0]
        rho = scipy.stats.spearmanr(f1_list, f2_list)[0]
        print(f"{f1}/{f2}:")
        print(f"\toverlap:\t{len(f1_list):,}")
        print(f"\tr:\t\t{r: .3f}")
        print(f"\tρ:\t\t{rho: .3f}")
        print()
    # Correlations between frequency and the ELP data.
    print("Frequency-ELP correlations")
    for f1 in FREQUENCIES:
        f1_list = []
        f2_list = []
        for (word, entry) in lexicon.entry.items():
            if entry.HasField(f1):
                try:
                    f2_list.append(elp_latency[word])
                    f1_list.append(getattr(entry, f1))
                except KeyError:
                    continue
        r = scipy.stats.pearsonr(f1_list, f2_list)[0]
        rho = scipy.stats.spearmanr(f1_list, f2_list)[0]
        print(f"{f1}/ELP RT:")
        print(f"\toverlap:\t{len(f1_list):,}")
        print(f"\tr:\t\t{r: .3f}")
        print(f"\tρ:\t\t{rho: .3f}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--textproto-path",
        default="../citylex.textproto",
        help="textproto path (default: %(default)s)",
    )
    parser.add_argument(
        "--latencies-path",
        default="elp-item.tsv",
        help="ELP latencies path (default: %(default)s)",
    )
    main(parser.parse_args())
