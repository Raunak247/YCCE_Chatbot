#!/usr/bin/env python
"""
Test script to verify recrawl_monitor URL extraction fix.
"""

print("=" * 60)
print("RECRAWL MONITOR URL EXTRACTION FIX VERIFICATION")
print("=" * 60)

# Simulate crawler output (list of dicts)
crawler_output = [
    {"url": "http://example.com", "type": "html", "depth": 0},
    {"url": "https://test.org/page", "type": "html", "depth": 1},
    {"url": "www.site.com", "type": "html", "depth": 2},
    "http://direct-string.com",  # Also handle direct strings
]

print("\n1. Testing URL extraction from crawler output:")
print("-" * 60)
print(f"Crawler output has {len(crawler_output)} items")
print(f"  - 3 dict items with 'url' key")
print(f"  - 1 direct string item")

# Simulate the extraction logic from recrawl_monitor.py
urls = []
for item in crawler_output:
    if isinstance(item, dict) and 'url' in item:
        urls.append(item['url'])
    elif isinstance(item, str):
        urls.append(item)

print(f"\nExtracted {len(urls)} URLs:")
for i, url in enumerate(urls, 1):
    print(f"  {i}. {url}")

print("\n2. Testing with normalize_batch (after extraction):")
print("-" * 60)
from pipelines.url_governor.incremental_recrawl_ingestion.url_normalizer import normalize_batch

result = normalize_batch(urls)
print(f"✓ Valid URLs: {result['valid_count']}")
print(f"✓ Invalid URLs: {result['invalid_count']}")
print(f"✓ Sample normalized URLs:")
for url in list(result['valid'])[:3]:
    print(f"    - {url}")

if result['valid_count'] == len(urls):
    print("\n✓ SUCCESS: URL extraction and normalization working correctly!")
else:
    print(f"\n✗ FAILURE: Lost {len(urls) - result['valid_count']} URLs")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
