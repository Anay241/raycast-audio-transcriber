#!/bin/bash

# Audio Transcriber Launch Script
# This script launches the audio transcriber application

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to the project root directory
cd "$PROJECT_ROOT" || { echo "Failed to change to project directory"; exit 1; }

# Set Python executable path
PYTHON_EXEC="python3"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }
    # Use the Python from the virtual environment
    PYTHON_EXEC="$PROJECT_ROOT/venv/bin/python"
fi

# Parse command line arguments
CHANGE_MODEL=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --change-model)
            CHANGE_MODEL=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--change-model]"
            exit 1
            ;;
    esac
done

# Launch the application using the Python launch manager
echo "Launching Audio Transcriber..."
if [ "$CHANGE_MODEL" = true ]; then
    "$PYTHON_EXEC" -m setup.launch_manager --change-model
else
    "$PYTHON_EXEC" -m setup.launch_manager
fi

# Check if launch was successful
if [ $? -eq 0 ]; then
    echo "Audio Transcriber launched successfully!"
else
    echo "Failed to launch Audio Transcriber"
    exit 1
fi 