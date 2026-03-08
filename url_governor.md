# 🔗 URL Governor System - Complete Documentation

**Status:** Production Architecture
**Last Updated:** March 2, 2026
**Purpose:** Two completely independent URL ingestion pipelines with strict separation of concerns

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Pipeline 1: Missing URL Ingestion](#pipeline-1--missing-url-ingestion)
4. [Pipeline 2: Incremental Recrawl + New URL Ingestion](#pipeline-2--incremental-recrawl--new-url-ingestion)
5. [Common Requirements](#common-requirements)
6. [Execution Guide](#execution-guide)
7. [Safety & Constraints](#safety--constraints)
8. [Example Workflows](#example-workflows)
9. [Troubleshooting](#troubleshooting)

---

## 📖 Overview

### The Problem

The existing RAG system has:
- **discovered_urls.json**: 29,894 URLs discovered by crawler
- **ingested_urls.json**: ~5,000 URLs successfully ingested
- **Gap**: ~24,894 missing URLs never ingested

### The Solution

Two completely independent processes:

1. **Pipeline 1 (Missing URL Ingestion)**: Process URLs discovered but not yet ingested
2. **Pipeline 2 (Incremental Recrawl)**: Continuously crawl for new URLs, then ingest them

### Design Principle

```
❌ NO shared controller
❌ NO combined execution
❌ NO cross-trigger logic
✅ Two completely separate entry files
✅ Each runs independently
✅ Zero modification to existing pipeline
```

---

## 🏗️ System Architecture

### Folder Structure

```
pipelines/
└── url_governor/
    ├── missing_url_ingestion/
    │   ├── __init__.py
    │   ├── run_missing_ingestion.py       ← ENTRY POINT 1
    │   ├── missing_checker.py
    │   ├── json_utils.py
    │   ├── url_normalizer.py
    │   ├── logger_config.py
    │   └── logs/
    │       └── missing_ingestion.log
    │
    └── incremental_recrawl_ingestion/
        ├── __init__.py
        ├── run_incremental_ingestion.py   ← ENTRY POINT 2
        ├── recrawl_monitor.py
        ├── json_utils.py
        ├── url_normalizer.py
        ├── logger_config.py
        └── logs/
            └── incremental_ingestion.log
```

### High-Level Flow Diagram

```
PIPELINE 1 (Missing URLs)
┌─────────────────────────────────────────────┐
│ run_missing_ingestion.py                    │
├─────────────────────────────────────────────┤
│ 1. Read discovered_urls.json                │
│ 2. Read ingested_urls.json                  │
│ 3. Normalize all URLs                       │
│ 4. Compute: missing = discovered - ingested│
│ 5. Call ingestion pipeline                  │
│    (from ingestion.ingest_pipeline)         │
│ 6. Update ingested_urls.json                │
│ 7. Log statistics                           │
└─────────────────────────────────────────────┘
        ↓
   [FAISS Updated]
   [Metadata Updated]


PIPELINE 2 (Incremental Recrawl)
┌─────────────────────────────────────────────┐
│ run_incremental_ingestion.py                │
├─────────────────────────────────────────────┤
│ 1. Run crawler (from crawler.bfs_crawler)   │
│ 2. Get crawled URLs                         │
│ 3. Compare: new = crawled - discovered     │
│ 4. If new URLs found:                       │
│    a. Append to discovered_urls.json        │
│    b. Call ingestion pipeline               │
│    c. Append to ingested_urls.json          │
│ 5. Log statistics                           │
└─────────────────────────────────────────────┘
        ↓
   [FAISS Updated]
   [Metadata Updated]
```

### Isolation Principle

```
Pipeline 1          Pipeline 2
   │                   │
   └─ INDEPENDENT ─────┘
   
Each can run 24/7 without triggering the other
Each writes only to its own log file
Each only calls EXISTING ingestion.ingest_pipeline
   (does NOT modify it)
```

---

## 🔍 Pipeline 1 — Missing URL Ingestion

### Purpose

**Ingest all URLs that were discovered but never successfully ingested.**

### Execution

```bash
# From project root
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py

# Or with explicit environment
conda activate base
cd E:/YCCE_RAG
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py
```

### Core Algorithm

```python
discovered_urls = load_json('data/discovered_urls.json')      # Set of ~29,894 URLs
ingested_urls = load_json('data/ingested_urls.json')          # Set of ~5,000 URLs

# Normalize all URLs (lowercase, strip trailing slash, etc.)
discovered_normalized = {normalize(url) for url in discovered_urls}
ingested_normalized = {normalize(url) for url in ingested_urls}

# Compute missing
missing_urls = discovered_normalized - ingested_normalized

print(f"Found {len(missing_urls)} URLs to ingest")

# Process missing URLs through existing ingestion pipeline
from ingestion.ingest_pipeline import run_ingestion
newly_ingested = run_ingestion(missing_urls)

# Update ingested_urls.json (atomic write)
existing_ingested = load_json('data/ingested_urls.json')
existing_ingested.extend(newly_ingested)
save_json_atomic('data/ingested_urls.json', existing_ingested)

# Log summary
log_summary(total=len(missing_urls), 
            successful=len(newly_ingested),
            failed=len(missing_urls) - len(newly_ingested))
```

### Expected Behavior Example

```
Input State:
  - discovered_urls.json: 29,894 URLs
  - ingested_urls.json: 5,000 URLs

Processing:
  ✓ Computing missing URLs...
  ✓ Found 24,894 URLs to ingest
  ✓ Ingesting batch 1/50... (500 URLs)
  ✓ Ingesting batch 2/50... (500 URLs)
  ... (continues) ...
  ✓ Ingesting batch 50/50... (394 URLs)

Output State:
  - ingested_urls.json: 5,000 + 24,894 = 29,894 URLs
  - FAISS index updated with new vectors
  - Log file: pipelines/url_governor/missing_url_ingestion/logs/missing_ingestion.log
```

### Key Files

| File | Purpose |
|------|---------|
| `run_missing_ingestion.py` | Main entry point; orchestrates the workflow |
| `missing_checker.py` | Computes missing URLs set difference |
| `json_utils.py` | Safe JSON reading/writing with atomic commits |
| `url_normalizer.py` | URL normalization (lowercase, strip /, remove #) |
| `logger_config.py` | Logging configuration (console + file) |

---

## 🔄 Pipeline 2 — Incremental Recrawl + New URL Ingestion

### Purpose

**Run crawler continuously, find new URLs, ingest them, update discovered set.**

### Execution

```bash
# From project root
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py

# Or with explicit environment
conda activate base
cd E:/YCCE_RAG
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py
```

### Core Algorithm

```python
# Step 1: Run the existing crawler
from crawler.bfs_crawler import run_crawler
crawled_urls = run_crawler()  # Crawls starting points, returns set of URLs

# Step 2: Load current discovered set
discovered_urls = load_json('data/discovered_urls.json')
discovered_normalized = {normalize(url) for url in discovered_urls}

# Step 3: Normalize crawled URLs
crawled_normalized = {normalize(url) for url in crawled_urls}

# Step 4: Find new URLs
new_urls = crawled_normalized - discovered_normalized

# Step 5: Handle results
if len(new_urls) == 0:
    log_info("No new URLs found")
    return

log_info(f"Found {len(new_urls)} new URLs")

# Step 6: Append new URLs to discovered
existing_discovered = load_json('data/discovered_urls.json')
existing_discovered.extend(new_urls)
save_json_atomic('data/discovered_urls.json', existing_discovered)

# Step 7: Ingest new URLs
from ingestion.ingest_pipeline import run_ingestion
newly_ingested = run_ingestion(new_urls)

# Step 8: Append newly ingested to ingested set
existing_ingested = load_json('data/ingested_urls.json')
existing_ingested.extend(newly_ingested)
save_json_atomic('data/ingested_urls.json', existing_ingested)

# Step 9: Log summary
log_summary(discovered=len(new_urls),
            ingested=len(newly_ingested),
            failed=len(new_urls) - len(newly_ingested))
```

### Expected Behavior Example

```
Input State:
  - discovered_urls.json: 29,894 URLs
  - ingested_urls.json: 29,894 URLs (after Pipeline 1)
  
Processing:
  ✓ Running crawler...
  ✓ Crawled 30,014 URLs
  ✓ Computing new URLs (30,014 - 29,894 = 120 new)
  ✓ Found 120 new URLs
  ✓ Appending to discovered_urls.json...
  ✓ Ingesting 120 new URLs...
  ✓ Ingestion successful: 118 URLs
  ✓ Ingestion failed: 2 URLs
  ✓ Appending to ingested_urls.json...

Output State:
  - discovered_urls.json: 30,014 URLs
  - ingested_urls.json: 30,012 URLs
  - FAISS index updated with 118 new vectors
  - Log file: pipelines/url_governor/incremental_recrawl_ingestion/logs/incremental_ingestion.log
```

### Key Files

| File | Purpose |
|------|---------|
| `run_incremental_ingestion.py` | Main entry point; orchestrates crawler + ingestion |
| `recrawl_monitor.py` | Monitors crawler output, detects new URLs |
| `json_utils.py` | Safe JSON reading/writing with atomic commits |
| `url_normalizer.py` | URL normalization (lowercase, strip /, remove #) |
| `logger_config.py` | Logging configuration (console + file) |

---

## 🔧 Common Requirements

### URL Normalization

All URL comparisons must use normalized URLs to avoid duplicates from:
- `https://example.com`
- `https://example.com/`
- `https://EXAMPLE.COM/`

**Normalization Rules:**

```python
def normalize(url: str) -> str:
    """
    Normalize URL for comparison.
    
    Rules:
    1. Convert to lowercase
    2. Remove fragment (#section)
    3. Strip trailing slash
    4. Optional: remove query parameters
    """
    # Remove fragment
    url = url.split('#')[0]
    
    # Lowercase
    url = url.lower()
    
    # Strip trailing slash
    url = url.rstrip('/')
    
    return url
```

**Implementation:** `url_normalizer.py` in each pipeline

### JSON Safety (Atomic Writes)

Prevent corruption from interrupted writes:

```python
def save_json_atomic(filepath: str, data: list) -> None:
    """
    Safely write JSON using atomic operations.
    
    Process:
    1. Write to temporary file (same directory)
    2. Verify temp file is valid JSON
    3. Replace original with temp file
    4. Confirm replacement success
    """
    import json
    from pathlib import Path
    import shutil
    
    filepath = Path(filepath)
    temp_path = filepath.parent / f"{filepath.name}.tmp"
    
    # Write to temp
    with open(temp_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Verify
    with open(temp_path, 'r') as f:
        json.load(f)  # Will raise if invalid
    
    # Replace (atomic on most filesystems)
    shutil.move(str(temp_path), str(filepath))
```

**Implementation:** `json_utils.py` in each pipeline

### Logging Configuration

Each pipeline logs independently to its own file plus console.

**Requirements:**

- **Log Level:** INFO
- **Format:** `[TIMESTAMP] [LEVEL] - Message`
- **Outputs:**
  - Console (STDOUT)
  - File in pipeline's `logs/` subdirectory

**Example Log Entry:**

```
[2026-03-02 14:23:45,123] [INFO] - Starting missing URL ingestion...
[2026-03-02 14:23:46,456] [INFO] - Loaded 29,894 discovered URLs
[2026-03-02 14:23:46,789] [INFO] - Loaded 5,000 ingested URLs
[2026-03-02 14:23:47,012] [INFO] - Found 24,894 missing URLs
[2026-03-02 14:24:15,234] [INFO] - Ingestion completed: 24,894 successful, 0 failed
[2026-03-02 14:24:16,567] [INFO] - Updated ingested_urls.json
[2026-03-02 14:24:17,890] [INFO] - ✓ Pipeline completed successfully
```

**Implementation:** `logger_config.py` in each pipeline

### FAISS Safety

**Critical Constraint:** Do NOT modify FAISS logic.

**Why:** Existing ingestion pipeline already:
- Embeds URLs
- Stores vectors in FAISS
- Updates metadata

**Both Pipelines:**
- Call `ingestion.ingest_pipeline.run_ingestion()` ONLY
- NEVER directly access FAISS index
- NEVER reinitialize FAISS
- Trust ingestion pipeline for deduplication

**Result:** Zero duplicate vectors guaranteed because:
1. Missing URLs are ingested only once
2. New URLs are ingested only once
3. Both processes track what was ingested
4. Ingestion pipeline handles vector storage atomically

---

## 🚀 Execution Guide

### Prerequisites

```bash
# Verify environment
python --version                    # 3.9+
python -c "import faiss; print('FAISS OK')"
python -c "import langchain; print('LangChain OK')"
python -c "import scrapy; print('Scrapy OK')"

# Verify data files exist
ls data/discovered_urls.json
ls data/ingested_urls.json
ls data/faiss_index/index.faiss
```

### Running Pipeline 1 (Missing URLs)

**Interactive Mode:**

```bash
cd E:/YCCE_RAG
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py
```

**With Logging to File:**

```bash
cd E:/YCCE_RAG
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py 2>&1 | tee pipeline1_console.log
```

**Expected Output:**

```
[INFO] - Starting missing URL ingestion...
[INFO] - Status: IDLE
[INFO] - Loaded 29,894 discovered URLs
[INFO] - Loaded 5,000 ingested URLs
[INFO] - Found 24,894 missing URLs to ingest
[INFO] - Processing batch 1 of 50...
[INFO] - Batch 1: 500 URLs ingested, 0 failed
...
[INFO] - Processing batch 50 of 50...
[INFO] - Batch 50: 394 URLs ingested, 0 failed
[INFO] - ✓ Total: 24,894 ingested, 0 failed
[INFO] - Updating ingested_urls.json...
[INFO] - ✓ Pipeline completed successfully in 1234 seconds
```

### Running Pipeline 2 (Incremental Recrawl)

**Interactive Mode:**

```bash
cd E:/YCCE_RAG
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py
```

**With Logging to File:**

```bash
cd E:/YCCE_RAG
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py 2>&1 | tee pipeline2_console.log
```

**Expected Output:**

```
[INFO] - Starting incremental recrawl and ingestion...
[INFO] - Running crawler...
[INFO] - Crawler completed: 30,014 URLs found
[INFO] - Loaded 29,894 discovered URLs
[INFO] - Computing new URLs...
[INFO] - Found 120 new URLs
[INFO] - Appending to discovered_urls.json...
[INFO] - Attempting to ingest 120 new URLs...
[INFO] - Batch 1: 120 URLs ingested, 0 failed
[INFO] - ✓ Total: 120 ingested, 0 failed
[INFO] - Updating ingested_urls.json...
[INFO] - ✓ Pipeline completed successfully in 456 seconds
```

### Scheduling (Optional)

#### Windows Task Scheduler

**Pipeline 1 - Daily at 2:00 AM:**

```batch
# Create scheduled_pipeline1.bat
@echo off
cd E:\YCCE_RAG
conda activate base
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py >> logs/pipeline1_scheduled.log 2>&1
```

Then create Windows Task Scheduler task:
- Trigger: Daily at 2:00 AM
- Action: Run C:\path\to\scheduled_pipeline1.bat

#### Linux/Mac Cron

```bash
# Edit crontab
crontab -e

# Pipeline 1 - Daily at 2:00 AM
0 2 * * * cd /path/to/YCCE_RAG && python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py >> logs/pipeline1_cron.log 2>&1

# Pipeline 2 - Every 6 hours
0 */6 * * * cd /path/to/YCCE_RAG && python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py >> logs/pipeline2_cron.log 2>&1
```

---

## 🛡️ Safety & Constraints

### Strict Design Rules

✅ **ALLOWED:**
- Reading `data/*.json`
- Calling `ingestion.ingest_pipeline.run_ingestion()`
- Calling `crawler.bfs_crawler.run_crawler()`
- Writing to own log file
- Modifying `data/discovered_urls.json` (Pipeline 2 only)
- Modifying `data/ingested_urls.json` (both pipelines)

❌ **FORBIDDEN:**
- Modifying `ingestion/` folder
- Modifying `crawler/` folder
- Modifying `vectordb/` folder
- Modifying `data/faiss_index/` directly
- Creating shared state between pipelines
- Triggering one pipeline from the other
- Rewriting URL comparison logic

### Error Handling

**Pipeline 1 - Missing URL Ingestion:**

| Error | Behavior |
|-------|----------|
| `discovered_urls.json` missing | Log error, exit |
| `ingested_urls.json` missing | Create empty file, continue |
| Ingestion failure (partial) | Log counts, continue to next batch |
| JSON corruption detected | Rollback to backup, log critical error |
| Network timeout | Retry 3 times, log and continue |

**Pipeline 2 - Incremental Recrawl:**

| Error | Behavior |
|-------|----------|
| Crawler crash | Log error, exit gracefully |
| No new URLs found | Log info message, exit cleanly |
| Ingestion failure (partial) | Log counts, update metadata only if success |
| FAISS unavailable | Log error, exit |

### Data Integrity

**Backup Strategy:**

Before any write to JSON files, create backup:

```python
from pathlib import Path
import shutil

def safe_write_json(filepath: str, data: list) -> None:
    filepath = Path(filepath)
    
    # Create backup
    backup_path = filepath.parent / f"{filepath.name}.backup"
    if filepath.exists():
        shutil.copy2(filepath, backup_path)
    
    # Write new data atomically
    save_json_atomic(filepath, data)
```

### Version Safety

**Do NOT upgrade these without testing:**

```
langchain
faiss-cpu or faiss-gpu
sentence-transformers
```

Each pipeline is compatible with existing versions.

---

## 📊 Example Workflows

### Scenario 1: Initial Backfill (Pipeline 1 Only)

**Goal:** Ingest all 24,894 missing URLs

**Execution:**

```bash
# Day 1 - Morning
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py

# Monitor progress
tail -f pipelines/url_governor/missing_url_ingestion/logs/missing_ingestion.log

# Expected result: All missing URLs ingested
```

**Before:**
```
discovered: 29,894
ingested: 5,000
gap: 24,894
```

**After:**
```
discovered: 29,894
ingested: 29,894
gap: 0
```

### Scenario 2: Continuous Recrawl (Pipeline 2 Scheduled)

**Goal:** Every 6 hours, crawl for new URLs and ingest them

**Setup:**

```bash
# Create scheduler wrapper
cat > scripts/scheduler_wrapper.py << 'EOF'
import subprocess
import time
from datetime import datetime

while True:
    print(f"[{datetime.now()}] Running incremental recrawl...")
    result = subprocess.run(
        "python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py",
        shell=True,
        cwd="E:/YCCE_RAG"
    )
    
    print(f"[{datetime.now()}] Pipeline returned code: {result.returncode}")
    print(f"[{datetime.now()}] Sleeping for 6 hours...")
    time.sleep(6 * 3600)
EOF

# Run scheduler
python scripts/scheduler_wrapper.py
```

**Expected Pattern Over Time:**

```
Hour 0:   discovered: 29,894, ingested: 29,894 (after Pipeline 1)
Hour 6:   discovered: 29,905, ingested: 29,903 (after Pipeline 2, found 11 new)
Hour 12:  discovered: 29,907, ingested: 29,905 (found 2 new)
Hour 18:  discovered: 29,907, ingested: 29,905 (no new URLs)
Hour 24:  discovered: 29,914, ingested: 29,912 (found 7 new)
```

### Scenario 3: Manual Verification

**Check if everything is in sync:**

```python
import json

def verify_state():
    with open('data/discovered_urls.json') as f:
        discovered = set(json.load(f))
    
    with open('data/ingested_urls.json') as f:
        ingested = set(json.load(f))
    
    missing = discovered - ingested
    
    print(f"Discovered:  {len(discovered):,} URLs")
    print(f"Ingested:    {len(ingested):,} URLs")
    print(f"Missing:     {len(missing):,} URLs")
    print(f"Unseen:      {len(ingested - discovered):,} URLs (errors)")
    
    if len(missing) > 0:
        print(f"\nSample missing URLs:")
        for url in list(missing)[:5]:
            print(f"  - {url}")

verify_state()
```

---

## 🔧 Troubleshooting

### Pipeline 1 Hangs or Is Very Slow

**Symptom:** Takes hours to ingest 24k URLs

**Possible Causes:**

1. **Network issues:** URLs timeout during ingestion
   - **Solution:** Check internet connection, retry with timeout settings

2. **Ingestion pipeline is slow:** Embedding model slow
   - **Solution:** Check GPU availability, model loading times

3. **Batch size too large:** OOM errors
   - **Solution:** Reduce batch size in ingestion call

**Diagnostic:**

```bash
# Check logs
tail -100 pipelines/url_governor/missing_url_ingestion/logs/missing_ingestion.log

# Test single URL manually
python -c "
from ingestion.ingest_pipeline import run_ingestion
result = run_ingestion(['https://example.com'])
print(f'Time to ingest 1 URL: {result}')
"
```

### Pipeline 2 Finds No New URLs

**Symptom:** Crawler found 0 new URLs in last run

**Possible Causes:**

1. **Crawler already visited all reachable URLs**
   - **Solution:** This is normal; expand crawler starting points if needed

2. **Normalized URL comparison failing**
   - **Solution:** Check URL normalization rules

3. **Crawler timeout:** Crawler didn't finish
   - **Solution:** Increase crawler timeout, check crawler logs

**Diagnostic:**

```bash
# Check crawler output directly
python -c "
from crawler.bfs_crawler import run_crawler
urls = run_crawler()
print(f'Crawler found {len(urls)} URLs')
"

# Check if discovered_urls.json matches
python scripts/verify_state.py
```

### JSON File Corruption

**Symptom:** JSONDecodeError when loading data/discovered_urls.json

**Recovery:**

```bash
# Check if backup exists
ls -la data/discovered_urls.json*

# Restore from backup
cp data/discovered_urls.json.backup data/discovered_urls.json

# Verify
python -c "import json; json.load(open('data/discovered_urls.json'))"
```

### FAISS Index Out of Sync

**Symptom:** FAISS vectors don't match ingested_urls count

**Diagnostic:**

```python
import faiss
import json

index = faiss.read_index('data/faiss_index/index.faiss')
print(f"FAISS vectors: {index.ntotal}")

with open('data/ingested_urls.json') as f:
    ingested = json.load(f)
print(f"Ingested URLs: {len(ingested)}")

if index.ntotal != len(ingested):
    print("⚠️  MISMATCH DETECTED")
    print("This may be due to:")
    print("1. Ingestion pipeline crash during update")
    print("2. Manual FAISS modifications")
    print("3. Multiple ingestion processes running simultaneously")
```

**Solution:**

Do NOT manually fix FAISS. Instead:

1. Stop both pipelines
2. Check ingestion logs for errors during last run
3. Verify data files are valid JSON
4. Re-run Pipeline 1 (will safely re-ingest any missing)

### Running Multiple Instances

**⚠️  WARNING:** Running Pipeline 1 and Pipeline 2 simultaneously is safe, BUT:

- Each will write to `ingested_urls.json`
- Writes are atomic (safe), but final count may be ±1 due to race conditions
- FAISS updates are serialized by ingestion pipeline (safe)

**Best Practice:** Run pipelines at different times or with file locking.

---

## 📈 Monitoring & Metrics

### Pipeline 1 Metrics

Track in `logs/missing_ingestion.log`:

```
Total Missing URLs:    24,894
Batches Processed:     50
URLs per Batch:        500
Success Rate:          99.8% (24,844 / 24,894)
Failed URLs:           50
Average Time/Batch:    25 seconds
Total Time:            1,250 seconds (20 minutes)
```

### Pipeline 2 Metrics

Track in `logs/incremental_ingestion.log`:

```
Crawled URLs:          30,014
Previously Discovered: 29,894
New URLs Found:        120
New URLs Ingested:     118
New URLs Failed:       2
Ingestion Success:     98.3% (118 / 120)
Total Time:            456 seconds (7.6 minutes)
```

### Query Example

Extract metrics from logs:

```bash
# Count successful ingestions (Pipeline 1)
grep "URLs ingested" pipelines/url_governor/missing_url_ingestion/logs/missing_ingestion.log | tail -5

# Count new URLs found (Pipeline 2)
grep "new URLs" pipelines/url_governor/incremental_recrawl_ingestion/logs/incremental_ingestion.log | tail -5
```

---

## 🎯 Next Steps

After implementing this URL Governor system:

### Phase 1 (Immediate)
- [ ] Create folder structure
- [ ] Implement Pipeline 1
- [ ] Test with small batch (100 URLs)
- [ ] Run full Pipeline 1 ingestion

### Phase 2 (1-2 weeks)
- [ ] Implement Pipeline 2
- [ ] Test edge cases (0 new URLs, many new URLs)
- [ ] Set up scheduling (cron/Task Scheduler)

### Phase 3 (Ongoing)
- [ ] Monitor logs daily
- [ ] Track ingestion success rates
- [ ] Adjust batch sizes if needed
- [ ] Update crawler starting points if saturation detected

### Optional Enhancements
- 🎯 **Statistics Tracker:** Real-time dashboard of discovered vs ingested
- 🔐 **Locking Mechanism:** Prevent simultaneous execution of same pipeline
- 🔄 **Retry Logic:** Automatic retry for failed URLs
- 📧 **Notifications:** Email alerts on pipeline failures
- 📊 **Performance Tuning:** GPU acceleration for embeddings

---

## 📞 Support & Questions

### Common Questions

**Q: Can I run both pipelines at the same time?**
A: Yes, but design them to run at different times to avoid I/O contention.

**Q: What if ingestion fails for some URLs?**
A: Pipeline logs the failure and continues. Failed URLs remain in `discovered_urls.json` and will be retried in next Pipeline 1 run.

**Q: How do I know which pipeline is running?**
A: Check running processes:
```bash
# Windows
Get-Process python | Where-Object {$_.CommandLine -like "*run_missing*"}

# Linux/Mac
ps aux | grep run_missing_ingestion.py
```

**Q: Can I modify the ingestion pipeline?**
A: No. Both pipelines depend on it. Modifications must go into the pipeline files themselves.

**Q: What if I want to exclude certain URLs?**
A: Modify `url_normalizer.py` to filter URLs:
```python
EXCLUDED_DOMAINS = ['spam.com', 'excluded.net']

def normalize(url: str) -> str:
    # ... existing code ...
    
    # Filter
    for domain in EXCLUDED_DOMAINS:
        if domain in url:
            return None  # Skip this URL
    
    return url
```

**Q: How do I scale this for 100k+ URLs?**
A: 
- Increase batch size in ingestion calls
- Use GPU for embeddings (FAISS-GPU)
- Run Pipeline 2 more frequently
- Consider sharding URLs across processes

---

## 📄 Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-02 | Initial architecture design and documentation |

---

## 🔒 Agreement Summary

✅ **This architecture ensures:**
- ✔️ Two completely independent executables
- ✔️ Clean segregation of concerns
- ✔️ No cross-execution or interference
- ✔️ Zero modification to existing pipeline
- ✔️ Production-ready code structure
- ✔️ Proper error handling and logging
- ✔️ FAISS safety and integrity
- ✔️ Scalable to 30k+ URLs

**Status:** Ready for implementation.

---

*Generated for YCCE_RAG Project - URL Governor System*
