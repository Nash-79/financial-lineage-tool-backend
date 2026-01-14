"""
Corpus ingestion wrapper.
(Wrapper for src.ingestion.corpus)
"""

import sys
import os
import argparse
from dotenv import load_dotenv

# Ensure src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.corpus import ingest_corpus_from_dir

load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest corpus into Knowledge Graph.")
    parser.add_argument(
        "--dir",
        default="data/raw",
        help="Target directory to ingest (default: data/raw)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.dir):
        print(f"[!] Directory not found: {args.dir}")
        sys.exit(1)

    ingest_corpus_from_dir(args.dir)
