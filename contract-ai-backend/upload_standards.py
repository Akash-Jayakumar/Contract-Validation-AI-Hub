#!/usr/bin/env python3
"""
Script to upload standard clauses from JSON to ChromaDB
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from services.embeddings import upload_standard_clauses

def main():
    try:
        json_path = "./app/standards/msa_playbook.json"
        count = upload_standard_clauses(json_path=json_path, collection_name="standard_clauses")
        print(f"Successfully uploaded {count} standard clauses to ChromaDB.")
    except Exception as e:
        print(f"Error uploading standard clauses: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
