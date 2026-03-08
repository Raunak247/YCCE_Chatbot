import json

d = json.load(open('data/discovered_urls.json'))
i = json.load(open('data/ingested_urls.json'))
print(f'Discovered URLs: {len(d)}')
print(f'Ingested URLs: {len(i)}')
print(f'Missing: {len(d)-len(i)}')
