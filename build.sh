#!/bin/bash

set -eou pipefail

pip install -r requirements.txt
python -m citylex.populate --all-free --celex
