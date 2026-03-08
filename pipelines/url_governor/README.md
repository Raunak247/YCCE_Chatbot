# URL Governor Pipelines - Quick Start Guide

## Overview

Two completely independent URL ingestion pipelines:

- **Pipeline 1 (Missing URLs)**: Ingests all discovered URLs that were never ingested
- **Pipeline 2 (Incremental)**: Runs crawler, finds new URLs, ingests them

## Quick Start

### Pipeline 1: Missing URL Ingestion

**Purpose:** Process all 24,894 missing URLs discovered but not ingested

```bash
cd E:\YCCE_RAG
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py
```

**What it does:**
1. Loads discovered_urls.json (~29,894 URLs)
2. Loads ingested_urls.json (~5,000 URLs)
3. Computes missing = discovered - ingested
4. Ingests missing URLs in batches of 500
5. Updates ingested_urls.json
6. Logs results to: `pipelines/url_governor/missing_url_ingestion/logs/`

**Example output:**
```
[INFO] - Starting missing URL ingestion...
[INFO] - Loaded 29,894 discovered URLs
[INFO] - Loaded 5,000 ingested URLs
[INFO] - Found 24,894 missing URLs to ingest
[INFO] - Processing batch 1 of 50...
[INFO] - Batch 1: 500 URLs ingested, 0 failed
... (continues for 50 batches) ...
[INFO] - ✓ Total: 24,894 ingested, 0 failed
[INFO] - ✓ Pipeline completed successfully in 1234 seconds
```

---

### Pipeline 2: Incremental Recrawl + Ingestion

**Purpose:** Continuously crawl for new URLs and ingest them

```bash
cd E:\YCCE_RAG
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py
```

**What it does:**
1. Runs the crawler
2. Gets crawled URLs
3. Computes new = crawled - discovered
4. If new URLs found:
   - Appends to discovered_urls.json
   - Ingests new URLs
   - Updates ingested_urls.json
5. Logs results to: `pipelines/url_governor/incremental_recrawl_ingestion/logs/`

**Example output:**
```
[INFO] - Starting incremental recrawl and ingestion...
[INFO] - Running crawler...
[INFO] - Crawler completed: 30,014 URLs found
[INFO] - Loaded 29,894 discovered URLs
[INFO] - Found 120 new URLs
[INFO] - Updating discovered_urls.json...
[INFO] - Ingesting 120 new URLs...
[INFO] - ✓ Total: 120 ingested, 0 failed
[INFO] - ✓ Pipeline completed successfully in 456 seconds
```

---

## Key Differences

| | Pipeline 1 | Pipeline 2 |
|---|---|---|
| **Runs Crawler** | ❌ No | ✅ Yes |
| **Checks for Missing URLs** | ✅ Yes | ❌ No |
| **Modifies discovered_urls.json** | ❌ No | ✅ Yes |
| **Updates ingested_urls.json** | ✅ Yes | ✅ Yes |
| **Use Case** | Backfill missing | Continuous updates |
| **Frequency** | Once (or as needed) | Every 6 hours |
| **Triggers Other Pipeline** | ❌ No | ❌ No |

---

## Important Rules

✅ **ALLOWED:**
- Running both pipelines at different times
- Reading existing data files
- Calling existing ingestion.ingest_pipeline module
- Writing to own logs
- Atomic JSON updates

❌ **FORBIDDEN:**
- Modifying ingestion/ folder
- Modifying crawler/ folder
- Modifying vectordb/ folder
- Running both simultaneously (risk of race conditions)
- Manual FAISS modifications

---

## Folder Structure

```
pipelines/
├── __init__.py
└── url_governor/
    ├── __init__.py
    │
    ├── missing_url_ingestion/
    │   ├── __init__.py
    │   ├── run_missing_ingestion.py          ← ENTRY POINT 1
    │   ├── missing_checker.py
    │   ├── json_utils.py
    │   ├── url_normalizer.py
    │   ├── logger_config.py
    │   └── logs/
    │       └── missing_ingestion_YYYYMMDD.log
    │
    └── incremental_recrawl_ingestion/
        ├── __init__.py
        ├── run_incremental_ingestion.py      ← ENTRY POINT 2
        ├── recrawl_monitor.py
        ├── json_utils.py
        ├── url_normalizer.py
        ├── logger_config.py
        └── logs/
            └── incremental_ingestion_YYYYMMDD.log
```

---

## Execution Examples

### Example 1: Backfill All Missing URLs

```bash
# Terminal 1: Run missing URL ingestion
cd E:\YCCE_RAG
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py

# Monitor logs in another terminal
tail -f pipelines/url_governor/missing_url_ingestion/logs/missing_ingestion_20260302.log
```

**Expected result:**
- Before: 5,000 ingested
- After: 29,894 ingested (all discovered URLs now ingested)

---

### Example 2: Schedule Incremental Recrawl

**Windows Task Scheduler:**

```batch
REM File: C:\Scripts\run_incremental.bat
@echo off
cd E:\YCCE_RAG
conda activate base
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py >> logs/incremental_scheduled.log 2>&1
```

