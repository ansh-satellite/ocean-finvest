#!/usr/bin/env bash

# Exit on error for safety, except when running the data update
set -o errexit

echo "==> Running backend data update script (Integrated_Momentum.py)..."
# We run the backend calculations to fetch the latest data and update Excel files.
# If this fails (e.g. temporary API issue), we print a warning but continue so the frontend starts.
python "MOMENTUM_DB_2 copy/Integrated_Momentum.py" || echo "WARNING: Backend update script failed or timed out. Starting frontend with existing cache..."

echo "==> Starting Streamlit frontend dashboard (app.py)..."
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
