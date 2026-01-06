"""
Entry point for Animation Library v2

Run this script to start the application:
    python run.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run main
from animation_library.main import main

if __name__ == "__main__":
    main()