Then create task to run this script every 6 hours.

**Linux Cron:**

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/YCCE_RAG && python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py >> logs/incremental_cron.log 2>&1
```

---

### Example 3: Check System State

```python
import json

with open('data/discovered_urls.json') as f:
    discovered = json.load(f)

with open('data/ingested_urls.json') as f:
    ingested = json.load(f)

missing = len(set(discovered) - set(ingested))

print(f"Discovered: {len(discovered)}")
print(f"Ingested:   {len(ingested)}")
print(f"Missing:    {missing}")
print(f"Coverage:   {(len(ingested) / len(discovered) * 100):.1f}%")
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ YCCE RAG System                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  data/                                                           │
│  ├── discovered_urls.json    (all URLs ever found)             │
│  ├── ingested_urls.json      (URLs with vectors in FAISS)      │
│  └── faiss_index/            (vector database)                  │
│                                                                  │
│  crawler/                    (existing, DO NOT MODIFY)          │
│  ingestion/                  (existing, DO NOT MODIFY)          │
│  vectordb/                   (existing, DO NOT MODIFY)          │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│ pipelines/url_governor/                                         │
│                                                                  │
│  ┌─────────────────────────┐    ┌──────────────────────────┐   │
│  │ Pipeline 1              │    │ Pipeline 2               │   │
│  │ Missing URL Ingestion   │    │ Incremental Recrawl      │   │
│  │                         │    │                          │   │
│  │ ✓ Read discovered       │    │ ✓ Run crawler            │   │
│  │ ✓ Read ingested         │    │ ✓ Find new (crawled-d)  │   │
│  │ ✓ Compute missing       │    │ ✓ Update discovered     │   │
│  │ ✓ Ingest missing        │    │ ✓ Ingest new            │   │
│  │ ✓ Update ingested       │    │ ✓ Update ingested       │   │
│  │                         │    │                          │   │
│  │ Entry Point:            │    │ Entry Point:             │   │
│  │ run_missing_            │    │ run_incremental_         │   │
│  │ ingestion.py            │    │ ingestion.py             │   │
│  │                         │    │                          │   │
│  │ ❌ Never triggers P2    │    │ ❌ Never triggers P1     │   │
│  │ ❌ Never runs crawler   │    │ ❌ Never checks missing  │   │
│  └─────────────────────────┘    └──────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Pipeline 1 Is Very Slow

**Check:**
1. Network connection (URLs timing out)
2. GPU availability (embeddings slow)
3. Batch size (try smaller)
4. Logs: `tail -50 pipelines/url_governor/missing_url_ingestion/logs/`

### Pipeline 1 Crashes

**Recovery:**
```bash
# Check error in log
cat pipelines/url_governor/missing_url_ingestion/logs/missing_ingestion_YYYYMMDD.log

# Re-run (will safely recompute missing and retry)
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py
```

### Pipeline 2 Finds No New URLs

**This is normal!** It means the crawler has found all reachable URLs.

**To troubleshoot:**
```bash
# Check saturation percentage in logs
grep "Saturation" pipelines/url_governor/incremental_recrawl_ingestion/logs/incremental_ingestion_YYYYMMDD.log

# If < 1% new, crawler is saturated
# If 100%, all crawled URLs are already discovered
```

### JSON Corruption

**Recovery:**
```bash
# Restore from backup
cp data/discovered_urls.json.backup data/discovered_urls.json

# Check integrity
python -c "import json; json.load(open('data/discovered_urls.json')); print('OK')"
```

---

## Next Steps

1. ✅ **Verify Environment:**
   ```bash
   python -c "from crawler.bfs_crawler import run_crawler; print('Crawler: OK')"
   python -c "from ingestion.ingest_pipeline import run_ingestion; print('Ingestion: OK')"
   ```

2. ✅ **Run Pipeline 1:**
   ```bash
   python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py
   ```

3. ✅ **Schedule Pipeline 2:**
   - Windows: Use Task Scheduler
   - Linux: Use Cron
   - Run every 6 hours

4. ✅ **Monitor:**
   - Check logs daily
   - Track coverage percentage
   - Monitor ingestion success rates

---

## Additional Features

### Enable Detailed Logging (Debug Mode)

Modify the logger level in the pipeline files:

```python
# In logger_config.py, change:
logger.setLevel(logging.INFO)
# To:
logger.setLevel(logging.DEBUG)
```

### Custom Batch Size

```python
# In run_missing_ingestion.py, modify:
ingestion_result = self.ingest_missing_urls(missing_urls, batch_size=1000)
```

### Skip Backups (Faster)

```python
# In json_utils.py, change:
save_json_atomic(filepath, data, create_backup=True)
# To:
save_json_atomic(filepath, data, create_backup=False)
```

---

## Support

For detailed documentation, see: `url_governor.md`

---

**Status:** Production Ready ✓
**Version:** 1.0
**Last Updated:** March 2, 2026
