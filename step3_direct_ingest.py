#!/usr/bin/env python
"""
Direct Ingestion Script - Step 3 Only
Ingest from discovered_urls.json directly into FAISS
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '.')

from ingestion.ingest_pipeline import ingest_items
from vectordb.vectordb_manager import VectorDBManager

print("=" * 60)
print("[STEP 3] Direct Ingestion from discovered_urls.json")
print("=" * 60)

# Load URLs
discovered_file = Path("data/discovered_urls.json")
if not discovered_file.exists():
    print(f"❌ Error: {discovered_file} not found")
    sys.exit(1)

print(f"\n[LOAD] Reading {discovered_file}...")
with open(discovered_file, 'r', encoding='utf-8') as f:
    urls = json.load(f)

if not isinstance(urls, list):
    urls = [urls]

total_urls = len(urls)
print(f"✅ Loaded {total_urls} URLs from discovered_urls.json")

# Initialize FAISS
print("\n[FAISS] Initializing VectorDB Manager...")
try:
    vdb = VectorDBManager()
    print(f"✅ VectorDB ready")
except Exception as e:
    print(f"❌ Failed to initialize VectorDB: {e}")
    sys.exit(1)

# Ingest
print(f"\n[INGEST] Starting ingestion of {total_urls} URLs...")
try:
    results = ingest_items(urls)
    print(f"\n✅ INGESTION COMPLETED")
    print(f"   Success: {results.get('success', 0)}")
    print(f"   Failed: {results.get('failed', 0)}")
    print(f"   Total chunks: {results.get('total_chunks', 'N/A')}")
except Exception as e:
    print(f"❌ Ingestion error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify FAISS index
print("\n[VERIFY] Checking FAISS index...")
try:
    vdb = VectorDBManager()
    if vdb.db:
        print(f"✅ FAISS Index verified: {vdb.db.index.ntotal} vectors")
        print(f"\n✅ SUCCESS: FAISS index created and ready!")
    else:
        print(f"❌ FAISS index is empty")
except Exception as e:
    print(f"⚠️  Warning: {e}")

print("\n" + "=" * 60)
