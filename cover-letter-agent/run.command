#!/bin/bash
# Starts the Job Application Assistant on a Mac and opens http://localhost:8501 once it's ready.
# Double-click it in Finder (it opens in Terminal). Close the Terminal window or press Ctrl+C to stop it.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/streamlit ]; then
    echo 'Not installed yet. See README.md, "Install on a Mac".'
    read -r -n 1 -p "Press any key to close."
    exit 1
fi
# Open the browser after the server has had a few seconds to start.
(sleep 5; open "http://localhost:8501") &
exec .venv/bin/streamlit run app.py
