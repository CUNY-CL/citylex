#!/bin/bash

set -eou pipefail

make install
make js
python -m citylex.populate --all-free --celex
