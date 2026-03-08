#!/usr/bin/env python
"""
Direct Ingestion Script - Ingest All Missing URLs One-by-One
Ingests from discovered_urls.json and appends successfully ingested URLs
to ingested_urls.json one by one in real-time
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '.')

from ingestion.ingest_pipeline import ingest_items
from vectordb.vectordb_manager import VectorDBManager

print("=" * 70)
print("[STEP 1] LOAD DISCOVERED & INGESTED URLs")
print("=" * 70)

# Load discovered URLs
discovered_file = Path("data/discovered_urls.json")
if not discovered_file.exists():
    print(f"❌ Error: {discovered_file} not found")
    sys.exit(1)

with open(discovered_file, 'r', encoding='utf-8') as f:
    discovered_data = json.load(f)

# Extract URLs from discovered (handle both dict and string formats)
discovered_urls = set()
for item in discovered_data:
    if isinstance(item, dict) and 'url' in item:
        discovered_urls.add(item['url'])
    elif isinstance(item, str):
        discovered_urls.add(item)

print(f"✅ Loaded {len(discovered_urls):,} discovered URLs")

# Load ingested URLs
ingested_file = Path("data/ingested_urls.json")
if ingested_file.exists():
    with open(ingested_file, 'r', encoding='utf-8') as f:
        ingested_urls = set(json.load(f))
else:
    ingested_urls = set()

print(f"✅ Loaded {len(ingested_urls):,} already ingested URLs")

# Compute missing URLs
missing_urls = discovered_urls - ingested_urls
print(f"\n📋 Missing URLs to ingest: {len(missing_urls):,}")

if not missing_urls:
    print("✅ All URLs already ingested!")
    sys.exit(0)

print("\n" + "=" * 70)
print("[STEP 2] INGEST MISSING URLs ONE-BY-ONE")
print("=" * 70)

# Initialize new ingested list (will append to this)
newly_ingested = []

# Format missing URLs as items
items = []
for url in missing_urls:
    # Detect file type
    url_lower = url.lower()
    if '.pdf' in url_lower:
        file_type = 'pdf'
    elif '.xlsx' in url_lower or '.xls' in url_lower:
        file_type = 'xlsx'
    elif '.csv' in url_lower:
        file_type = 'csv'
    elif '.txt' in url_lower:
        file_type = 'txt'
    else:
        file_type = 'html'
    
    items.append({
        "url": url,
        "type": file_type
    })

print(f"\n🚀 Starting ingestion of {len(items):,} URLs...")
print("   (URLs will be added to ingested_urls.json as they complete)\n")

# Run ingestion with the items
# This will internally call save_ingested_urls() periodically
try:
    result = ingest_items(items)
    
    print(f"\n✅ INGESTION COMPLETE")
    print(f"   Newly ingested: {result.get('newly_ingested', 0):,}")
    print(f"   Skipped: {result.get('skipped', 0):,}")
    print(f"   Failed: {result.get('failed', 0):,}")
    
except Exception as e:
    print(f"\n❌ Error during ingestion: {e}")
    sys.exit(1)

# Final verification
print("\n" + "=" * 70)
print("[STEP 3] VERIFICATION")
print("=" * 70)

with open(ingested_file, 'r', encoding='utf-8') as f:
    final_ingested = json.load(f)

with open(discovered_file, 'r', encoding='utf-8') as f:
    final_discovered_data = json.load(f)

final_discovered = set()
for item in final_discovered_data:
    if isinstance(item, dict) and 'url' in item:
        final_discovered.add(item['url'])
    elif isinstance(item, str):
        final_discovered.add(item)

coverage = len(final_ingested) / len(final_discovered) * 100

print(f"\nFinal Status:")
print(f"  Discovered URLs: {len(final_discovered):,}")
print(f"  Ingested URLs:   {len(final_ingested):,}")
print(f"  Coverage:        {coverage:.2f}%")

if len(final_ingested) == len(final_discovered):
    print(f"\n🎉 SUCCESS! All {len(final_ingested):,} URLs ingested into FAISS!")
else:
    missing = len(final_discovered) - len(final_ingested)
    print(f"\n⚠️  Still {missing:,} URLs missing")

print("\n✅ Complete!")
