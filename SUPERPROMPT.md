# Superprompt for GitHub Copilot - Fix Pipeline Failures

## Project Context

You are working on a YCCE_RAG project. The `pipelines/url_governor/` folder contains two independent URL ingestion pipelines that are currently failing. Your task is to fix ONLY the issues within this folder WITHOUT modifying any other folders or files outside of `pipelines/url_governor/`.

## Folder Structure (ONLY EDIT THESE FILES)

```
pipelines/url_governor/
├── __init__.py
├── README.md
├── incremental_recrawl_ingestion/
│   ├── __init__.py
│   ├── json_utils.py
│   ├── logger_config.py
│   ├── recrawl_monitor.py      ← FIX THIS FILE
│   ├── run_incremental_ingestion.py
│   ├── url_normalizer.py      ← FIX THIS FILE
│   └── logs/
└── missing_url_ingestion/
    ├── __init__.py
    ├── json_utils.py
    ├── logger_config.py
    ├── missing_checker.py     ← FIX THIS FILE
    ├── run_missing_ingestion.py
    ├── url_normalizer.py      ← FIX THIS FILE
    └── logs/
```

## DO NOT MODIFY (Forbidden)

- `crawler/bfs_crawler.py`
- `ingestion/ingest_pipeline.py`
- `vectordb/faiss_stores.py`
- Any other files outside `pipelines/url_governor/`

---

## ISSUE 1: Wrong Import in recrawl_monitor.py (CRITICAL)

**File:** `pipelines/url_governor/incremental_recrawl_ingestion/recrawl_monitor.py`

**Current Code (Line ~67):**
```
python
from crawler.bfs_crawler import bfs_crawl
```

**Problem:** This is correct, but the issue is that when the crawler returns results, the format might not match what the pipeline expects. The `bfs_crawl` function returns a list of dictionaries like:
```
python
[{"url": "http://example.com", "type": "html", "depth": 0}, ...]
```

But the normalization expects either:
- A list of strings: `["http://example.com", ...]`
- OR a list of dicts with 'url' key

**Fix Required:** In `recrawl_monitor.py`, the `run_crawler()` method normalizes the output. Make sure it extracts URLs correctly before normalization.

---

## ISSUE 2: URL Normalization Bug (CRITICAL)

**Files to Fix:**
1. `pipelines/url_governor/missing_url_ingestion/url_normalizer.py`
2. `pipelines/url_governor/incremental_recrawl_ingestion/url_normalizer.py`

**Problem:** The logs show:
- "discovered raw: 27890, discovered normalized: 2871"
- "ingested raw: 5000, ingested normalized: 2683"

This means ~92% of URLs are being marked as "invalid" during normalization! This is because the `normalize()` function raises `ValueError` for any URL that fails parsing, and these failed URLs are collected in the `invalid` list and discarded.

**Root Cause:** The `normalize()` function is too strict. Many URLs might have:
- Missing schemes (e.g., "www.example.com" instead of "http://www.example.com")
- Special characters that cause parsing issues
- Very long URLs with complex query strings

**Fix Required:** Update the `normalize()` function to:
1. Handle URLs without schemes by adding `http://` prefix automatically
2. Use try/except to gracefully handle parsing failures instead of raising errors
3. Return the original URL (or a best-effort normalized version) even if parsing fails
4. Never lose URLs during normalization

**Recommended Fix:**
```
python
def normalize(url: str, remove_query_params: bool = False) -> str:
    """
    Normalize URL for comparison purposes.
    Never raises errors - always returns a best-effort normalized URL.
    """
    if not url or not isinstance(url, str):
        return ""  # Return empty string instead of raising
    
    url = url.strip()
    if not url:
        return ""
    
    try:
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # Parse URL
        parsed = urlparse(url)
        
        # If parsing failed (no netloc), return original
        if not parsed.netloc:
            return url
        
        # Lowercase scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Remove query params if requested
        query = "" if remove_query_params else parsed.query.lower()
        
        # Reconstruct without fragment
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
        
        # Strip trailing slash
        normalized = normalized.rstrip('/')
        
        return normalized
    
    except Exception:
        # Return best-effort: lowercase, stripped
        return url.lower().strip()
```

Also update `normalize_batch()` to handle empty strings:
```
python
def normalize_batch(urls: list, remove_query_params: bool = False) -> dict:
    valid = set()
    invalid = []
    
    for url in urls:
        normalized = normalize(url, remove_query_params)
        # Skip empty strings but don't count as invalid
        if normalized:
            valid.add(normalized)
        elif url and isinstance(url, str) and url.strip():
            # URL was provided but couldn't be normalized
            invalid.append(url)
    
    return {
        'valid': valid,
        'invalid': invalid,
        'valid_count': len(valid),
        'invalid_count': len(invalid)
    }
```

---

## ISSUE 3: Logging/Encoding Issue (Minor)

**File:** `pipelines/url_governor/missing_url_ingestion/json_utils.py`

**Problem:** The log shows error: `'charmap' codec can't encode character '\U0001f4e5'`

**Fix:** Ensure all file operations use `encoding='utf-8'`. The json_utils.py already uses this, but verify the logger is also configured correctly.

---

## Verification Steps

After making fixes, test by running:

```
bash
# Test Pipeline 1 (Missing URL Ingestion)
python pipelines/url_governor/missing_url_ingestion/run_missing_ingestion.py

# Test Pipeline 2 (Incremental Recrawl)
python pipelines/url_governor/incremental_recrawl_ingestion/run_incremental_ingestion.py
```

**Expected Results:**
1. Pipeline 1 should find and ingest missing URLs without massive normalization loss
2. Pipeline 2 should run the crawler without import errors
3. Normalization should preserve at least 95% of URLs (not lose 92%)

---

## Summary of Files to Modify

| File | Issue to Fix |
|------|--------------|
| `pipelines/url_governor/incremental_recrawl_ingestion/recrawl_monitor.py` | Ensure crawler output format is handled correctly |
| `pipelines/url_governor/missing_url_ingestion/url_normalizer.py` | Fix normalize() to not lose URLs |
| `pipelines/url_governor/incremental_recrawl_ingestion/url_normalizer.py` | Fix normalize() to not lose URLs |

---

## Important Notes

1. The `crawler/bfs_crawler.py` exports `bfs_crawl` function - this is correct and should not be modified
2. The `ingestion/ingest_pipeline.py` and `vectordb/faiss_stores.py` work correctly - the issue is in how the pipeline uses them
3. After fixing normalization, the "missing URLs" count should be much smaller (because we weren't actually missing that many - we were just losing them during normalization)
4. The pipelines should work with the existing ingestion and crawler modules
