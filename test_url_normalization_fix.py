#!/usr/bin/env python
"""
Test script to verify URL normalization fixes.
Tests both missing_url_ingestion and incremental_recrawl_ingestion modules.
"""

print("=" * 60)
print("URL NORMALIZATION FIX VERIFICATION")
print("=" * 60)

# Test 1: Missing URL Ingestion Normalizer
print("\n1. Testing missing_url_ingestion.url_normalizer:")
print("-" * 60)
from pipelines.url_governor.missing_url_ingestion.url_normalizer import normalize, normalize_batch

test_urls = [
    'www.example.com',
    'https://example.com/path',
    'http://example.com/',
    'example.org',
    '',
    None,
    'test.io?query=value',
]

print(f"Testing {len([u for u in test_urls if u])} URLs...")
result = normalize_batch(test_urls)
print(f"✓ Valid URLs: {result['valid_count']}")
print(f"✓ Invalid URLs: {result['invalid_count']}")
print(f"✓ Preservation Rate: {(result['valid_count'] / len([u for u in test_urls if u]) * 100):.1f}%")

# Test 2: Incremental Recrawl Normalizer
print("\n2. Testing incremental_recrawl_ingestion.url_normalizer:")
print("-" * 60)
from pipelines.url_governor.incremental_recrawl_ingestion.url_normalizer import (
    normalize as normalize_recrawl, 
    normalize_batch as normalize_batch_recrawl
)

result2 = normalize_batch_recrawl(test_urls)
print(f"✓ Valid URLs: {result2['valid_count']}")
print(f"✓ Invalid URLs: {result2['invalid_count']}")
print(f"✓ Preservation Rate: {(result2['valid_count'] / len([u for u in test_urls if u]) * 100):.1f}%")

# Test 3: URL without scheme handling
print("\n3. Testing URLs without scheme (CRITICAL FIX):")
print("-" * 60)
no_scheme_urls = [
    'www.example.com',
    'google.com',
    'github.com/path/to/page',
    'localhost:8080',
]
result3 = normalize_batch_recrawl(no_scheme_urls)
print(f"Input URLs: {len(no_scheme_urls)}")
print(f"Normalized URLs: {result3['valid_count']}")
if result3['valid_count'] == len(no_scheme_urls):
    print("✓ SUCCESS: All URLs without scheme were normalized!")
else:
    print(f"✗ FAILURE: {len(no_scheme_urls) - result3['valid_count']} URLs were lost")

# Test 4: Large batch simulation (27890 URLs)
print("\n4. Simulating large URL batch (27890 URLs):")
print("-" * 60)
import random
large_batch = []
for i in range(27890):
    if random.random() < 0.3:  # 30% without scheme
        large_batch.append(f'example-{i}.com')
    elif random.random() < 0.1:  # 10% with special chars
        large_batch.append(f'https://site-{i}.org/path?q=value#{i}')
    else:  # 60% normal URLs
        large_batch.append(f'http://example-{i}.com/{i}')

result4 = normalize_batch_recrawl(large_batch)
preservation_rate = (result4['valid_count'] / len(large_batch) * 100)
print(f"Input URLs: {len(large_batch)}")
print(f"Valid URLs: {result4['valid_count']}")
print(f"Invalid URLs: {result4['invalid_count']}")
print(f"Preservation Rate: {preservation_rate:.2f}%")

if preservation_rate >= 95:
    print("✓ SUCCESS: Preservation rate >= 95%!")
else:
    print(f"✗ WARNING: Preservation rate is {preservation_rate:.2f}% (target: >= 95%)")

# Test 5: Logger encoding fix
print("\n5. Testing logger configuration (UTF-8 encoding):")
print("-" * 60)
from pipelines.url_governor.missing_url_ingestion.logger_config import setup_logger
from pipelines.url_governor.incremental_recrawl_ingestion.logger_config import setup_logger as setup_logger_recrawl

logger1 = setup_logger("test_missing")
logger2 = setup_logger_recrawl("test_recrawl")

# Check if file handler has encoding
for handler in logger1.handlers:
    if hasattr(handler, 'encoding'):
        if handler.encoding == 'utf-8':
            print(f"✓ Logger 1: {handler.__class__.__name__} has UTF-8 encoding")
        else:
            print(f"✗ Logger 1: {handler.__class__.__name__} has {handler.encoding} encoding")

for handler in logger2.handlers:
    if hasattr(handler, 'encoding'):
        if handler.encoding == 'utf-8':
            print(f"✓ Logger 2: {handler.__class__.__name__} has UTF-8 encoding")
        else:
            print(f"✗ Logger 2: {handler.__class__.__name__} has {handler.encoding} encoding")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
