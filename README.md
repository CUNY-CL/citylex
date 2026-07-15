# 🗽 CityLex: a free English lexical database

[![CircleCI](https://dl.circleci.com/status-badge/img/gh/CUNY-CL/citylex/tree/webapp.svg?style=svg)](https://dl.circleci.com/status-badge/redirect/gh/CUNY-CL/citylex/tree/webapp)

CityLex is an English lexical database intended to replace or enhance databases
like [CELEX](https://catalog.ldc.upenn.edu/LDC96L14). It combines data from up
to seven unique sources, including frequency norms, morphological analyses, and
pronunciations. Since these have varying license conditions (some are
proprietary, others restrict redistribution), we do not provide the database as
is. Rather the user must generate a personal copy by executing a Python script,
enabling whatever sources they wish to use.

## Building your own CityLex

To see the available data sources and options, execute
`python -m populate --help`.

To generate a lexicon database with all the free sources, execute:

    python -m populate --all-free

If you plan to use the web application, ensure that you populate the database
with at least the `--all-free` flag and optionally with the `--celex` and
`--celex-path` flags (see below for more info on including CELEX data).

## Deploying

Copy the following files to your static host:

    app/app.min.js
    app/citylex.db
    app/citylex.db.json
    app/favicon.ico
    app/index.html
    app/features.min.js
    app/script.min.js
    app/xsampa.min.js
    app/CELEX_features.pdf

Your host must support HTTP range requests.

## Testing locally

Run `make server` and then visit http://localhost:8000.

## Non-redistributable data sources

Not all CityLex data can be obtained automatically from online sources. If you
wish to enable CELEX features, follow the instructions below.

This proprietary resource must be obtained from the [Linguistic Data
Consortium](https://catalog.ldc.upenn.edu/LDC96L14).

To enable CELEX features, pass `--celex` to `python -m populate` and set the
`CELEX_PATH` environmental variable like so:

    CELEX_PATH="https://path.to.celex" python -m populate --all-free --celex

## For more information

[`citylex.bib`](citylex.bib) provides references for the data sources used.

## License

The CityLex codebase are distributed under the Apache 2.0 license. Please see
[`LICENSE.txt`](LICENSE.txt) for details.

All other data sources bear their original licenses chosen by their creators;
see `python -m populate --help` for more information.

## Author

CityLex was created by [Kyle Gorman](http://wellformedness.com) and Forest
Hallee with help from
[contributors](https://github.com/CUNY-CL/citylex/graphs/contributors).
