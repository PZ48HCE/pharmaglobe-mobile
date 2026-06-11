#!/bin/bash
# Move to the directory containing this script
cd "$(dirname "$0")"

echo "==============================================="
echo "   Launching PharmaGlobe Mobile App Launcher   "
echo "==============================================="
echo "Initializing Python virtual environment..."

# Run python script using the local virtual environment
.venv/bin/python main.py

echo ""
echo "App closed. Press Enter to close this window."
read -r
