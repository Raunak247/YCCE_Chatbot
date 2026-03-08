"""
URL Governor Pipelines

Two completely independent pipelines for URL management:

Pipeline 1: Missing URL Ingestion
  - Ingests URLs that were discovered but not yet ingested
  - Run: python missing_url_ingestion/run_missing_ingestion.py

Pipeline 2: Incremental Recrawl + New URL Ingestion
  - Runs crawler, finds new URLs, ingests them
  - Run: python incremental_recrawl_ingestion/run_incremental_ingestion.py

Each pipeline:
  ✓ Runs completely independently
  ✓ Does NOT trigger the other
  ✓ Has its own entry point
  ✓ Has its own logging
  ✓ Does NOT modify existing code
"""
