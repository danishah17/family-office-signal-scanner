#!/usr/bin/env python3
"""Smoke test: Chroma index exists, non-empty, row count meets Falcon floor (200+)."""
import os
import sys

# Repo root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)


def main() -> int:
    from rag_query import FamilyOfficeRAG

    rag = FamilyOfficeRAG()
    if not rag.is_database_ready():
        print("FAIL:", rag.init_status_message())
        return 1
    n = rag.database_count()
    if n < 200:
        print(f"FAIL: expected at least 200 indexed records, got {n}")
        return 1
    print(f"OK: RAG index ready with {n} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
