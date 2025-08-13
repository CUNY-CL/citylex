#!/bin/bash

set -eou pipefail

pip install -r requirements.txt

# Populates the DB.
python -m citylex.populate --all-free 

# Starts the webapp in the background, catching its ID.
gunicorn flask_app.app:app & 
PID=$! 

# Wait 10 seconds and then kill it gracefully.
sleep 10 && kill $PID