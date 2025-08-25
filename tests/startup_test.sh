#!/bin/bash

set -eou pipefail

pip install -r requirements.txt

# Populates the DB.
python -m citylex.populate --all-free 

# Starts the webapp in the background, catching its ID.
gunicorn --pid pid.file webapp.app:app & 

# Wait 10 seconds and then kill it gracefully.
sleep 10 && kill $(cat pid.file) && sleep 10 && echo "Success!"
