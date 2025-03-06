# setup/check_requirements.py

#!/usr/bin/env python3
# Script to check if the system meets all requirements for the audio transcriber

import sys
import os
import platform
import shutil
import subprocess
import importlib.util
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.11 or higher."""
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 11):
        print("❌ Python 3.11 or higher is required.")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def check_os():
    """Check if the OS is macOS."""
    if platform.system() != "Darwin":
        print("❌ This application is designed for macOS only.")
        print(f"   Current OS: {platform.system()}")
        return False
    print(f"✅ Operating System: macOS {platform.mac_ver()[0]}")
    return True

def check_disk_space():
    """Check if there's enough disk space (at least 2GB)."""
    # Check space in home directory
    home = Path.home()
    total, used, free = shutil.disk_usage(home)
    free_gb = free / (1024 ** 3)  # Convert to GB
    
    if free_gb < 2:
        print(f"❌ Not enough disk space. At least 2GB required.")
        print(f"   Available space: {free_gb:.2f}GB")
        return False
    print(f"✅ Disk space available: {free_gb:.2f}GB")
    return True

def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = [
        "faster_whisper",
        "sounddevice",
        "numpy",
        "pyperclip",
        "pynput",
        "rumps",
        "psutil"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nRun 'pip install -r requirements.txt' to install all dependencies.")
        return False
    
    print("✅ All required packages are installed.")
    return True

def check_audio_devices():
    """Check if audio input devices are available."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        
        if not input_devices:
            print("❌ No audio input devices found.")
            return False
        
        print(f"✅ Audio input devices available: {len(input_devices)}")
        return True
    except Exception as e:
        print(f"❌ Error checking audio devices: {e}")
        return False

def check_permissions():
    """Check if the application has the necessary permissions."""
    # This is a basic check - macOS permissions are complex and often require user interaction
    print("ℹ️ Permission check:")
    print("   - Microphone access will be requested when you first run the application")
    print("   - If transcription doesn't work, check System Preferences > Security & Privacy > Microphone")
    return True

def main():
    """Run all checks and report results."""
    print("\n=== AudioTranscriber System Requirements Check ===\n")
    
    checks = [
        check_python_version(),
        check_os(),
        check_disk_space(),
        check_dependencies(),
        check_audio_devices(),
        check_permissions()
    ]
    
    print("\n=== Summary ===")
    if all(checks):
        print("✅ Your system meets all requirements!")
        print("   You can run the application with: ./setup/launch_transcriber.sh")
    else:
        print("❌ Your system does not meet all requirements.")
        print("   Please address the issues above before running the application.")
    
    print("\n")

if __name__ == "__main__":
    main() 