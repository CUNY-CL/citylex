#!/bin/bash

set -eou pipefail

make install
python -m citylex.populate --all-free --celex
