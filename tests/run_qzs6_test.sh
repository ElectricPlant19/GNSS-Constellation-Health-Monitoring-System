#!/bin/bash
# Example script to run QZS-6 analysis
# Replace YOUR_USERNAME and YOUR_PASSWORD with your Space-Track credentials

echo "Starting QZS-6 Parameter Sensitivity Analysis..."
echo "This will analyze the last 365 days of data"
echo ""

python test_qzs6_analysis.py \
    --username YOUR_USERNAME \
    --password YOUR_PASSWORD \
    --days 365

echo ""
echo "Analysis complete!"
