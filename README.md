# 🗽 CityLex: a free English lexical database

[![PyPI
version](https://badge.fury.io/py/citylex.svg)](https://pypi.org/project/citylex)
[![Supported Python
versions](https://img.shields.io/pypi/pyversions/citylex.svg)](https://pypi.org/project/citylex)
[![CircleCI](https://dl.circleci.com/status-badge/img/gh/CUNY-CL/citylex/tree/master.svg?style=svg)](https://dl.circleci.com/status-badge/redirect/gh/CUNY-CL/citylex/tree/master)

CityLex is an English lexical database intended to replace or enhance databases
like [CELEX](https://catalog.ldc.upenn.edu/LDC96L14). It combines data from up
to seven unique sources, including frequency norms, morphological analyses, and
pronunciations. Since these have varying license conditions (some are
proprietary, others restrict redistribution), we do not provide the database as
is. Rather the user must generate a personal copy by executing a Python script,
enabling whatever sources they wish to use.

## Building your own CityLex

To install CityLex execute

```bash
pip install citylex
```

To see the available data sources and options, execute `python -m citylex.populate --help`.

To generate the lexicon, execute `python -m citylex.populate` with at least one source enabled
using command-line flags. As most of the data is downloaded from outline
sources, an internet connection is normally required. The process takes roughly
four minutes with all sources enabled; much of the time is spent downloading
large files.

To generate a lexicon with all the sources that don't require manual downloads,
execute

```bash
python -m citylex.populate --all-free
```

If you plan to use the web application, ensure that you populate the database with at least the `--all-free` flag and optionally with the `--celex` and `--celex-path` flags (see below for more info on including CELEX data).

## Launching the web application

Once the database (`citylex.db`) is populated, you can launch the Flask web application. First, set the `FLASK_APP` environment variable:

```bash
export FLASK_APP=citylex.flask_app.app
```

Then, run the Flask application:

```bash
flask run
```

This will start the web server locally, making the CityLex application accessible. The application allows you to access the data in tsv and json formats.

## Non-redistributable data sources

Not all CityLex data can be obtained automatically from online sources. If you
wish to enable CELEX features, follow the instructions below.

This proprietary resource must be obtained from the [Linguistic Data
Consortium](https://catalog.ldc.upenn.edu/LDC96L14) as `LDC96L14.tgz`. The file
should be decompressed using

```bash
tar -xzf LDC96L14.tgz
```

This will produce a directory named `celex2`. To enable CELEX2 features, use
`--celex` and pass the local path of this directory as an argument to
`--celex_path`.

Optionally, to password protect access to CELEX data within the web application, set the `CELEX_PASSWORD` environment variable:

```bash
export CELEX_PASSWORD="your_desired_password"
```

## For more information

- [`citylex.bib`](citylex.bib) for references to the data sources used

## License

The CityLex codebase are distributed under the Apache 2.0 license. Please see
[`LICENSE.txt`](LICENSE.txt) for details.

All other data sources bear their original licenses chosen by their creators;
see `citylex --help` for more information.

## Author

CityLex was created by [Kyle Gorman](http://wellformedness.com) with help from
[contributors](https://github.com/CUNY-CL/citylex/graphs/contributors).
