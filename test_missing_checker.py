#!/usr/bin/env python
"""Quick test of missing URL checker"""

from pipelines.url_governor.missing_url_ingestion.missing_checker import MissingUrlChecker

m = MissingUrlChecker('data/discovered_urls.json', 'data/ingested_urls.json')
result = m.compute_missing()
print(f"Discovered: {result['discovered_count']}")
print(f"Ingested: {result['ingested_count']}")
print(f"Missing: {result['missing_count']}")
print(f"Coverage: {result['coverage']:.1f}%")
missing_urls = result['missing']
if len(missing_urls) > 0:
    print(f'Sample URLs: {list(missing_urls)[:3]}')
else:
    print('No missing URLs found!')
