#utils/logger.py

import os
import sys
import logging
import time
import glob
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Get the project root directory (parent of the directory containing this file)
project_root = Path(__file__).resolve().parent.parent

# Log directory and file paths
log_dir = project_root / 'logs'
log_file = log_dir / 'transcriber.log'
error_log_file = log_dir / 'transcriber.error.log'

# Log rotation settings
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Keep 3 backup files

def cleanup_logs(force_cleanup=False):
    """Clean up log files.
    
    Args:
        force_cleanup (bool): If True, delete all log files regardless of rotation settings.
                             Used during application shutdown.
    """
    try:
        # Ensure log directory exists
        log_dir.mkdir(exist_ok=True)
        
        if force_cleanup:
            # Delete all log files when force_cleanup is True
            log_pattern = str(log_dir / '*.log*')
            log_files = glob.glob(log_pattern)
            
            for file_path in log_files:
                try:
                    Path(file_path).unlink()
                    print(f"Deleted log file: {file_path}")
                except Exception as e:
                    print(f"Error deleting log file {file_path}: {e}")
        else:
            # During normal startup, we don't need to do anything special
            # as RotatingFileHandler will handle log rotation
            pass
                
    except Exception as e:
        print(f"Error cleaning up log files: {e}")

def setup_logging():
    """Configure logging for the application with log rotation."""
    # Ensure log directory exists
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Formatter for all logs
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler (all logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler for all logs
    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Rotating file handler for error logs only
    error_file_handler = RotatingFileHandler(
        str(error_log_file),
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    error_file_handler.setLevel(logging.ERROR)  # Only ERROR and CRITICAL
    error_file_handler.setFormatter(formatter)
    logger.addHandler(error_file_handler)
    
    logger.info("Logging initialized with rotation (max size: %d bytes, backups: %d)", 
               MAX_LOG_SIZE, BACKUP_COUNT)
    
    return logger 