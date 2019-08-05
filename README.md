CityLex: a multisource lexical database for English
===================================================

This directory contains code and data used to (re)generate CityLex. There are
two user endpoints:

* `build.py` constructs the textproto variant of the lexicon, and
* `tsv.py` converts a textproto lexicon to a TSV file.

See `data/README.md` for the required data sources.
See `citylex.proto` for the data structure and references to the internal data.
