#!/usr/bin/env python3
# setup/test_log_rotation.py
# Script to test log rotation functionality

import sys
import os
import time
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import our logging setup
from utils.logger import setup_logging, cleanup_logs

def generate_log_entries(count=1000, size_per_entry=1000):
    """Generate a large number of log entries to test rotation."""
    logger = logging.getLogger()
    
    print(f"Generating {count} log entries (approximately {count * size_per_entry / 1024:.2f} KB)...")
    
    # Generate log entries with increasing size
    for i in range(count):
        # Create a log message with padding to reach the desired size
        padding = "X" * (size_per_entry - 50)  # Subtract some bytes for the log format
        logger.info(f"Test log entry #{i}: {padding}")
        
        # Print progress every 100 entries
        if i % 100 == 0:
            print(f"Generated {i} entries...")
            
        # Small delay to make it more realistic
        if i % 10 == 0:
            time.sleep(0.01)
    
    print("Log generation complete.")

def check_log_files():
    """Check and display information about log files."""
    log_dir = project_root / 'logs'
    
    if not log_dir.exists():
        print(f"Log directory does not exist: {log_dir}")
        return
    
    print("\nLog files found:")
    total_size = 0
    
    for file_path in log_dir.glob('*.log*'):
        size = file_path.stat().st_size
        total_size += size
        print(f"  - {file_path.name}: {size / 1024:.2f} KB")
    
    print(f"\nTotal log size: {total_size / 1024:.2f} KB")

def main():
    """Run the log rotation test."""
    print("=== Log Rotation Test ===\n")
    
    # Initialize logging with rotation
    setup_logging()
    
    # Check initial log files
    print("\nInitial log files:")
    check_log_files()
    
    # Generate logs to trigger rotation
    generate_log_entries()
    
    # Check log files after generation
    print("\nLog files after generation:")
    check_log_files()
    
    # Test cleanup
    print("\nTesting log cleanup...")
    cleanup_logs(force_cleanup=True)
    
    # Check log files after cleanup
    print("\nLog files after cleanup:")
    check_log_files()
    
    print("\nTest complete.")

if __name__ == "__main__":
    main() 