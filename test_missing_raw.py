#!/usr/bin/env python
"""Quick test of raw-level missing URL detection"""

from pipelines.url_governor.missing_url_ingestion.missing_checker import MissingUrlChecker

m = MissingUrlChecker('data/discovered_urls.json', 'data/ingested_urls.json')
result = m.compute_missing()

print(f'Missing (RAW level): {result["missing_count"]} URLs')
print(f'Discovered: {result["discovered_count"]}, Ingested: {result["ingested_count"]}')
print(f'Coverage: {result["coverage"]:.1f}%')

# Show samples
if result['missing_count'] > 0:
    samples = list(result['missing'])[:5]
    print(f'\nSample missing URLs:')
    for url in samples:
        print(f'  - {url[:80]}')
