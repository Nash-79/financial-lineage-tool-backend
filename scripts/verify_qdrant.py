"""
Qdrant verification wrapper.
(Wrapper for src.utils.diagnostics.verify_qdrant_connection)
"""

import sys
import os
from dotenv import load_dotenv

# Ensure src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.diagnostics import verify_qdrant_connection

load_dotenv()

if __name__ == "__main__":
    success = verify_qdrant_connection()
    exit(0 if success else 1)
