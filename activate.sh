#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Set PYTHONPATH to include current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "Thalex Quoter environment activated!"
echo "Virtual environment: $(which python)"
echo "Python path: $PYTHONPATH"
echo ""
echo "To run the main quoter: python simple_quoter_queue.py"
echo "To deactivate: deactivate" 