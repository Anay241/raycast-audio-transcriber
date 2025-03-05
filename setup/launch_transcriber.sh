#setup/launch_transcriber.sh

#!/bin/bash

# Enable strict mode to exit on errors
set -e

# Audio Transcriber Launch Script
# This script launches the audio transcriber application

# Simple error handling function
handle_error() {
    echo "ERROR: $1"
    exit 1
}

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to the project root directory
cd "$PROJECT_ROOT" || handle_error "Failed to change to project directory"

# Set Python executable path
PYTHON_EXEC="python3"

# Check if Python is installed
if ! command -v $PYTHON_EXEC &> /dev/null; then
    handle_error "Python 3 is not installed or not in PATH"
fi

# Check Python version (warn but don't fail for older versions)
PYTHON_VERSION=$($PYTHON_EXEC --version | cut -d' ' -f2)
if [[ $(echo "$PYTHON_VERSION" | cut -d. -f1) -lt 3 ]]; then
    echo "Warning: Python 3.11+ is recommended. You're using $PYTHON_VERSION"
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate || handle_error "Failed to activate virtual environment"
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
            handle_error "Invalid command line argument"
            ;;
    esac
done

# Build command arguments
CMD_ARGS=""
if [ "$CHANGE_MODEL" = true ]; then
    CMD_ARGS="--change-model"
fi

# Launch the application using the Python launch manager
echo "Launching Audio Transcriber..."
"$PYTHON_EXEC" -m setup.launch_manager $CMD_ARGS

# Check if launch was successful
if [ $? -eq 0 ]; then
    echo "Audio Transcriber launched successfully!"
else
    handle_error "Failed to launch Audio Transcriber"
fi 