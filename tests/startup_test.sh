#!/bin/bash

set -eou pipefail

# Populates the DB.
citylex --all-free 

# Starts the webapp in the background, catching its ID.
gunicorn flask_app.app:app & 
PID=$! 

# Wait 10 seconds and then kill it gracefully.
sleep 10 && kill $PID